"""Unit tests for HDLC framing and checksum calculation.

Run with: python3 -m unittest desktop/tests/test_hdlc.py
"""
import unittest
import sys
import os

# Add desktop to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dlms.hdlc import fcs16, make_hdlc, hex_str


class TestDLMSHdlc(unittest.TestCase):

    def test_fcs16_checksum(self):
        # Empty checksum should be 0xFFFF (then inverted to 0x0000)
        self.assertEqual(fcs16(b""), 0)

        # Standard known sequence (from HDLC specifications or simple values)
        data = b"\xA0\x0A\x03\x21\x93"
        chk = fcs16(data)
        # Verify it's a 16-bit unsigned integer
        self.assertTrue(0 <= chk <= 0xFFFF)

    def test_make_hdlc_without_info(self):
        # Frame without info field (e.g. SNRM or DISC)
        # dest=0x03, src=0x21, ctrl=0x93
        frame = make_hdlc(0x03, 0x21, 0x93)
        self.assertEqual(frame[0], 0x7E)
        self.assertEqual(frame[-1], 0x7E)
        # Length without info should be: 1 (7E) + 2 (len/fmt) + 3 (header) + 2 (FCS) + 1 (7E) = 9 bytes
        self.assertEqual(len(frame), 9)

    def test_make_hdlc_with_info(self):
        # Frame with info field (e.g. AARQ or GET)
        info = b"\x01\x02\x03"
        frame = make_hdlc(0x03, 0x21, 0x54, info)
        self.assertEqual(frame[0], 0x7E)
        self.assertEqual(frame[-1], 0x7E)
        # Header checksum (HCS) should be present before info field
        # Length: 1 (7E) + 2 (len/fmt) + 3 (header) + 2 (HCS) + 3 (info) + 2 (FCS) + 1 (7E) = 14 bytes
        self.assertEqual(len(frame), 14)

    def test_hex_str(self):
        self.assertEqual(hex_str(b"\x01\x0A\xFF"), "01 0A FF")


if __name__ == "__main__":
    unittest.main()
