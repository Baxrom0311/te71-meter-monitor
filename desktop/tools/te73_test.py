#!/usr/bin/env python3
"""
TE73 SP-1-3 autentifikatsiya testi
DIQQAT: 3 ta noto'g'ri parol = 24 SOAT BLOK!
"""
import sys, os, time
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dlms.hdlc import make_hdlc, send_recv, hex_str
from dlms.connection import DLMSConnection, _client_to_hdlc
from dlms.parser import parse_dlms_data

import serial.tools.list_ports as _lp
def _autoport():
    if len(sys.argv) > 1:
        return sys.argv[1]
    usb = [p.device for p in _lp.comports()
           if 'usb' in p.device.lower() or 'serial' in p.device.lower()]
    return usb[0] if usb else _lp.comports()[0].device

PORT = _autoport()
BAUD = 9600  # ESP32 bridge USB baud (RS485 = 4800 bridge ichida)

LLC = b"\xE6\xE6\x00"
OBIS_SERIAL = (0, 0, 96, 1, 0, 255)


def _read_serial(conn):
    raw = conn.get_attribute(1, OBIS_SERIAL, 2)
    if raw:
        val, _, _ = parse_dlms_data(raw)
        return str(val)
    return "o'qib bo'lmadi"


def _connect_low(conn, client_id, password):
    conn.client_addr = client_id
    conn.client_src = _client_to_hdlc(client_id)
    conn.auth_mode = "low"

    if not conn._snrm():
        print("  SNRM: javob yo'q")
        return False

    pwd_bytes = password.encode("ascii")
    body = (
        bytes([0xA1, 0x09, 0x06, 0x07, 0x60, 0x85, 0x74, 0x05, 0x08, 0x01, 0x01])
        + bytes([0x8A, 0x02, 0x07, 0x80])
        + bytes([0x8B, 0x07, 0x60, 0x85, 0x74, 0x05, 0x08, 0x02, 0x01])
        + bytes([0xAC, len(pwd_bytes) + 2, 0x80, len(pwd_bytes)]) + pwd_bytes
        + bytes([0xBE, 0x10, 0x04, 0x0E, 0x01, 0x00, 0x00, 0x00,
                 0x06, 0x5F, 0x1F, 0x04, 0x00, 0x00, 0x7E, 0x1F, 0x04, 0xB0])
    )
    aarq = bytes([0x60, len(body)]) + body
    return conn._finish_aarq(aarq)


def pause(seconds, msg=""):
    if msg:
        print(f"  {msg}")
    for i in range(seconds, 0, -1):
        print(f"  {i}... (Ctrl+C bilan to'xtatish mumkin)", flush=True)
        time.sleep(1)


def run_test(label, connect_fn, lockout_attempt=None):
    sep = "-" * 55
    print(f"\n{sep}")
    if lockout_attempt:
        print(f"[{lockout_attempt}/3-URINISH] {label}")
        pause(3, "Boshlayapti...")
    else:
        print(f"[XAVFSIZ] {label}")
    print(sep)

    conn = DLMSConnection(port=PORT, baud=BAUD)
    result = False
    try:
        conn.open()
        result = connect_fn(conn)
        if result:
            sn = _read_serial(conn)
            print(f"  >>> ULANDI! Seriya: {sn}")
            conn.disconnect()
        else:
            if lockout_attempt:
                print(f"  >>> RAD ETILDI (noto'g'ri parol?)")
            else:
                print(f"  >>> ULANMADI")
    except Exception as e:
        print(f"  >>> XATO: {e}")
    finally:
        conn.close()
        time.sleep(0.8)
    return result


if __name__ == "__main__":
    print("=" * 55)
    print("  TE73 SP-1-3  Autentifikatsiya Testi")
    print(f"  Port: {PORT}")
    print("  DIQQAT: Noto'g'ri 3 parol = 24 soat BLOK!")
    print("=" * 55)

    results = {}

    # ── 1. XAVFSIZ: Client 16 + NONE ────────────────────
    results["client16_none"] = run_test(
        "Client 16 + NONE (Public)",
        lambda c: c.connect_public()
    )

    # ── 2. XAVFSIZ: Client 1 + HLS5 ─────────────────────
    results["client1_hls5"] = run_test(
        "Client 1 + HLS5 (Rele, parolsiz)",
        lambda c: c.connect_reader()
    )

    # ── 3. LOCKOUT 1/3: Client 2 + LOW + 00000000 ───────
    results["client2_low_00"] = run_test(
        "Client 2 + LOW + '00000000'",
        lambda c: _connect_low(c, 2, "00000000"),
        lockout_attempt=1
    )

    # ── 4. LOCKOUT 2/3: Client 1 + LOW + 00000000 ───────
    if not results["client2_low_00"]:
        results["client1_low_00"] = run_test(
            "Client 1 + LOW + '00000000'",
            lambda c: _connect_low(c, 1, "00000000"),
            lockout_attempt=2
        )

        # ── 5. LOCKOUT 3/3: Client 1 + LOW + 11111111 ───
        if not results["client1_low_00"]:
            print("\n  !!! OXIRGI URINISH — keyin 24 soat kutish !!!")
            results["client1_low_11"] = run_test(
                "Client 1 + LOW + '11111111'",
                lambda c: _connect_low(c, 1, "11111111"),
                lockout_attempt=3
            )

    # ── YAKUNIY HISOBOT ──────────────────────────────────
    print("\n" + "=" * 55)
    print("  NATIJALAR")
    print("=" * 55)
    names = {
        "client16_none":  "Client 16 + NONE         ",
        "client1_hls5":   "Client 1  + HLS5         ",
        "client2_low_00": "Client 2  + LOW 00000000 ",
        "client1_low_00": "Client 1  + LOW 00000000 ",
        "client1_low_11": "Client 1  + LOW 11111111 ",
    }
    for key, lbl in names.items():
        if key not in results:
            continue
        v = results[key]
        status = "ISHLADI" if v else "ISHLAMADI"
        print(f"  {lbl}: {status}")
    print("=" * 55)
