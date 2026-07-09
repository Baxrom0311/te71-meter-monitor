#!/usr/bin/env python3
"""
TE73 server address + baud rate scanner.
XAVFSIZ: faqat SNRM yuboradi, autentifikatsiya yo'q, lockout yo'q.
"""
import sys, os, time
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import serial
from dlms.hdlc import fcs16

import serial.tools.list_ports as _lp
PORT = sys.argv[1] if len(sys.argv) > 1 else next(
    (p.device for p in _lp.comports()
     if 'usb' in p.device.lower() or 'serial' in p.device.lower()),
    _lp.comports()[0].device if _lp.comports() else "COM1"
)

# ESP32 bridge orqali: USB har doim 9600 8N1
# RS485 baud bridge ichida = 4800 (firmwarega bog'liq)
BAUDS = [9600]  # Bridge USB baud (RS485 = 4800 bridge ichida)

# Server address sinash qiymatlari (HDLC raw byte)
# Logical addr N -> HDLC byte = (N << 1) | 1
SERVER_CANDIDATES = [
    (0x03, "server=1"),
    (0x01, "server=0"),
    (0x05, "server=2"),
    (0x11, "server=8/17raw"),
    (0x21, "server=16"),
    (0x23, "server=17"),
    (0x41, "server=32"),
    (0x81, "server=64"),
    (0xFF, "server=127"),
]

# Client 16 (public) src = (16<<1)|1 = 0x21
CLIENT_PUBLIC_SRC = 0x21


def build_snrm(server_addr_byte: int) -> bytes:
    """SNRM frame with given server address byte."""
    addr = bytes([server_addr_byte, CLIENT_PUBLIC_SRC])
    ctrl = bytes([0x93])  # SNRM
    content = addr + ctrl
    fc = fcs16(content)
    length = len(content) + 4  # 2 flag + 2 FCS
    frame = (
        b"\x7e"
        + bytes([0xa0 | (length >> 8), length & 0xff])
        + content
        + bytes([fc & 0xff, (fc >> 8) & 0xff])
        + b"\x7e"
    )
    return frame


def try_snrm(port: str, baud: int, server_byte: int) -> bytes:
    try:
        ser = serial.Serial(port, baud, bytesize=8, parity='N', stopbits=1, timeout=1.5)
        time.sleep(0.15)
        frame = build_snrm(server_byte)
        ser.reset_input_buffer()
        ser.write(frame)
        ser.flush()
        time.sleep(0.1)
        resp = ser.read(64)
        ser.close()
        return resp
    except Exception as e:
        return b""


if __name__ == "__main__":
    print("=" * 60)
    print(f"  TE73 Server Address Scanner  |  Port: {PORT}")
    print("  XAVFSIZ: SNRM only, lockout yo'q")
    print("=" * 60)

    found = []

    for baud in BAUDS:
        print(f"\n--- Baud: {baud} ---")
        for srv_byte, srv_label in SERVER_CANDIDATES:
            resp = try_snrm(PORT, baud, srv_byte)
            if resp and len(resp) > 4 and b"\x7e" in resp:
                print(f"  [{baud}] {srv_label} (0x{srv_byte:02X}): JAVOB! -> {resp.hex()}")
                found.append((baud, srv_byte, srv_label))
            else:
                print(f"  [{baud}] {srv_label} (0x{srv_byte:02X}): yo'q")
            time.sleep(0.2)

    print("\n" + "=" * 60)
    if found:
        print("  TOPILDI:")
        for baud, srv, lbl in found:
            print(f"    baud={baud}, {lbl} (0x{srv:02X})")
    else:
        print("  Hech qanday javob kelmadi.")
        print("  RS-485 kabelini tekshiring yoki hisoblagich holatini.")
    print("=" * 60)
