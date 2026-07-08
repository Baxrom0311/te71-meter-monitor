#!/usr/bin/env python3
"""
TE73 fizik ulanish diagnostikasi.
Parity, baud va RTS testlari.
XAVFSIZ: lockout yo'q.
"""
import sys, os, time, struct
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

import serial
from dlms.hdlc import fcs16, make_hdlc

import serial.tools.list_ports as _lp
PORT = sys.argv[1] if len(sys.argv) > 1 else next(
    (p.device for p in _lp.comports()
     if 'usb' in p.device.lower() or 'serial' in p.device.lower()),
    _lp.comports()[0].device if _lp.comports() else "COM1"
)

# SNRM frame (Client 16 -> Server 1)
SNRM = make_hdlc(0x03, 0x21, 0x93)
# Wakeup bytes (ba'zi hisoblagichlar talab qiladi)
WAKEUP = bytes([0x55] * 20)


def test_raw(port, baud, parity, rts_ctrl=False):
    tag = f"{baud} 8{parity}1"
    try:
        ser = serial.Serial(port, baud, bytesize=8, parity=parity,
                            stopbits=1, timeout=1.5)
        time.sleep(0.2)

        if rts_ctrl:
            ser.rts = True
            time.sleep(0.05)

        ser.reset_input_buffer()
        ser.write(SNRM)
        ser.flush()

        if rts_ctrl:
            time.sleep(0.01)
            ser.rts = False

        time.sleep(0.3)
        resp = ser.read(64)
        ser.close()

        if resp:
            return f"JAVOB ({len(resp)} bayt): {resp.hex()}"
        return "javob yoq"
    except Exception as e:
        return f"XATO: {e}"


def test_wakeup(port, baud, parity):
    """Wakeup + SNRM."""
    tag = f"wakeup+{baud} 8{parity}1"
    try:
        ser = serial.Serial(port, baud, bytesize=8, parity=parity,
                            stopbits=1, timeout=2.0)
        time.sleep(0.2)
        ser.reset_input_buffer()
        # Wakeup
        ser.write(WAKEUP)
        ser.flush()
        time.sleep(0.5)
        ser.reset_input_buffer()
        # SNRM
        ser.write(SNRM)
        ser.flush()
        time.sleep(0.5)
        resp = ser.read(128)
        ser.close()
        if resp:
            return f"JAVOB: {resp.hex()}"
        return "javob yoq"
    except Exception as e:
        return f"XATO: {e}"


def loopback_test(port, baud):
    """Adapter o'zi o'qiydimi (loopback)."""
    try:
        ser = serial.Serial(port, baud, bytesize=8, parity='N',
                            stopbits=1, timeout=0.5)
        time.sleep(0.1)
        ser.reset_input_buffer()
        test_data = bytes([0xAA, 0x55, 0x7E])
        ser.write(test_data)
        ser.flush()
        time.sleep(0.2)
        echo = ser.read(10)
        ser.close()
        if echo == test_data:
            return "LOOPBACK bor (adapter o'z-o'zini eshitadi)"
        elif echo:
            return f"Qisman echo: {echo.hex()}"
        return "Loopback yo'q (normal holat)"
    except Exception as e:
        return f"XATO: {e}"


if __name__ == "__main__":
    print("=" * 60)
    print(f"  TE73 Diagnostika  |  Port: {PORT}")
    print("=" * 60)

    print("\n[1] Loopback tekshirish (adapter ishlayaptimi?)")
    r = loopback_test(PORT, 9600)
    print(f"  -> {r}")

    print("\n[2] Parity + Baud sinovlari")
    combos = [
        (9600, 'N'),
        (9600, 'E'),
        (9600, 'O'),
        (4800, 'N'),
        (4800, 'E'),
        (1200, 'E'),
        (1200, 'N'),
        (19200, 'N'),
        (19200, 'E'),
    ]
    for baud, par in combos:
        r = test_raw(PORT, baud, par)
        print(f"  {baud} 8{par}1: {r}")
        time.sleep(0.3)

    print("\n[3] RTS boshqaruvli test (9600 8N1 va 8E1)")
    for par in ['N', 'E']:
        r = test_raw(PORT, 9600, par, rts_ctrl=True)
        print(f"  9600 8{par}1 RTS: {r}")
        time.sleep(0.3)

    print("\n[4] Wakeup + SNRM (9600 8E1)")
    r = test_wakeup(PORT, 9600, 'E')
    print(f"  -> {r}")

    print("\n" + "=" * 60)
    print("  SNRM frame (yuborilayotgan):")
    print(f"  {SNRM.hex()}")
    print("=" * 60)
    print("\nAgar hammasi 'javob yoq' bo'lsa:")
    print("  1. A va B simlarini almashtiring (teskari ulash)")
    print("  2. GND ulanganligini tekshiring")
    print("  3. Hisoblagich quvvat olayaptimi? (display yonganmi?)")
