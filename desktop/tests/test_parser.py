"""Unit tests for DLMS/COSEM parser and formatter.

Run with: python3 -m unittest desktop/tests/test_parser.py
"""
import unittest
from datetime import datetime
import sys
import os

# Add desktop to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dlms.parser import (
    parse_dlms_data, parse_datetime, encode_datetime,
    parse_scaler_unit, format_value
)


class TestDLMSParser(unittest.TestCase):

    def test_parse_boolean(self):
        val, tag, _ = parse_dlms_data(bytes([0x03, 0x01]))
        self.assertEqual(val, True)
        self.assertEqual(tag, 3)

        val, tag, _ = parse_dlms_data(bytes([0x03, 0x00]))
        self.assertEqual(val, False)
        self.assertEqual(tag, 3)

    def test_parse_integers(self):
        # int16
        val, tag, _ = parse_dlms_data(bytes([0x10, 0x00, 0x0A]))
        self.assertEqual(val, 10)
        self.assertEqual(tag, 16)

        # uint16
        val, tag, _ = parse_dlms_data(bytes([0x12, 0x00, 0xFF]))
        self.assertEqual(val, 255)
        self.assertEqual(tag, 18)

        # int32
        val, tag, _ = parse_dlms_data(bytes([0x05, 0x00, 0x00, 0x00, 0x0F]))
        self.assertEqual(val, 15)
        self.assertEqual(tag, 5)

        # uint32
        val, tag, _ = parse_dlms_data(bytes([0x06, 0x00, 0x00, 0x01, 0x00]))
        self.assertEqual(val, 256)
        self.assertEqual(tag, 6)

    def test_parse_octet_string(self):
        # Plain ASCII string
        val, tag, _ = parse_dlms_data(bytes([0x09, 0x04, 0x54, 0x45, 0x53, 0x54]))
        self.assertEqual(val, "TEST")
        self.assertEqual(tag, 9)

    def test_datetime_encoding_decoding(self):
        dt = datetime(2025, 6, 15, 14, 30, 0)
        encoded = encode_datetime(dt)
        self.assertEqual(len(encoded), 12)

        decoded = parse_datetime(encoded)
        self.assertEqual(decoded.year, dt.year)
        self.assertEqual(decoded.month, dt.month)
        self.assertEqual(decoded.day, dt.day)
        self.assertEqual(decoded.hour, dt.hour)
        self.assertEqual(decoded.minute, dt.minute)
        self.assertEqual(decoded.second, dt.second)

    def test_parse_scaler_unit(self):
        # struct { int8, enum }
        # -2 (scaler), 27 (Wh)
        data = bytes([0x02, 0x02, 0x0F, 0xFE, 0x16, 0x1B])
        scaler, unit = parse_scaler_unit(data)
        self.assertEqual(scaler, -2)
        self.assertEqual(unit, "Wh")

    def test_format_value(self):
        self.assertEqual(format_value(2204, -1, "V"), "220.4 V")
        self.assertEqual(format_value(153420, -2, "Wh"), "1534.20 Wh")
        self.assertEqual(format_value(None), "N/A")


if __name__ == "__main__":
    unittest.main()
