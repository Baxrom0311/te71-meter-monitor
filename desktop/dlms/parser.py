"""DLMS/COSEM data type parser and encoder."""
import struct
from datetime import datetime


# DLMS unit codes -> human readable
UNIT_NAMES = {
    1: "", 27: "Wh", 28: "VAh", 29: "VARh", 30: "W", 31: "VA", 32: "VAR",
    33: "A", 35: "V", 44: "Hz", 255: "",
}

# DLMS type tags
TYPE_NAMES = {
    0: "null-data", 3: "boolean", 5: "int32", 6: "uint32", 9: "octet-string",
    10: "visible-string", 15: "int8", 16: "int16", 17: "uint8", 18: "uint16",
    22: "enum", 23: "float32", 24: "float64",
}


def parse_dlms_data(data: bytes):
    """Parse DLMS typed data, return (value, type_tag, raw_hex).

    Returns Python native types: int, float, str, bytes, bool, datetime, list, dict.
    """
    if not data:
        return None, 0, ""

    tag = data[0]

    if tag == 0x00:  # null
        return None, tag, ""
    elif tag == 0x03 and len(data) >= 2:  # boolean
        return bool(data[1]), tag, ""
    elif tag == 0x05 and len(data) >= 5:  # int32 (double-long)
        return struct.unpack(">i", data[1:5])[0], tag, ""
    elif tag == 0x06 and len(data) >= 5:  # uint32 (double-long-unsigned)
        return struct.unpack(">I", data[1:5])[0], tag, ""
    elif tag == 0x0F and len(data) >= 2:  # int8
        return struct.unpack("b", data[1:2])[0], tag, ""
    elif tag == 0x10 and len(data) >= 3:  # int16
        return struct.unpack(">h", data[1:3])[0], tag, ""
    elif tag == 0x11 and len(data) >= 2:  # uint8
        return data[1], tag, ""
    elif tag == 0x12 and len(data) >= 3:  # uint16
        return struct.unpack(">H", data[1:3])[0], tag, ""
    elif tag == 0x16 and len(data) >= 2:  # enum
        return data[1], tag, ""
    elif tag == 0x17 and len(data) >= 5:  # float32
        return struct.unpack(">f", data[1:5])[0], tag, ""
    elif tag == 0x18 and len(data) >= 9:  # float64
        return struct.unpack(">d", data[1:9])[0], tag, ""
    elif tag == 0x09 and len(data) >= 2:  # octet-string
        length = data[1]
        raw = data[2:2 + length]
        try:
            txt = raw.decode("ascii")
            if all(0x20 <= c < 0x7F for c in raw):
                return txt, tag, ""
        except (UnicodeDecodeError, ValueError):
            pass
        if length == 12:
            dt = parse_datetime(raw)
            if dt is not None:
                return dt, tag, ""
        if length == 6:
            # Possibly OBIS code / logical name.
            return tuple(raw), tag, ""
        return raw, tag, ""
    elif tag == 0x0A and len(data) >= 2:  # visible-string
        length = data[1]
        return data[2:2 + length].decode("ascii", errors="replace"), tag, ""
    elif tag == 0x02 and len(data) >= 2:  # structure
        count = data[1]
        items = []
        pos = 2
        for _ in range(count):
            val, _, _ = parse_dlms_data(data[pos:])
            items.append(val)
            pos += _dlms_data_size(data[pos:])
        return items, tag, ""
    elif tag == 0x01 and len(data) >= 2:  # array
        count = data[1]
        items = []
        pos = 2
        for _ in range(count):
            val, _, _ = parse_dlms_data(data[pos:])
            items.append(val)
            pos += _dlms_data_size(data[pos:])
        return items, tag, ""

    return data, tag, ""


def _dlms_data_size(data: bytes) -> int:
    """Calculate size of one DLMS data element."""
    if not data:
        return 0
    tag = data[0]
    fixed = {0: 1, 3: 2, 5: 5, 6: 5, 0x0F: 2, 0x10: 3,
             0x11: 2, 0x12: 3, 0x16: 2, 0x17: 5, 0x18: 9}
    if tag in fixed:
        return fixed[tag]
    if tag in (0x09, 0x0A) and len(data) >= 2:
        return 2 + data[1]
    if tag == 0x02 and len(data) >= 2:
        count = data[1]
        pos = 2
        for _ in range(count):
            pos += _dlms_data_size(data[pos:])
        return pos
    return len(data)


def parse_datetime(raw: bytes) -> datetime | None:
    """Parse DLMS octet-string[12] to datetime."""
    if len(raw) < 12:
        return None
    try:
        year = struct.unpack(">H", raw[0:2])[0]
        month, day = raw[2], raw[3]
        hour, minute, second = raw[5], raw[6], raw[7]
        if year == 0xFFFF or month == 0xFF:
            return None
        return datetime(year, month, day, hour, minute, second)
    except (ValueError, OverflowError):
        return None


def encode_datetime(dt: datetime) -> bytes:
    """Encode datetime to DLMS octet-string[12] for SET."""
    dow = dt.isoweekday()  # 1=Monday..7=Sunday
    return (struct.pack(">H", dt.year) +
            bytes([dt.month, dt.day, dow, dt.hour, dt.minute, dt.second,
                   0x00, 0x80, 0x00, 0x00]))


def parse_scaler_unit(data: bytes) -> tuple[int, str]:
    """Parse scaler_unit structure: struct{int8 scaler, enum unit}.

    Returns (scaler_exponent, unit_name).
    """
    if not data or len(data) < 6:
        return 0, ""
    # struct { int8, enum }
    if data[0] == 0x02 and data[1] == 0x02:
        scaler = struct.unpack("b", bytes([data[3]]))[0] if data[2] == 0x0F else 0
        unit_code = data[5] if data[4] == 0x16 else 0
        return scaler, UNIT_NAMES.get(unit_code, f"unit({unit_code})")
    return 0, ""


def format_value(raw_value, scaler: int = 0, unit: str = "") -> str:
    """Format a raw DLMS value with scaler and unit for display."""
    if raw_value is None:
        return "N/A"
    if isinstance(raw_value, datetime):
        return raw_value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(raw_value, (int, float)):
        if scaler != 0:
            scaled = raw_value * (10 ** scaler)
            if scaler < 0:
                decimals = abs(scaler)
                return f"{scaled:.{decimals}f} {unit}".strip()
            return f"{scaled:.0f} {unit}".strip()
        return f"{raw_value} {unit}".strip()
    if isinstance(raw_value, bytes):
        return " ".join(f"{b:02X}" for b in raw_value)
    if isinstance(raw_value, tuple):
        return ".".join(str(x) for x in raw_value)
    return str(raw_value)
