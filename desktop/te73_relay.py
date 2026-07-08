import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

import serial.tools.list_ports
from dlms.connection import DLMSConnection

def _autoport():
    if len(sys.argv) > 1:
        return sys.argv[1]
    usb = [p.device for p in serial.tools.list_ports.comports()
           if 'usb' in p.device.lower() or 'serial' in p.device.lower()]
    return usb[0] if usb else serial.tools.list_ports.comports()[0].device

PORT = _autoport()
print(f'Port: {PORT}')

# ESP32 bridge: USB=9600, RS485=4800 (bridge ichida)
conn = DLMSConnection(port=PORT, baud=9600)
conn.open()
print('Client 1 HLS5 ulanmoqda...')
if conn.connect_reader():
    print('Ulandi!')
    print('Rele yoqilyapti (method 2 = reconnect)...')
    ok, code = conn.action(70, (0, 0, 96, 3, 10, 255), 2)
    if ok:
        print('MUVAFFAQIYAT - rele yoqildi!')
    else:
        print(f'XATO - code={code}')
    conn.disconnect()
else:
    print('Ulanmadi')
conn.close()
