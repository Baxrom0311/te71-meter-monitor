import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))

from dlms.connection import DLMSConnection

conn = DLMSConnection(port='COM18', baud=4800)
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
