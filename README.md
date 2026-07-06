# TE71 / TE73 Meter Monitor Platform

**Toshelectroapparat** ishlab chiqargan **TE71** (1-fazali) va **TE73** (3-fazali) elektr hisoblagichlari uchun to'liq monitoring va boshqaruv platformasi.

---

## Arxitektura

```
┌─────────────────────────────────────────────────────────────────┐
│                        FIELD (Ob'ekt)                           │
│                                                                 │
│   ┌──────────┐   RS-485 / DLMS    ┌──────────────┐            │
│   │  TE71 /  │◄──────────────────►│   ESP32      │            │
│   │  TE73    │   HDLC frames      │  (MAX485ESA) │            │
│   │Hisoblagich│  9600 baud        │              │            │
│   └──────────┘                   └──────┬───────┘            │
│                                          │ WiFi               │
└──────────────────────────────────────────┼────────────────────┘
                                           │
                              ┌────────────▼─────────────┐
                              │         SERVER            │
                              │                           │
                              │  ┌──────────────────────┐│
                              │  │  Mosquitto MQTT      ││
                              │  │  Broker (port 1883)  ││
                              │  └──────────┬───────────┘│
                              │             │             │
                              │  ┌──────────▼───────────┐│
                              │  │  FastAPI Backend      ││
                              │  │  + SQLite + WebSocket ││
                              │  └──────────┬───────────┘│
                              └─────────────┼─────────────┘
                                            │ WebSocket / HTTP
                              ┌─────────────▼─────────────┐
                              │   Browser Dashboard        │
                              │   (Sneat Bootstrap 5)      │
                              └───────────────────────────┘

     Yoki to'g'ridan:
   ┌──────────┐   RS-485 / DLMS    ┌──────────────────────────┐
   │  TE71 /  │◄──────────────────►│  Windows Desktop App     │
   │  TE73    │   (USB-RS485)      │  (PyQt6 + pyserial)      │
   └──────────┘                   └──────────────────────────┘
```

---

## Foydalanilgan Protokollar

### 1. DLMS/COSEM (IEC 62056)

**DLMS** (Device Language Message Specification) — elektr hisoblagichlar bilan muloqot qilish uchun xalqaro standart. **COSEM** (Companion Specification for Energy Metering) esa ma'lumot modeli.

**Ishlash tartibi:**
```
Client (ESP32/Desktop)              Server (Hisoblagich)
        │                                   │
        │──── SNRM (Set Normal Response) ──►│  1. Kanal ochish
        │◄─── UA (Unnumbered Ack) ──────────│
        │                                   │
        │──── AARQ (Association Request) ──►│  2. Auth (LOW/HLS5)
        │◄─── AARE (Association Response) ──│
        │                                   │
        │──── GET.Request (OBIS code) ──────►│  3. Ma'lumot o'qish
        │◄─── GET.Response (data) ──────────│
        │                                   │
        │──── DISC (Disconnect) ────────────►│  4. Kanal yopish
        │◄─── UA ───────────────────────────│
```

**Autentifikatsiya rejimlari:**
| Rejim | Client ID | Tavsif |
|-------|-----------|--------|
| Public (NONE) | 16 | Parolsiz, faqat umumiy ma'lumot |
| Reader (LOW) | 1 | Oddiy parol bilan barcha o'qish |
| Manager (HLS5) | 2 | MD5-challenge, to'liq boshqaruv |

### 2. HDLC (ISO/IEC 13239 / IEC 62056-46)

**HDLC** (High-level Data Link Control) — DLMS ma'lumotlarini RS-485 ustidan transport qilish uchun frame protokoli.

**Frame tuzilishi:**
```
┌──────┬────────┬──────┬──────┬──────┬──────────┬─────┬──────┐
│ 0x7E │ Format │ Dest │ Src  │ Ctrl │   HCS    │Info │ FCS  │ 0x7E │
│ Flag │ Field  │ Addr │ Addr │ Byte │(CRC-16)  │     │(CRC) │ Flag │
└──────┴────────┴──────┴──────┴──────┴──────────┴─────┴──────┘
```

- **FCS** — CRC-16/IBM algoritmi (polynomial `0x8408`)
- **Ctrl byte**: `SNRM=0x93`, `UA=0x73`, `I-frame=0x00/0x20`, `DISC=0x53`
- Har bir I-frame da **send_seq** va **recv_seq** raqamlar boshqariladi

### 3. OBIS Kodlar (IEC 62056-61)

Har bir parametrga **6-baytli** identifikator: `A.B.C.D.E.F`

| OBIS Kod | Parametr | Birlik |
|----------|----------|--------|
| `0.0.96.1.0.255` | Serial raqam | — |
| `1.0.32.7.0.255` | Kuchlanish L1 | V |
| `1.0.52.7.0.255` | Kuchlanish L2 (TE73) | V |
| `1.0.72.7.0.255` | Kuchlanish L3 (TE73) | V |
| `1.0.31.7.0.255` | Tok L1 | A |
| `1.0.15.7.0.255` | Aktiv quvvat | W |
| `1.0.14.7.0.255` | Chastota | Hz |
| `1.0.1.8.0.255` | Umumiy energiya | kWh |
| `0.0.96.3.10.255` | Rele holati | — |

### 4. RS-485 (EIA-485)

**Differential** signal standarti — shovqinga chidamli, 1200m gacha.

**Pinout (ESP32 + MAX485ESA):**
```
ESP32 GPIO17 (TX) ──► MAX485 DI
ESP32 GPIO16 (RX) ◄── MAX485 RO  [10kΩ/20kΩ voltage divider orqali]
ESP32 GPIO4  (DE) ──► MAX485 DE + /RE (birlashtirilgan)

MAX485 A ──────────────────── RS-485 A (sariq)
MAX485 B ──────────────────── RS-485 B (ko'k)
```

> ⚠️ MAX485ESA 5V bilan ishlaydi, RO chiqishi ~4.8V. ESP32 GPIO 3.3V tolerant, shuning uchun voltage divider (10kΩ + 20kΩ) ishlatilgan.

### 5. MQTT (Message Queuing Telemetry Transport)

ESP32 ↔ Backend o'rtasidagi asinxron xabar almashish protokoli.

**Topic tuzilishi:**
```
meters/{MAC_ADDRESS}/telemetry   ← ESP32 publish qiladi (JSON o'lchov)
meters/{MAC_ADDRESS}/cmd         ← Backend buyruq yuboradi (relay, reboot, OTA)
meters/{MAC_ADDRESS}/status      ← LWT (Last Will Testament) — offline detection
```

**Telemetry JSON namunasi:**
```json
{
  "mac": "AA:BB:CC:DD:EE:FF",
  "meter_serial": "12345678",
  "meter_type": "TE71",
  "voltage_l1": 224.5,
  "current_l1": 2.31,
  "power_w": 518.7,
  "frequency": 49.98,
  "energy_kwh": 1234.56,
  "relay_on": true,
  "ts": 1735689600
}
```

### 6. WebSocket

Browser ↔ Backend o'rtasida real-time ma'lumot uzatish.

**Xabar turlari:**
| Type | Tavsif |
|------|--------|
| `snapshot` | Ulanganda barcha qurilma va alertlar |
| `reading` | Yangi o'lchov (30 soniyada bir) |
| `status` | Qurilma online/offline o'zgardi |
| `alert` | Yangi ogohlantirish (kuchlanish, chastota, offline) |
| `device_online` | Yangi ESP32 ro'yxatdan o'tdi |

---

## Loyha Tarkibi

```
te71-meter-monitor/
│
├── src/main.cpp              # ESP32 Arduino firmware
├── platformio.ini            # PlatformIO konfiguratsiyasi
├── include/config.h          # Pin va timeout konstantalari
├── sdkconfig.defaults        # ESP32 SDK sozlamalari
│
├── backend/
│   ├── app.py                # FastAPI + SQLite + WebSocket + MQTT
│   └── requirements.txt
│
├── frontend/
│   ├── index.html            # Sneat Bootstrap 5 dashboard (SPA)
│   └── assets/               # Sneat CSS/JS/fonts (ko'chirilib olingan)
│
├── desktop/
│   ├── main.py               # Entry point (PyQt6)
│   ├── meter.py              # Meter abstraction (TE71/TE73 auto-detect)
│   ├── dlms/
│   │   ├── hdlc.py           # HDLC framing + FCS16
│   │   ├── connection.py     # SNRM/AARQ/GET/SET/ACTION/DISC
│   │   ├── parser.py         # DLMS data types parser + encoder
│   │   └── obis.py           # OBIS kod registri
│   ├── ui/
│   │   ├── main_window.py    # Asosiy oyna + ulanish paneli
│   │   ├── dashboard.py      # Real-time ko'rsatkichlar
│   │   ├── relay_panel.py    # Rele boshqarish
│   │   ├── registers_panel.py# Barcha OBIS registrlar jadvali
│   │   ├── settings_panel.py # Vaqt, tarif, parol
│   │   ├── log_panel.py      # HDLC frame log
│   │   └── styles.py         # Dark theme QSS
│   └── requirements.txt
│
├── product/
│   └── MeterToolSetup.exe    # Windows installer (tayyor mahsulot)
│
├── mosquitto/
│   └── mosquitto.conf        # MQTT broker konfiguratsiyasi
├── docker-compose.yml        # Docker orqali ishga tushirish
└── .env.example              # Muhit o'zgaruvchilari namunasi
```

---

## Tezkor Ishga Tushirish

### Server (Docker bilan)

```bash
# 1. Reponi yuklab olish
git clone https://github.com/Baxrom0311/te71-meter-monitor.git
cd te71-meter-monitor

# 2. Konfiguratsiya
cp .env.example .env
# .env faylni tahrirlang: SECRET_KEY, DEVICE_API_TOKEN, DATABASE_URL va boshqalar

# 3. Ishga tushirish
docker compose up -d --build

# Dashboard: http://localhost:8000
# Flower: http://localhost:5555
```

### ESP32 Firmware

```bash
# PlatformIO o'rnatilgan bo'lishi kerak
pip install platformio

# Yuklash
pio run -t upload

# Serial monitor
pio device monitor
```

**Birinchi marta ishga tushganda:**
1. ESP32 `MeterSetup` WiFi tarmog'ini ochadi (parol: `meter1234`)
2. Telefon yoki noutbukdan ulanib `192.168.4.1` ga kiring
3. WiFi tarmog'i, asosiy Server URL va backup Server URLlarni kiriting
4. Saqlash — ESP32 qayta ishga tushadi va hisoblagichni topadi

### Windows Desktop Tool

```
product/MeterToolSetup.exe — o'rnating va ishga tushiring
```

Yoki manba koddan:
```bash
pip install PyQt6 pyserial
python desktop/main.py
```

---

## Backend API

| Method | Endpoint | Tavsif |
|--------|----------|--------|
| GET | `/api/devices` | Qurilmalar ro'yxati (filter: online, type, group) |
| GET | `/api/devices/{id}/latest` | Oxirgi o'lchov |
| GET | `/api/devices/{id}/stats?hours=24` | Soatlik agregat (grafik uchun) |
| GET | `/api/devices/{id}/export?hours=24` | CSV yuklab olish |
| PUT | `/api/devices/{id}` | Nom, joylashuv tahrirlash |
| POST | `/api/devices/{id}/relay` | Rele yoq/o'chir |
| POST | `/api/devices/{id}/reboot` | Qayta yuklash buyrug'i |
| GET | `/api/summary` | Umumiy statistika (jami, online, energiya) |
| GET | `/api/alerts?limit=20` | Ogohlantirishlar |
| POST | `/api/alerts/{id}/clear` | Alertni tozalash |
| POST | `/api/alerts/clear-all` | Barchasini tozalash |
| POST | `/api/ota/upload` | Firmware yuklash (.bin) |
| GET | `/api/ota/list` | Firmware versiyalar ro'yxati |
| POST | `/api/ota/push/{id}` | OTA buyrug'i yuborish |
| DELETE | `/api/ota/{id}` | Firmwareni o'chirish |
| GET | `/metrics` | Prometheus text metrics |
| WS | `/ws` | WebSocket real-time stream |

---

## Texnik Talablar

| Komponent | Texnologiya |
|-----------|-------------|
| Mikrokontroller | ESP32 DevKit v1 |
| RS-485 interfeys | MAX485ESA |
| Firmware | Arduino (PlatformIO), C++17 |
| Backend | Python 3.12, FastAPI, SQLAlchemy asyncio, Alembic |
| Queue | Redis, Celery, Celery Beat, Flower |
| Frontend | Bootstrap 5 (Sneat), ApexCharts, WebSocket |
| Desktop | Python 3.x, PyQt6, pyserial |
| Deploy | Dockerfile + Docker Compose |

CI: GitHub Actions backend smoke test, py_compile va Alembic migration upgrade tekshiradi.

---

## Litsenziya

Faqat **Toshelectroapparat** TE71/TE73 hisoblagichlari bilan ishlatish uchun mo'ljallangan.
