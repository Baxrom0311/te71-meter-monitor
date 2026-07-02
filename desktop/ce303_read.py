#!/usr/bin/env python3
"""
CE 303 S31 — IEC 62056-21 Mode C Reader
ESP32 Smart Bridge orqali

Protokol ketma-ketligi:
  1. RS485 = 300 baud 7E1
  2. /?!\r\n yuborish (sign-on)
  3. /EKT5\r\n javob → 5 = 9600 baud kodi
  4. \x06 0 5 1 \r\n ACK (9600 da qolish)
  5. RS485 = 9600 baud 7E1
  6. Data so'rovlar: VOLTA(), CURRE(), ...

BCC = arifmetik summa & 0xFF

Ishlatish:
    python3 ce303_read.py /dev/cu.usbserial-110
    python3 ce303_read.py /dev/cu.usbserial-110 --addr 123456789
"""
import sys, time, re, serial, serial.tools.list_ports

USB_PORT = '/dev/cu.usbserial-110'
USB_BAUD = 9600

PARAMS = [
    ('SNUMB', 'Serial raqam'),
    ('VOLTA', 'Kuchlanish L1/L2/L3 (V)'),
    ('CURRE', 'Tok L1/L2/L3 (A)'),
    ('POWEP', 'Aktiv quvvat jami (kW)'),
    ('POWPP', 'Aktiv quvvat L1/L2/L3 (kW)'),
    ('FREQU', 'Chastota (Hz)'),
    ('COS_f', 'Cos φ'),
    ('ET0PE', 'Energiya jami/T1..T5 (kWh)'),
    ('TIME_', 'Vaqt'),
    ('DATE_', 'Sana'),
]

# ── BCC: arifmetik summa & 0xFF (Energomera standarti) ───────────────────────
def bcc(data: bytes) -> int:
    return sum(data) & 0xFF

# ── IEC so'rov yasash ─────────────────────────────────────────────────────────
def make_req(param: str, addr: str = '') -> bytes:
    """/?[addr]!\x01R1\x02PARAM()\x03BCC"""
    payload = f'{param}()'.encode()
    body    = b'\x01R1\x02' + payload + b'\x03'
    crc     = bcc(b'R1\x02' + payload + b'\x03')
    return f'/?{addr}!'.encode() + body + bytes([crc])

# ── Javobdan qiymatlar ────────────────────────────────────────────────────────
def parse_vals(data: bytes) -> list[str]:
    text = data.decode('ascii', errors='replace')
    return re.findall(r'\(([^)]*)\)', text)

# ── Yuborish va javob kutish ──────────────────────────────────────────────────
def send_recv(ser: serial.Serial, frame: bytes,
              timeout: float = 3.0, min_wait: float = 0.0) -> bytes:
    ser.reset_input_buffer()
    ser.write(frame)
    if min_wait:
        time.sleep(min_wait)
    resp = b''
    start = time.time()
    last  = time.time()
    while time.time() - start < timeout:
        if ser.in_waiting:
            resp += ser.read(ser.in_waiting)
            last  = time.time()
        elif resp and (time.time() - last) > 0.4:
            break
        time.sleep(0.02)
    return resp

def hs(d: bytes) -> str:
    return d.hex(' ').upper() if d else '—'

# ── Bridge baud o'zgartirish ──────────────────────────────────────────────────
def bridge_set_baud(ser: serial.Serial, baud: int) -> bool:
    """ESP32 bridge ga RS485 baud ni o'zgartirishni buyurish."""
    cmd = f'~B{baud}~'.encode()
    ser.reset_input_buffer()
    ser.write(cmd)
    time.sleep(0.5)
    resp = b''
    while ser.in_waiting:
        resp += ser.read(ser.in_waiting)
        time.sleep(0.05)
    ok = f'OK:BAUD:{baud}'.encode() in resp
    print(f'  Bridge BAUD {baud}: {"✓" if ok else "? "+hs(resp)}')
    return ok

# ── IEC 62056-21 Session ──────────────────────────────────────────────────────
def iec_connect(ser: serial.Serial, addr: str = '') -> bool:
    """
    IEC 62056-21 Mode C ulanish:
      1. RS485 → 300 baud
      2. /?!\r\n → /EKTx\r\n
      3. \x06 0 5 1 \r\n → baud 9600 tasdiq
      4. RS485 → 9600 baud
    """
    print('\n── IEC 62056-21 Ulanish ─────────────────────────────')

    # 1. RS485 → 300 baud
    print('[1] RS485 → 300 baud ...')
    bridge_set_baud(ser, 300)
    time.sleep(0.3)

    # 2. Sign-on
    signon = f'/?{addr}!\r\n'.encode()
    print(f'[2] Sign-on: {signon!r}')
    resp = send_recv(ser, signon, timeout=4.0, min_wait=0.5)

    if not resp:
        print('    ✗ Javob yo\'q (300 baud da ham ishlamadi)')
        return False

    # null baytlarni filtrlash
    resp_clean = bytes(b for b in resp if b != 0x00)
    print(f'    RX raw: {hs(resp)}')
    print(f'    RX txt: {resp_clean.decode("ascii", errors="?")!r}')

    if not resp_clean or resp_clean[0:1] != b'/':
        print(f'    ✗ To\'g\'ri format emas (kutilgan: /EKT5...) ')
        # Hali ham urinib ko'rish
        return False

    # Manufacturer va baud ID
    mfr      = resp_clean[1:4].decode('ascii', errors='?')
    baud_chr = chr(resp_clean[4]) if len(resp_clean) > 4 else '?'
    baud_map = {'0':300,'1':600,'2':1200,'3':2400,'4':4800,'5':9600,'6':19200}
    meter_baud = baud_map.get(baud_chr, 9600)
    print(f'    ✓ Meter: /{mfr} | Baud kodi: {baud_chr!r} = {meter_baud} bps')

    # 3. ACK: baud 9600 da qolish (yoki yangi baud)
    # Format: \x06 0 Z baud_char \r\n
    # Z=1 = Programming mode, Z=0 = Data readout mode
    ack = f'\x060{baud_chr}1\r\n'.encode()
    print(f'[3] ACK yuborilmoqda: {hs(ack)}')
    ser.write(ack)
    time.sleep(0.5)   # Meter baud o'zgartirsin

    # 4. RS485 → yangi baud
    print(f'[4] RS485 → {meter_baud} baud ...')
    bridge_set_baud(ser, meter_baud)
    time.sleep(0.3)

    print(f'    ✓ Ulanish muvaffaqiyatli! ({meter_baud} baud)')
    return True

# ── Parametr o'qish ───────────────────────────────────────────────────────────
def read_param(ser: serial.Serial, param: str,
               addr: str = '', label: str = '') -> list[str]:
    frame = make_req(param, addr)
    print(f'  TX {param}: {hs(frame)}')
    resp = send_recv(ser, frame, timeout=3.0, min_wait=0.2)
    if not resp:
        print(f'  → javob yo\'q')
        return []
    # null bayt filtrlash
    resp = bytes(b for b in resp if b != 0x00)
    vals = parse_vals(resp)
    lbl  = label or param
    if vals:
        print(f'  ✓ {lbl}: {", ".join(vals)}')
    else:
        print(f'  ~ {lbl}: javob bor lekin qiymat yo\'q — {hs(resp[:30])}')
    return vals

# ── Hammani o'qish ────────────────────────────────────────────────────────────
def read_all(ser: serial.Serial, addr: str = ''):
    print(f'\n{"="*55}')
    results = {}
    for param, lbl in PARAMS:
        vals = read_param(ser, param, addr=addr, label=lbl)
        if vals:
            results[param] = vals
        time.sleep(0.3)

    print(f'\n{"="*55}')
    print('  NATIJALAR:')
    print(f'{"="*55}')
    if results:
        for param, lbl in PARAMS:
            if param in results:
                v = results[param]
                print(f'  {lbl:35s}: {", ".join(v)}')
    else:
        print('  ✗ Hech qanday parametr o\'qilmadi!')
    print(f'{"="*55}\n')

# ── Asosiy diagnostika ────────────────────────────────────────────────────────
def run(port: str, addr: str = ''):
    print(f'\n{"="*55}')
    print(f'  CE 303 S31 — IEC 62056-21 Reader')
    print(f'  Port: {port} | Addr: "{addr}" (bo\'sh=broadcast)')
    print(f'{"="*55}')

    ser = serial.Serial(port, USB_BAUD, bytesize=8,
                        parity='N', stopbits=1, timeout=2)
    time.sleep(0.5)

    try:
        # Session o'rnatish
        ok = iec_connect(ser, addr=addr)

        if ok:
            print('\n── Parametrlar o\'qilmoqda ────────────────────────────')
            read_all(ser, addr=addr)
        else:
            # Fallback: sessiyasiz tez o'qish sinash (9600 da)
            print('\n── Fallback: 9600 baud tez o\'qish ──────────────────')
            bridge_set_baud(ser, 9600)
            time.sleep(0.3)
            for param, lbl in PARAMS[:5]:
                read_param(ser, param, addr=addr, label=lbl)
                time.sleep(0.5)

    finally:
        # Session yopish
        try:
            ser.write(b'\x01B0\x03\x75')
        except Exception:
            pass
        ser.close()

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = None
    addr = ''

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ('--addr', '-a') and i + 1 < len(args):
            addr = args[i + 1]; i += 2
        elif args[i].startswith('--addr='):
            addr = args[i].split('=', 1)[1]; i += 1
        elif not args[i].startswith('-'):
            port = args[i]; i += 1
        else:
            i += 1

    if not port:
        ports = list(serial.tools.list_ports.comports())
        usb = [p for p in ports
               if 'usb' in p.device.lower() or 'serial' in p.device.lower()]
        port = usb[0].device if usb else (ports[0].device if ports else None)
        if port:
            print(f'Auto-detect: {port}')
        else:
            print('COM port topilmadi!'); sys.exit(1)

    run(port, addr=addr)
