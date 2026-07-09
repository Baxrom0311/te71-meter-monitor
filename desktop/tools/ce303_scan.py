"""CE 303 S31 — DLMS/COSEM scanner va diagnostika.

Turli baud rate, server/client address kombinatsiyalarini sinaydi.
Topilgan kombinatsiya bilan asosiy o'lchov qiymatlarini o'qiydi.

Ishlatish:
    python ce303_scan.py                   # auto-detect COM port
    python ce303_scan.py COM3              # Windows
    python ce303_scan.py /dev/cu.usbserial-110  # Mac
"""
import sys
import struct
import time
import serial
import serial.tools.list_ports

# ── FCS16 ──────────────────────────────────────────────────────────────────────
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

# ── HDLC framing — 1-baytli address ───────────────────────────────────────────
def make_hdlc_1b(dest: int, src: int, ctrl: int, info: bytes = b"") -> bytes:
    """Standard 1-byte address HDLC frame."""
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

# ── HDLC framing — 2-baytli server address (CE 303 style) ────────────────────
def make_hdlc_2b(dest_upper: int, dest_lower: int, src: int,
                 ctrl: int, info: bytes = b"") -> bytes:
    """2-byte server address HDLC frame.
    dest_upper = (logical_addr << 1)        # MSB, last bit = 0
    dest_lower = (physical_addr << 1) | 1   # LSB, last bit = 1
    """
    header = bytes([dest_upper, dest_lower, src, ctrl])
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

def hex_str(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)

# ── Raw send/receive ───────────────────────────────────────────────────────────
def send_recv(ser: serial.Serial, frame: bytes, timeout: float = 2.5) -> bytes:
    ser.reset_input_buffer()
    ser.write(frame)
    time.sleep(0.3)
    data = b""
    start = time.time()
    while time.time() - start < timeout:
        if ser.in_waiting:
            data += ser.read(ser.in_waiting)
            if len(data) > 4 and data[-1] == 0x7E and data.count(0x7E) >= 2:
                break
        time.sleep(0.02)
    return data

# ── SNRM sinash ───────────────────────────────────────────────────────────────
def try_snrm_1b(ser, dest, src, label=""):
    frame = make_hdlc_1b(dest, src, 0x93)
    print(f"  TX [{label}]: {hex_str(frame)}")
    resp = send_recv(ser, frame, timeout=2.0)
    if resp:
        print(f"  RX: {hex_str(resp)}")
        # UA frame tekshirish (0x73 ctrl byte)
        if 0x73 in resp:
            print(f"  ✓ UA javob! SNRM muvaffaqiyatli!")
            return True
        else:
            print(f"  ~ Javob bor lekin UA emas")
            return False
    else:
        print(f"  ✗ Javob yo'q")
        return False

def try_snrm_2b(ser, dest_u, dest_l, src, label=""):
    frame = make_hdlc_2b(dest_u, dest_l, src, 0x93)
    print(f"  TX [{label}]: {hex_str(frame)}")
    resp = send_recv(ser, frame, timeout=2.0)
    if resp:
        print(f"  RX: {hex_str(resp)}")
        if 0x73 in resp:
            print(f"  ✓ UA javob! SNRM muvaffaqiyatli!")
            return True
        else:
            print(f"  ~ Javob bor lekin UA emas")
            return False
    else:
        print(f"  ✗ Javob yo'q")
        return False

# ── GET request — serial number o'qish ───────────────────────────────────────
def read_serial(ser, dest, src, is_2b=False, dest_u=None, dest_l=None):
    """AARQ + GET serial number (OBIS 0.0.96.1.0.255, class 1, attr 2)."""
    # Public AARQ (no auth)
    aarq_body = bytes([
        0xA1, 0x09, 0x06, 0x07, 0x60, 0x85, 0x74, 0x05, 0x08, 0x01, 0x01,
        0xBE, 0x10, 0x04, 0x0E,
        0x01, 0x00, 0x00, 0x00, 0x06, 0x5F, 0x1F, 0x04,
        0x00, 0x00, 0x7E, 0x1F, 0x04, 0xB0
    ])
    aarq = bytes([0x60, len(aarq_body)]) + aarq_body
    info = b"\xE6\xE6\x00" + aarq  # LLC + AARQ

    if is_2b:
        frame = make_hdlc_2b(dest_u, dest_l, src, 0x10, info)
    else:
        frame = make_hdlc_1b(dest, src, 0x10, info)

    print(f"    AARQ TX: {hex_str(frame[:20])}...")
    resp = send_recv(ser, frame, timeout=3.0)
    if not resp:
        print("    AARQ: javob yo'q")
        return False
    print(f"    AARQ RX: {hex_str(resp[:30])}...")

    # AARE muvaffaqiyat tekshirish (0x61 = AARE tag)
    if 0x61 not in resp:
        print("    AARE topilmadi — auth xato yoki mos kelmagan parametr")
        return False
    print("    ✓ AARE qabul qilindi — ulanish ochildi!")

    # I-frame GET request — serial (0.0.96.1.0.255, class_id=1, attr=2)
    obis = bytes([0x00, 0x00, 0x60, 0x01, 0x00, 0xFF])
    get_req = bytes([
        0xC0, 0x01, 0xC1,        # GET.request, normal, invoke_id
        0x00, 0x01,              # class_id = 1 (Data)
    ]) + obis + bytes([0x02, 0x00])  # attr=2, no access selection

    info2 = b"\xE6\xE7\x00" + get_req
    if is_2b:
        frame2 = make_hdlc_2b(dest_u, dest_l, src, 0x10, info2)
    else:
        frame2 = make_hdlc_1b(dest, src, 0x10, info2)

    print(f"    GET TX: {hex_str(frame2[:20])}...")
    resp2 = send_recv(ser, frame2, timeout=3.0)
    if not resp2:
        print("    GET: javob yo'q")
        return False
    print(f"    GET RX: {hex_str(resp2)}")

    # Ma'lumotni ochib ko'rish (raw ASCII/hex)
    try:
        # 0xC4 = GET.response tag
        if 0xC4 in resp2:
            idx = resp2.index(0xC4)
            payload = resp2[idx:]
            print(f"    GET response payload: {hex_str(payload)}")
            # ASCII yoki visible bytes ni qidirish
            printable = bytes(b for b in payload if 32 <= b < 127)
            if printable:
                print(f"    >>> Matn: {printable.decode('ascii', errors='replace')}")
    except Exception as e:
        print(f"    Parse xato: {e}")

    return True

# ── DISC yuborish ──────────────────────────────────────────────────────────────
def send_disc(ser, dest, src, is_2b=False, dest_u=None, dest_l=None):
    if is_2b:
        frame = make_hdlc_2b(dest_u, dest_l, src, 0x53)
    else:
        frame = make_hdlc_1b(dest, src, 0x53)
    send_recv(ser, frame, timeout=1.0)

# ── Asosiy scan ───────────────────────────────────────────────────────────────
def scan(port: str):
    print(f"\n{'='*60}")
    print(f" CE 303 S31 — DLMS Scanner")
    print(f" Port: {port}")
    print(f"{'='*60}\n")

    # Sinash kombinatsiyalari
    BAUDS = [9600, 4800, 2400]

    # 1-baytli server addresslar: (dest_byte, label)
    SERVER_1B = [
        (0x03, "server=1 (1-byte)"),    # phys_addr=1: (1<<1)|1=3
        (0x01, "server=0 (1-byte)"),    # phys_addr=0: (0<<1)|1=1
        (0x21, "server=16 (1-byte)"),
        (0x43, "server=33 (1-byte)"),
        (0x41, "server=32 (1-byte)"),
        (0xFF, "broadcast (1-byte)"),
    ]

    # 2-baytli server addresslar: (upper, lower, label)
    SERVER_2B = [
        (0x00, 0x01, "log=0,phys=0 (2-byte)"),   # logical=0, physical=0
        (0x00, 0x03, "log=0,phys=1 (2-byte)"),   # logical=0, physical=1
        (0x02, 0x01, "log=1,phys=0 (2-byte)"),   # logical=1, physical=0
        (0x02, 0x03, "log=1,phys=1 (2-byte)"),   # logical=1, physical=1
        (0x04, 0x01, "log=2,phys=0 (2-byte)"),
    ]

    # Client addresslar: (src_byte, label)
    CLIENTS = [
        (0x21, "client=16 (public)"),
        (0x41, "client=32"),
        (0x61, "client=48"),
        (0x03, "client=1"),
    ]

    found = []

    for baud in BAUDS:
        print(f"\n{'─'*50}")
        print(f" Baud rate: {baud}")
        print(f"{'─'*50}")

        try:
            ser = serial.Serial(port, baud, bytesize=8, parity='N',
                                stopbits=1, timeout=3)
            time.sleep(0.3)
        except Exception as e:
            print(f"  Port ochilmadi: {e}")
            continue

        try:
            for src_byte, client_label in CLIENTS:
                print(f"\n  Client: {client_label}")

                # 1-baytli server addresslar
                for dest, srv_label in SERVER_1B:
                    label = f"baud={baud}, {srv_label}, {client_label}"
                    ok = try_snrm_1b(ser, dest, src_byte, label=f"{srv_label}+{client_label}")
                    if ok:
                        print(f"\n  ★ TOPILDI! {label}")
                        # Serial raqam o'qishga urinish
                        print("  → Serial raqam o'qilmoqda...")
                        read_serial(ser, dest, src_byte)
                        send_disc(ser, dest, src_byte)
                        found.append({
                            'baud': baud, 'type': '1b',
                            'dest': dest, 'src': src_byte,
                            'label': label
                        })
                        time.sleep(0.5)

                # 2-baytli server addresslar
                for du, dl, srv_label in SERVER_2B:
                    label = f"baud={baud}, {srv_label}, {client_label}"
                    ok = try_snrm_2b(ser, du, dl, src_byte,
                                     label=f"{srv_label}+{client_label}")
                    if ok:
                        print(f"\n  ★ TOPILDI! {label}")
                        print("  → Serial raqam o'qilmoqda...")
                        read_serial(ser, None, src_byte, is_2b=True,
                                    dest_u=du, dest_l=dl)
                        send_disc(ser, None, src_byte, is_2b=True,
                                  dest_u=du, dest_l=dl)
                        found.append({
                            'baud': baud, 'type': '2b',
                            'dest_u': du, 'dest_l': dl, 'src': src_byte,
                            'label': label
                        })
                        time.sleep(0.5)

        finally:
            ser.close()

    # Natija
    print(f"\n{'='*60}")
    if found:
        print(f" ✓ {len(found)} ta kombinatsiya ishladi:")
        for f in found:
            print(f"   → {f['label']}")
    else:
        print(" ✗ Hech qanday kombinatsiya ishlamadi.")
        print("\n Tekshirish:")
        print("   1. A va B simlar to'g'ri ulanganmi? (teskari bo'lishi mumkin)")
        print("   2. DE/RE pin (GPIO4) to'g'ri ishlayaptimi?")
        print("   3. Metrda RS-485 interfeysi yoqilganmi?")
        print("   4. Voltage divider (10kΩ/20kΩ) to'g'rimi?")
    print(f"{'='*60}\n")

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        # Auto-detect
        ports = list(serial.tools.list_ports.comports())
        usb_ports = [p for p in ports if "usb" in p.device.lower()
                     or "USB" in p.description or "serial" in p.device.lower()]
        if usb_ports:
            port = usb_ports[0].device
            print(f"Auto-detect: {port} ({usb_ports[0].description})")
        elif ports:
            port = ports[0].device
            print(f"Birinchi port: {port}")
        else:
            print("Hech qanday COM port topilmadi!")
            sys.exit(1)

    scan(port)
