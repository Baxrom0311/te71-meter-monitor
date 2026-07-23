"""test_lora_decoder.py — LoRa packet decoder unit testlari."""
import struct
import pytest
from services.lora_decoder import LoRaPacketDecoder, crc16_ccitt


def test_crc16_ccitt():
    data = b"123456789"
    crc = crc16_ccitt(data)
    assert isinstance(crc, int)
    assert crc != 0


def test_decode_soil_uplink():
    mac = b"\x01\x02\x03\x04\x05\x06"
    flags = 0
    humidity_raw = 8530  # 85.30%
    
    buf = struct.pack("<B6sBh", 0x03, mac, flags, humidity_raw)
    crc = crc16_ccitt(buf)
    buf += struct.pack("<H", crc)

    res = LoRaPacketDecoder.decode_packet(buf)
    assert res is not None
    assert res["valid_crc"] is True
    assert res["type"] == "SOIL_UPLINK"
    assert res["humidity_pct"] == 85.30


def test_decode_electricity_uplink():
    mac = b"\x10\x20\x30\x40\x50\x60"
    flags = 0x01 # is_te73
    serial_str = b"TE71_000123\x00\x00"
    v1, v2, v3 = 22000, 22100, 21950 # 220.0V
    i1, i2, i3 = 10500, 10200, 9800  # 10.5A
    power_w = 2310
    freq_chz = 5000 # 50.0Hz
    energy_wh = 125000 # 125.0kWh
    pf_pct = 98 # 0.98

    fmt = "<B6sB13s" + "h"*6 + "i" + "h" + "i" + "h"
    buf = struct.pack(fmt, 
        0x01, mac, flags, serial_str,
        v1, v2, v3, i1, i2, i3,
        power_w, freq_chz, energy_wh, pf_pct
    )
    crc = crc16_ccitt(buf)
    buf += struct.pack("<H", crc)

    res = LoRaPacketDecoder.decode_packet(buf)
    assert res is not None
    assert res["valid_crc"] is True
    assert res["type"] == "ELECTRICITY_UPLINK"
    assert res["meter_serial"] == "TE71_000123"
    assert res["voltage_v"]["l1"] == 220.0
    assert res["current_a"]["l1"] == 10.5
    assert res["energy_kwh"] == 125.0
