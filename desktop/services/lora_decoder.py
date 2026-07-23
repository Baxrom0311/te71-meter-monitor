"""lora_decoder.py — LoRa ikkilik va text paketlarini tahlil qilish va dekodlash.

`iot/include/lora_packet.h` C++ strukturalari bilan 100% mos keladi.
"""
import struct


def crc16_ccitt(data: bytes) -> int:
    """CRC16-CCITT hisoblash (lora_packet.h lora_crc16 bilan mos)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


class LoRaPacketDecoder:
    """ESP32 LoRa paketlarini dekodlash xizmati."""

    @staticmethod
    def parse_hex_string(hex_str: str) -> bytes | None:
        """Hex matnini ikkilik baytlarga aylantiradi."""
        try:
            clean_hex = hex_str.strip().replace(" ", "").replace("0x", "")
            return bytes.fromhex(clean_hex)
        except Exception:
            return None

    @classmethod
    def decode_packet(cls, data: bytes) -> dict | None:
        """LoRa UPLINK / SOIL_UPLINK paketlarini dekodlaydi."""
        if not data or len(data) < 12:
            return None

        pkt_type = data[0]

        # ── PKT_UPLINK_SOIL (0x03) ── 12 bytes
        if pkt_type == 0x03 and len(data) >= 12:
            try:
                pkt_t, mac_b, flags, humidity_raw, crc_rx = struct.unpack("<B6sBhH", data[:12])
                mac_str = ":".join(f"{b:02X}" for b in mac_b)
                crc_calc = crc16_ccitt(data[:10])

                return {
                    "valid_crc": (crc_rx == crc_calc),
                    "type": "SOIL_UPLINK",
                    "type_code": 0x03,
                    "mac": mac_str,
                    "flags": flags,
                    "humidity_pct": humidity_raw / 100.0,
                    "crc_rx": hex(crc_rx),
                    "crc_calc": hex(crc_calc)
                }
            except Exception:
                return None

        # ── PKT_UPLINK Electricity (0x01) ── 47 bytes
        # Format: pkt_type(B), mac(6s), flags(B), meter_serial(13s), v_l1..l3(3h), i_l1..l3(3h), power_w(i), freq_chz(h), energy_wh(i), pf_pct(h), crc16(H)
        if pkt_type == 0x01 and len(data) >= 47:
            try:
                fmt = "<B6sB13s" + "h"*6 + "i" + "h" + "i" + "hH"
                unpacked = struct.unpack(fmt, data[:47])

                pkt_t = unpacked[0]
                mac_b = unpacked[1]
                flags = unpacked[2]
                serial_b = unpacked[3]
                v_l1, v_l2, v_l3 = unpacked[4], unpacked[5], unpacked[6]
                i_l1, i_l2, i_l3 = unpacked[7], unpacked[8], unpacked[9]
                power_w = unpacked[10]
                freq_chz = unpacked[11]
                energy_wh = unpacked[12]
                pf_pct = unpacked[13]
                crc_rx = unpacked[14]

                mac_str = ":".join(f"{b:02X}" for b in mac_b)
                serial_str = serial_b.decode("utf-8", errors="ignore").rstrip("\x00")
                crc_calc = crc16_ccitt(data[:45])

                return {
                    "valid_crc": (crc_rx == crc_calc),
                    "type": "ELECTRICITY_UPLINK",
                    "type_code": 0x01,
                    "mac": mac_str,
                    "is_te73": bool(flags & 0x01),
                    "test_mode": bool(flags & 0x02),
                    "meter_serial": serial_str,
                    "voltage_v": {
                        "l1": v_l1 / 100.0,
                        "l2": v_l2 / 100.0,
                        "l3": v_l3 / 100.0
                    },
                    "current_a": {
                        "l1": i_l1 / 1000.0,
                        "l2": i_l2 / 1000.0,
                        "l3": i_l3 / 1000.0
                    },
                    "power_w": power_w,
                    "power_kw": power_w / 1000.0,
                    "frequency_hz": freq_chz / 100.0,
                    "energy_kwh": energy_wh / 1000.0,
                    "power_factor": pf_pct / 100.0,
                    "crc_rx": hex(crc_rx),
                    "crc_calc": hex(crc_calc)
                }
            except Exception:
                return None

        return None

    @classmethod
    def parse_serial_log_line(cls, line: str) -> dict | None:
        """Serial monitor matnidan LoRa RSSI/SNR va payload ma'lumotlarini ajratib oladi."""
        if not line:
            return None

        res = {}
        if "RSSI" in line.upper():
            import re
            m = re.search(r"RSSI[:=]?\s*(-?\d+)", line, re.IGNORECASE)
            if m:
                res["rssi"] = int(m.group(1))

        if "SNR" in line.upper():
            import re
            m = re.search(r"SNR[:=]?\s*(-?\d+\.?\d*)", line, re.IGNORECASE)
            if m:
                res["snr"] = float(m.group(1))

        if "[" in line and "]" in line:
            import re
            m = re.search(r"\[(?:HEX|PKT|PAYLOAD)\]\s*([0-9A-Fa-f\s]{24,})", line)
            if m:
                raw_bytes = cls.parse_hex_string(m.group(1))
                if raw_bytes:
                    decoded = cls.decode_packet(raw_bytes)
                    if decoded:
                        res["packet"] = decoded

        return res if res else None
