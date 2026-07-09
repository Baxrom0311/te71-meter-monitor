#!/usr/bin/env python3
"""
CE 303 S31 — IEC 62056-21 Mode C Reader (ESP32 bridge orqali)

CE 303 DLMS emas, IEC 62056-21 ishlatadi:
  1. Client → /?!\r\n          (sign-on)
  2. Meter  → /ENE5CE303...\r\n (identification)
  3. Client → ACK + opt        (\x06 0 Z 0 \r\n — same baud)
  4. Meter  → \x01 P 0 \x02 data \x03 checksum

ESP32 bridge orqali: USB(8N1,9600) ↔ RS485(7E1,9600)

Ishlatish:
    python ce303_iec.py                        # auto-detect
    python ce303_iec.py /dev/cu.usbserial-110  # Mac
    python ce303_iec.py COM3                   # Windows
"""
import sys
import time
import serial
import serial.tools.list_ports

# ── BCC hisoblash (XOR) ────────────────────────────────────────────────────────
def calc_bcc(data: bytes) -> int:
    """IEC 62056-21 BCC: SOH dan ETX gacha (SOH kiritilmaydi) XOR."""
    bcc = 0
    for b in data:
        bcc ^= b
    return bcc & 0xFF

# ── Raw send/receive ───────────────────────────────────────────────────────────
def send_recv(ser: serial.Serial, data: bytes,
              timeout: float = 2.0,
              end_chars: bytes = b'\n') -> bytes:
    """Yuborish va javob kutish."""
    ser.reset_input_buffer()
    ser.write(data)

    resp = b""
    start = time.time()
    last_byte = time.time()

    while time.time() - start < timeout:
        if ser.in_waiting:
            chunk = ser.read(ser.in_waiting)
            resp += chunk
            last_byte = time.time()

            # End condition tekshirish
            for ec in end_chars:
                if ec in resp:
                    # Oxirgi baytdan keyin 100ms kutish (frame tugashi)
                    time.sleep(0.15)
                    if ser.in_waiting:
                        resp += ser.read(ser.in_waiting)
                    return resp
        else:
            # Ma'lumot kelib, 300ms pauza → tugadi
            if resp and (time.time() - last_byte) > 0.3:
                return resp
        time.sleep(0.02)

    return resp

def hex_str(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)

def printable(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else f"[{b:02X}]" for b in data)

# ── IEC 62056-21 sign-on ───────────────────────────────────────────────────────
def iec_sign_on(ser: serial.Serial) -> bytes | None:
    """/?!\r\n yuborish va meter ID ni olish."""
    msg = b"/?!\r\n"
    print(f"  TX: {msg!r}")
    resp = send_recv(ser, msg, timeout=3.0, end_chars=b'\n')
    if not resp:
        print("  RX: javob yo'q")
        return None
    print(f"  RX hex: {hex_str(resp)}")
    print(f"  RX txt: {printable(resp)}")
    return resp

# ── IEC 62056-21 ACK + readout ─────────────────────────────────────────────────
def iec_readout(ser: serial.Serial, baud_char: str = "0") -> bytes | None:
    """ACK yuborish (baud change: 0=keep, 5=9600→19200, 6=9600→38400)
    va ma'lumotlar to'plamini o'qish."""
    # ACK: \x06 + "0" + "Z" + baud_char + \r\n
    # Z: 0=normal readout, 1=programming mode
    ack = f"\x060Z{baud_char}\r\n".encode()
    print(f"  ACK TX: {hex_str(ack)} → {ack!r}")
    # readout response — ETX (0x03) + BCC ile tugaydi
    resp = send_recv(ser, ack, timeout=5.0, end_chars=b'\x03')
    if not resp:
        print("  Readout: javob yo'q")
        return None
    # BCC ni o'qish (ETX dan keyin 1 bayt)
    time.sleep(0.2)
    if ser.in_waiting:
        resp += ser.read(ser.in_waiting)
    print(f"  Readout ({len(resp)} bayt):")
    print(f"  HEX: {hex_str(resp)}")
    return resp

# ── Readout parsing ────────────────────────────────────────────────────────────
def parse_readout(data: bytes):
    """IEC 62056-21 data readout ni parse qilish.

    Format: \x01 P0 \x02 data_lines \x03 bcc
    data_lines: OBIS(value)\r\n  yoki   label(value)\r\n
    """
    try:
        text = data.decode("ascii", errors="replace")
    except Exception:
        text = repr(data)

    print("\n  ── Parsed Data ─────────────────────────────────────")

    # STX dan ETX gacha
    if "\x02" in text and "\x03" in text:
        start = text.index("\x02") + 1
        end   = text.index("\x03")
        payload = text[start:end]
        lines = [ln.strip() for ln in payload.splitlines() if ln.strip()]
        for line in lines:
            print(f"    {line}")
    else:
        # Raw matn ko'rinishi
        for line in text.splitlines():
            if line.strip():
                print(f"    {line}")

    print("  ───────────────────────────────────────────────────")

# ── Baud o'zgartirish ──────────────────────────────────────────────────────────
BAUD_CHARS = {
    "0": 300, "1": 600, "2": 1200, "3": 2400,
    "4": 4800, "5": 9600, "6": 19200
}

# ── Asosiy test ────────────────────────────────────────────────────────────────
def test_port(port: str):
    print(f"\n{'='*60}")
    print(f" CE 303 IEC 62056-21 Mode C Test")
    print(f" Port: {port}")
    print(f"{'='*60}")

    # Sinab ko'rish uchun baud ratelar
    test_bauds = [9600, 4800, 2400, 300]

    for baud in test_bauds:
        print(f"\n{'─'*50}")
        print(f" Baud: {baud}")
        print(f"{'─'*50}")

        try:
            ser = serial.Serial(
                port, baud,
                bytesize=8, parity='N', stopbits=1,
                timeout=3
            )
        except Exception as e:
            print(f" Port ochilmadi: {e}")
            continue

        try:
            time.sleep(0.3)

            # Sign-on
            print("\n [1] Sign-on /?!\\r\\n yuborilmoqda...")
            id_resp = iec_sign_on(ser)

            if id_resp and len(id_resp) >= 5:
                # Identification string tekshirish: /xxxYbaud...\r\n
                if id_resp[0:1] == b'/':
                    print(f"\n  ✓ Meter javob berdi!")
                    print(f"  Manufacturer: {id_resp[1:4].decode('ascii', errors='?')}")
                    if len(id_resp) >= 5:
                        bc = chr(id_resp[4])
                        print(f"  Baud ID: '{bc}' → {BAUD_CHARS.get(bc, '?')} baud")

                    # Readout so'rash
                    print("\n [2] Data readout so'ralmoqda...")
                    data = iec_readout(ser, baud_char="0")  # same baud keep
                    if data:
                        parse_readout(data)
                        ser.close()
                        return True
                    else:
                        # Programming mode sinash
                        print("\n [2b] Programming mode sinash (0Z1)...")
                        data = iec_readout(ser, baud_char="1")
                        if data:
                            parse_readout(data)
                            ser.close()
                            return True
                else:
                    print(f"  ~ Noto'g'ri format: {hex_str(id_resp[:8])}")

                    # Balki DLMS response?
                    if id_resp[0:1] == b'\x7E':
                        print("  → Bu DLMS HDLC frame! Meter DLMS ishlatayotgan bo'lishi mumkin.")
            else:
                print(f"  ✗ Javob yo'q yoki qisqa ({len(id_resp) if id_resp else 0} bayt)")

        except KeyboardInterrupt:
            print("\n  Bekor qilindi.")
            ser.close()
            return False
        except Exception as e:
            print(f"  Xato: {e}")
        finally:
            try:
                ser.close()
            except Exception:
                pass

    print(f"\n{'='*60}")
    print(" ✗ CE 303 javob bermadi.")
    print("\n Tekshirish:")
    print("   1. ESP32 bridge firmware yuklanganmi? (9600 8N1 USB, 9600 7E1 RS485)")
    print("   2. A/B simlar to'g'ri ulanganmi?")
    print("      CE 303 X9: Pin3=B, Pin4=A, Pin5=GND")
    print("      MAX485: A=A, B=B")
    print("   3. Simlar qayta ulanib tekshiring (A↔B almashtirib ko'ring)")
    print("   4. Metr 220V ga ulanganmi va ishlayaptimi?")
    print("   5. Serial monitor da bridge 'RS-485 BRIDGE tayyor' ni ko'rsatyaptimi?")
    print(f"{'='*60}\n")
    return False

# ── Raw mode — har qanday baytni yuborish va ko'rish ──────────────────────────
def raw_test(port: str, baud: int = 9600):
    """Raw diagnostika — har qanday yuboriladigan baytlarni test qilish."""
    print(f"\n{'='*60}")
    print(f" RAW Mode — {port} @ {baud}")
    print(f"{'='*60}")

    ser = serial.Serial(port, baud, bytesize=8, parity='N', stopbits=1, timeout=3)
    time.sleep(0.3)

    tests = [
        (b"/?!\r\n",          "IEC sign-on"),
        (b"/?\r\n",            "IEC sign-on (variant)"),
        (b"\x06\x30\x5A\x30\r\n", "IEC ACK (0Z0)"),
        (b"\x01R1\x02()\x03\x28", "IEC Read request"),
    ]

    for payload, label in tests:
        print(f"\n  [{label}]")
        print(f"  TX: {hex_str(payload)} → {payload!r}")
        ser.reset_input_buffer()
        ser.write(payload)
        time.sleep(1.5)
        resp = b""
        if ser.in_waiting:
            resp = ser.read(ser.in_waiting)
        print(f"  RX ({len(resp)} bayt): {hex_str(resp)}")
        if resp:
            print(f"  TXT: {printable(resp)}")
        time.sleep(0.5)

    ser.close()
    print()

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--raw":
        port = sys.argv[2] if len(sys.argv) > 2 else None
        baud = int(sys.argv[3]) if len(sys.argv) > 3 else 9600
        if not port:
            print("Usage: python ce303_iec.py --raw /dev/cu.usbserial-110 [baud]")
            sys.exit(1)
        raw_test(port, baud)
        sys.exit(0)

    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        port = sys.argv[1]
    else:
        ports = list(serial.tools.list_ports.comports())
        usb_ports = [p for p in ports
                     if "usb" in p.device.lower() or "serial" in p.device.lower()]
        if usb_ports:
            port = usb_ports[0].device
            print(f"Auto-detect: {port}")
        elif ports:
            port = ports[0].device
            print(f"Birinchi port: {port}")
        else:
            print("COM port topilmadi!")
            sys.exit(1)

    test_port(port)
