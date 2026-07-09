#!/usr/bin/env python3
"""
CE303 RS485 Debug Tool — to'liq diagnostika

Muammo: CE303 RS485 dan javob yo'q
Tekshirish: har bir qadam da raw baytlarni ko'rsatish

Ishlatish:
    python3 ce303_debug.py /dev/cu.usbserial-110
"""
import sys
import time
import serial
import serial.tools.list_ports

def hx(data: bytes) -> str:
    if not data:
        return "(bo'sh)"
    return data.hex(' ').upper() + f"  [{len(data)} bayt]"

def txt(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else f"[{b:02X}]" for b in data)

def bcc_sum(data: bytes) -> int:
    """Energomera BCC: arifmetik summa & 0xFF"""
    return sum(data) & 0xFF

def wait_bytes(ser: serial.Serial, timeout: float = 3.0, extra_ms: int = 300) -> bytes:
    """Timeout gacha barcha baytlarni o'qish, raw holda."""
    buf = b""
    start = time.time()
    last_byte = time.time()
    while time.time() - start < timeout:
        if ser.in_waiting:
            chunk = ser.read(ser.in_waiting)
            buf += chunk
            last_byte = time.time()
        elif buf and (time.time() - last_byte) > extra_ms / 1000:
            break
        time.sleep(0.01)
    return buf

def send_cmd(ser: serial.Serial, data: bytes, label: str,
             timeout: float = 3.0, extra_ms: int = 300) -> bytes:
    print(f"\n  → TX [{label}]:")
    print(f"     HEX: {hx(data)}")
    print(f"     TXT: {txt(data)!r}")
    ser.reset_input_buffer()
    ser.write(data)
    resp = wait_bytes(ser, timeout=timeout, extra_ms=extra_ms)
    print(f"  ← RX [{label}]:")
    print(f"     HEX: {hx(resp)}")
    if resp:
        resp_clean = bytes(b for b in resp if b != 0)
        print(f"     TXT: {txt(resp)!r}")
        if resp_clean != resp:
            print(f"     (null filtrsiz): {txt(resp_clean)!r}")
    else:
        print(f"     *** JAVOB YO'Q ***")
    return resp

def bridge_cmd(ser: serial.Serial, cmd: str) -> bytes:
    """ESP32 bridge buyrug'i."""
    data = cmd.encode()
    ser.reset_input_buffer()
    ser.write(data)
    time.sleep(0.6)
    resp = b""
    while ser.in_waiting:
        resp += ser.read(ser.in_waiting)
        time.sleep(0.05)
    ok = "OK:" in resp.decode("ascii", errors="?") or "BAUD:" in resp.decode("ascii", errors="?")
    print(f"     Bridge {cmd}: {'✓' if ok else '?'} → {hx(resp)}")
    return resp

def test1_basic_9600(ser: serial.Serial):
    """Test 1: 9600 baud, sign-on, to'g'ri protokol."""
    print("\n" + "="*60)
    print("TEST 1: 9600 baud Sign-on (to'g'ri protokol)")
    print("="*60)

    print("\n[1.1] RS485 = 9600 baud (CE303 RS485 har doim 9600)")
    bridge_cmd(ser, "~B9600~")
    time.sleep(0.5)

    print("\n[1.2] Sign-on: /?!\\r\\n (broadcast)")
    resp = send_cmd(ser, b"/?!\r\n", "sign-on", timeout=4.0, extra_ms=500)
    if resp and bytes(b for b in resp if b != 0):
        print("  *** JAVOB BOR! Metr ishlayapti! ***")
        return True

    print("\n[1.3] Sign-on bilan address (agar metr broadcast qabul qilmasa)")
    # Ba'zi CE303 lar manufacturer kodi bilan javob beradi
    resp = send_cmd(ser, b"/?EKT!\r\n", "sign-on +MFR", timeout=4.0, extra_ms=500)
    if resp and bytes(b for b in resp if b != 0):
        print("  *** JAVOB BOR! /EKT sign-on ishladi! ***")
        return True

    return False

def test2_long_timeout(ser: serial.Serial):
    """Test 2: Katta timeout bilan — metr sekin javob berishi mumkin."""
    print("\n" + "="*60)
    print("TEST 2: Katta timeout (8 soniya)")
    print("="*60)

    bridge_cmd(ser, "~B9600~")
    time.sleep(0.5)

    print("\n[2.1] /?!\\r\\n → 8 soniya kutish")
    ser.reset_input_buffer()
    ser.write(b"/?!\r\n")
    print("  Yuborildi, 8 soniya kutilmoqda...")
    resp = b""
    start = time.time()
    while time.time() - start < 8:
        if ser.in_waiting:
            chunk = ser.read(ser.in_waiting)
            resp += chunk
            now = time.time() - start
            print(f"  t={now:.2f}s: +{len(chunk)} bayt: {hx(chunk)}")
        time.sleep(0.05)
    if not resp:
        print("  *** 8 soniyada hech narsa kelmadi ***")
    return bool(resp and bytes(b for b in resp if b != 0))

def test3_raw_bytes(ser: serial.Serial):
    """Test 3: Individual baytlarni yuborish — metr echo qilishi mumkin."""
    print("\n" + "="*60)
    print("TEST 3: Raw baytlar — har birini alohida yuborish")
    print("="*60)

    bridge_cmd(ser, "~B9600~")
    time.sleep(0.5)

    # Har bir baytni alohida yuboring, echo ni kuting
    for b_val in [0x2F, 0x3F, 0x21, 0x0D, 0x0A]:
        ser.write(bytes([b_val]))
        time.sleep(0.1)
        resp = b""
        while ser.in_waiting:
            resp += ser.read(ser.in_waiting)
        print(f"  TX: {b_val:02X} → RX: {hx(resp)}")

def test4_300baud(ser: serial.Serial):
    """Test 4: 300 baud sinash (optik port ham bo'lishi mumkin)."""
    print("\n" + "="*60)
    print("TEST 4: 300 baud (optik port yoki RS485 boshqacha)")
    print("="*60)

    bridge_cmd(ser, "~B300~")
    time.sleep(0.5)

    print("\n[4.1] /?!\\r\\n at 300 baud (5 soniya)")
    ser.reset_input_buffer()
    ser.write(b"/?!\r\n")
    resp = b""
    start = time.time()
    while time.time() - start < 5:
        if ser.in_waiting:
            chunk = ser.read(ser.in_waiting)
            resp += chunk
            now = time.time() - start
            print(f"  t={now:.2f}s: +{len(chunk)} bayt: {hx(chunk)}")
        time.sleep(0.05)
    if not resp:
        print("  *** 5 soniyada javob yo'q ***")

    bridge_cmd(ser, "~B9600~")

def test5_loopback(ser: serial.Serial):
    """Test 5: ESP32 UART2 loopback — hardware tekshirish."""
    print("\n" + "="*60)
    print("TEST 5: ESP32 UART2 Loopback testi")
    print("="*60)
    resp = send_cmd(ser, b"~STEST~", "loopback", timeout=2.0, extra_ms=200)
    if b"OK" in resp:
        print("  ✓ ESP32 UART2 ishlayapti")
    else:
        print("  ✗ UART2 muammo bor!")

def test6_fast_read(ser: serial.Serial):
    """Test 6: Tezkor o'qish format (sign-on + request kombinatsiya)."""
    print("\n" + "="*60)
    print("TEST 6: Fast-read format (IEC 62056-21 short notification)")
    print("="*60)

    bridge_cmd(ser, "~B9600~")
    time.sleep(0.5)

    # Format: /?!\x01R1\x02PARAM()\x03BCC
    for param in [b"VOLTA", b"SNUMB", b"ET0PE"]:
        payload = param + b"()"
        body = b"\x01R1\x02" + payload + b"\x03"
        crc = bcc_sum(b"R1\x02" + payload + b"\x03")
        frame = b"/?!" + body + bytes([crc])
        resp = send_cmd(ser, frame, f"fast-read {param.decode()}", timeout=3.0, extra_ms=400)
        if resp and bytes(b for b in resp if b != 0):
            print(f"  *** JAVOB: {param.decode()} ***")
        time.sleep(0.5)

def test7_full_handshake(ser: serial.Serial):
    """Test 7: To'liq IEC 62056-21 handshake (9600 baud)."""
    print("\n" + "="*60)
    print("TEST 7: To'liq IEC 62056-21 Mode C Handshake")
    print("="*60)

    bridge_cmd(ser, "~B9600~")
    time.sleep(0.5)

    # Step 1: Sign-on
    print("\n[7.1] Sign-on")
    ser.reset_input_buffer()
    ser.write(b"/?!\r\n")
    time.sleep(0.5)
    resp = wait_bytes(ser, timeout=4.0, extra_ms=500)
    print(f"  RX: {hx(resp)}")
    print(f"  TXT: {txt(resp)!r}")

    if not resp or not bytes(b for b in resp if b != 0):
        print("  ✗ Sign-on javob yo'q, test 7 to'xtatildi")
        return

    # Step 2: ACK — same baud (baud_char = '5' for 9600)
    print("\n[7.2] ACK yuborish (\\x06 0 5 0 \\r\\n)")
    ack = b"\x060Z0\r\n"  # Z=0 = data readout mode, same baud
    ser.reset_input_buffer()
    ser.write(ack)
    time.sleep(0.2)
    resp2 = wait_bytes(ser, timeout=5.0, extra_ms=500)
    print(f"  RX: {hx(resp2)}")
    print(f"  TXT: {txt(resp2)!r}")

    if resp2 and bytes(b for b in resp2 if b != 0):
        print("  *** DATA DUMP QABUL QILINDI! ***")

def main():
    port = None
    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        ports = list(serial.tools.list_ports.comports())
        usb = [p for p in ports if "usb" in p.device.lower() or "serial" in p.device.lower()]
        port = usb[0].device if usb else (ports[0].device if ports else None)
        if port:
            print(f"Auto-detect: {port}")

    if not port:
        print("Port topilmadi!"); sys.exit(1)

    print(f"\n{'='*60}")
    print(f" CE303 RS485 Debug — {port}")
    print(f"{'='*60}")

    ser = serial.Serial(port, 9600, bytesize=8, parity='N', stopbits=1, timeout=3)
    time.sleep(0.5)

    try:
        test5_loopback(ser)           # ESP32 hardware check
        time.sleep(0.5)

        found = test1_basic_9600(ser) # 9600 baud sign-on
        if not found:
            test2_long_timeout(ser)   # Longer wait
            test6_fast_read(ser)      # Fast-read format
            test7_full_handshake(ser) # Full 3-step handshake
            test3_raw_bytes(ser)      # Raw bytes
            test4_300baud(ser)        # 300 baud (just in case)

        print("\n" + "="*60)
        print(" Diagnostika tugadi.")
        print("\n Agar hamma testlar 0x00 yoki bo'sh qaytarsa:")
        print("   1. MAX485 VCC voltaj tekshiring (5V bo'lishi kerak)")
        print("   2. MAX485 RO → ESP32 GPIO16 ulangan-ullanmaganligini tekshiring")
        print("   3. CE303 X19 connector pinlarini qayta tekshiring:")
        print("      Pin3=B, Pin4=A, Pin5=GND")
        print("   4. MAX485 A va B dan voltaj o'lchang (bitta tomondan):")
        print("      A-GND: ~2.5-3V (idle), B-GND: ~2.0-2.5V")
        print("   5. CE303 220V dan quvvat olayaptimi?")
        print(f"{'='*60}\n")

    finally:
        ser.close()

if __name__ == "__main__":
    main()
