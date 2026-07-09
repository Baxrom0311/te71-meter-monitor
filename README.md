# TE71 Meter Monitor

TE71 Meter Monitor — elektr, suv va gaz monitoringi uchun yagona backend va web dashboard platformasi. Tizim ESP32 qurilmalardan HTTP orqali o‘lchovlarni qabul qiladi, binolar kesimida saqlaydi, grafiklar, alertlar, OTA firmware va admin boshqaruvini beradi.

Platforma faqat elektr uchun alohida emas: bitta backend ichida elektr, suv va gaz modullari birga ishlaydi.

## Qanday Ishlaydi

1. ESP32 qurilma elektr hisoblagich, suv sensori yoki gaz sensoridan ma’lumot o‘qiydi.
2. Qurilma HTTP orqali backendga o‘lchov yuboradi.
3. Backend kelgan payloadni `utility_type` bo‘yicha elektr, suv yoki gaz reading modeliga ajratadi.
4. Har bir qurilma building yoki measurement point bilan bog‘lanadi.
5. Dashboard real vaqtga yaqin monitoring, grafiklar, alertlar, OTA va admin amallarini ko‘rsatadi.

Backend MQTT ishlatmaydi. ESP32 bilan asosiy aloqa HTTP orqali bo‘ladi. Web dashboard uchun WebSocket real-time status va yangilanishlar beradi.

## Asosiy Imkoniyatlar

- Elektr, suv va gaz uchun bitta FastAPI backend.
- PostgreSQL asosiy database.
- SQLAlchemy async model/repository/service qatlamlari.
- React + Vite frontend, PWA qo‘llab-quvvatlanadi.
- Admin va oddiy user rollari.
- ESP32 device token orqali himoyalangan HTTP contract.
- Har bir building uchun alohida qurilmalar va grafiklar.
- Dashboardda barcha binolar bo‘yicha elektr/suv/gaz umumiy grafiklari.
- Alert rules, escalation va notification outbox.
- OTA firmware catalog, compatibility metadata va batch rollout.
- Backup export/restore API.
- AI chat endpointlari xavfsiz tool layer orqali ishlaydi.

## Arxitektura

```text
Sensor / meter
  |
  | RS-485, pulse, analog yoki digital sensor
  v
ESP32 universal firmware
  |
  | HTTP + X-Device-Token
  v
FastAPI backend
  |
  | SQLAlchemy async
  v
PostgreSQL
  |
  v
React dashboard + WebSocket
```

Elektr uchun TE71/TE73 hisoblagichlar RS-485/DLMS orqali o‘qilishi mumkin. Suv va gaz uchun bosim/flow sensorlari alohida ESP32 modullar orqali yuboriladi.

## Building Model Mantig‘i

- Har bir dom `Building` sifatida yuritiladi.
- Har bir xonadon, texnik joy yoki umumiy kirish nuqtasi `MeasurementPoint` bo‘lishi mumkin.
- Elektrda domga asosiy elektr hisoblagich va xonadon/nuqta hisoblagichlari ulanadi.
- Suvda pastki va yuqori bosim nuqtalari bo‘lishi mumkin.
- Gazda bosim va flow sensorlari alohida measurement point sifatida ishlaydi.
- Dashboarddagi umumiy grafiklar barcha buildinglar yig‘indisini ko‘rsatadi.
- Building detail sahifasidagi grafiklar faqat shu buildingga biriktirilgan qurilmalar bo‘yicha hisoblanadi.

## Tezkor Ishga Tushirish

Docker orqali to‘liq stack:

```bash
cp .env.example .env
docker compose up -d --build
```

Dashboard:

```text
http://localhost:8000
```

Backend tayyorligini tekshirish:

```bash
curl http://localhost:8000/health
```

Default development login `.env.example` ichida:

```text
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=Admin1234
```

Productionda `SECRET_KEY`, `DEVICE_API_TOKEN`, admin parol va CORS/host sozlamalarini albatta almashtirish kerak.

## Frontendni Alohida Ishlatish

Frontend dev server:

```bash
cd meter-frontend
pnpm install
pnpm dev
```

Frontend API manzili:

```bash
VITE_API_URL=https://67.205.171.93
```

Production build:

```bash
cd meter-frontend
pnpm build
```

Docker compose backend `meter-frontend/dist` papkasini static frontend sifatida serve qiladi.

## Backendni Alohida Ishlatish

Backend uchun Python 3.12 tavsiya qilinadi.

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app:app --host 0.0.0.0 --port 8000
```

Database URL `.env` orqali beriladi:

```text
DATABASE_URL=postgresql+asyncpg://meter:meter_password@localhost:5432/meter_monitor
```

## ESP32 Ishlash Tartibi

ESP32 birinchi ishga tushganda WiFi va server sozlamalarini oladi. Qurilma backenddan o‘z konfiguratsiyasini so‘raydi:

```http
GET /api/device-config/{device_id}
```

Keyin o‘lchovlarni yuboradi:

```http
POST /api/readings
X-Device-Token: <device-token>
Content-Type: application/json
```

ESP32 asosiy server ishlamasa backup serverlarga retry qilishi mumkin. Serverlar ro‘yxati config orqali beriladi.

To‘liq ESP32 HTTP contract:

```text
backend/ESP32_API_CONTRACT.md
```

## OTA Firmware

OTA printer driver katalogiga o‘xshash ishlaydi:

1. Admin firmware `.bin` faylni serverga yuklaydi.
2. Firmware metadata ichida utility type, hardware version, software version, sensor/converter compatibility yoziladi.
3. ESP32 OTA check qilganda backend uning profiliga mos firmware topadi.
4. OTA batch orqali rollout nazorat qilinadi.
5. ESP32 install holatini `/api/ota/report` orqali qaytaradi.

Asosiy endpointlar:

| Method | Endpoint | Tavsif |
|---|---|---|
| `POST` | `/api/ota/upload` | Firmware yuklash |
| `GET` | `/api/ota/list` | Firmware ro‘yxati |
| `POST` | `/api/ota/batches` | OTA batch yaratish |
| `POST` | `/api/ota/batches/{id}/process` | Batch process qilish |
| `POST` | `/api/ota/batches/{id}/cancel` | Batch bekor qilish |
| `POST` | `/api/ota/report` | ESP32 OTA status report |

## Dashboard

Dashboard quyidagilarni ko‘rsatadi:

- jami qurilmalar, online/offline holat;
- yangi biriktirilmagan qurilmalar;
- elektr/suv/gaz bo‘yicha umumiy grafiklar;
- har bir building bo‘yicha alohida grafiklar;
- alertlar;
- firmware va OTA batchlar;
- audit jurnali;
- user management;
- AI yordamchi.

Ma’lumot bo‘lmasa ham grafik panel ko‘rinadi. O‘lchov kelishi bilan chart avtomatik to‘ladi.

## Alert va Notification

Backend elektr, suv va gaz uchun threshold qoidalarini tekshiradi:

- offline device;
- kuchlanish/tok/quvvat anomaliyasi;
- suv bosimi pastligi;
- yuqori qavatga suv chiqmasligi;
- gaz bosimi minimal/maksimal chegaradan chiqishi;
- duplicate alert prevention.

Notification kanallari env orqali boshqariladi:

```text
ALERT_NOTIFICATION_CHANNELS=internal
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ALERT_WEBHOOK_URL=
```

## Backup va Restore

Admin backenddan backup yaratishi, yuklab olishi va restore qilishi mumkin.

| Method | Endpoint | Tavsif |
|---|---|---|
| `POST` | `/api/backups` | Manual backup yaratish |
| `GET` | `/api/backups` | Backup ro‘yxati |
| `GET` | `/api/backups/download/{filename}` | Backup yuklab olish |
| `POST` | `/api/backups/restore/{filename}?confirm=RESTORE` | Restore |
| `DELETE` | `/api/backups/{filename}` | Backup o‘chirish |

Restore xavfli amal bo‘lgani uchun `confirm=RESTORE` talab qilinadi.

## Asosiy APIlar

| Method | Endpoint | Tavsif |
|---|---|---|
| `POST` | `/api/auth/login` | Username/password login |
| `GET` | `/api/summary` | Umumiy statistika |
| `GET` | `/api/buildings` | Buildinglar |
| `POST` | `/api/buildings` | Building yaratish |
| `GET` | `/api/devices` | Qurilmalar |
| `PUT` | `/api/devices/{id}` | Qurilmani tahrirlash/biriktirish |
| `GET` | `/api/devices/{id}/latest` | Oxirgi reading |
| `GET` | `/api/devices/{id}/history` | Qurilma tarixi |
| `GET` | `/api/analytics/hourly` | Elektr/suv/gaz hourly stats |
| `GET` | `/api/alerts` | Alertlar |
| `POST` | `/api/alerts/{id}/clear` | Alert tozalash |
| `GET` | `/api/audit-logs` | Audit jurnali |
| `WS` | `/ws` | Dashboard WebSocket |

OpenAPI docs:

```text
http://localhost:8000/docs
```

## Test va Build

Backend testlar:

```bash
cd backend
pytest
```

Frontend tekshiruv:

```bash
cd meter-frontend
pnpm typecheck
pnpm build
```

ESP32 firmware:

```bash
pio run
pio run -t upload
pio device monitor
```

## Production Eslatmalar

- PostgreSQL ishlating.
- `.env` ichidagi default secret va tokenlarni almashtiring.
- `DEVICE_API_TOKEN` maxfiy saqlansin.
- `CORS_ORIGINS` va `TRUSTED_HOSTS` production domen/IP bo‘yicha cheklansin.
- Firmware fayllari va backup papkasi persistent volume bo‘lsin.
- HTTPS reverse proxy orqali xizmat ko‘rsating.
- Migration deploy vaqtida `alembic upgrade head` ishlashi kerak.

## Litsenziya

Loyiha TE71/TE73 va kommunal monitoring yechimlari uchun ishlab chiqilgan.
