"""HDLC framing for DLMS/COSEM over RS-485 (IEC 62056-46)."""
import struct
import time

# Pre-computed FCS16 lookup table
FCS_TABLE = []
for _i in range(256):
    _fcs = _i
    for _ in range(8):
        _fcs = (_fcs >> 1) ^ 0x8408 if _fcs & 1 else _fcs >> 1
    FCS_TABLE.append(_fcs)


def fcs16(data: bytes) -> int:
    fcs = 0xFFFF
    for b in data:
        fcs = (fcs >> 8) ^ FCS_TABLE[(fcs ^ b) & 0xFF]
    return fcs ^ 0xFFFF


def make_hdlc(dest: int, src: int, ctrl: int, info: bytes = b"") -> bytes:
    header = bytes([dest, src, ctrl])
    if info:
        total_len = 2 + len(header) + 2 + len(info) + 2
        fmt = bytes([0xA0 | ((total_len >> 8) & 0x07), total_len & 0xFF])
        hcs = fcs16(fmt + header)
        fcs_data = fmt + header + struct.pack("<H", hcs) + info
        fcs = fcs16(fcs_data)
        return b"\x7E" + fcs_data + struct.pack("<H", fcs) + b"\x7E"
    else:
        total_len = 2 + len(header) + 2
        fmt = bytes([0xA0 | ((total_len >> 8) & 0x07), total_len & 0xFF])
        fcs_data = fmt + header
        fcs = fcs16(fcs_data)
        return b"\x7E" + fcs_data + struct.pack("<H", fcs) + b"\x7E"


def send_recv(ser, frame: bytes, timeout: float = 3.0, on_tx=None, on_rx=None) -> bytes:
    """Send HDLC frame and receive response.

    on_tx/on_rx callbacks receive hex string for logging.
    """
    ser.reset_input_buffer()
    ser.write(frame)
    if on_tx:
        on_tx(hex_str(frame))
    time.sleep(0.35)
    data = b""
    start = time.time()
    while time.time() - start < timeout:
        if ser.in_waiting:
            data += ser.read(ser.in_waiting)
            if len(data) > 2 and data[-1] == 0x7E and data.count(0x7E) >= 2:
                break
        time.sleep(0.02)
    if on_rx and data:
        on_rx(hex_str(data))
    return data


def hex_str(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)
