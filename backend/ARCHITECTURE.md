# Unified Utilities Backend Architecture

Bu hujjat elektr, suv va gaz monitoring tizimi uchun yagona backend arxitekturasini belgilaydi. Hujjat hozircha loyiha yo'nalishini aniqlash uchun yozildi; keyingi xabarlarda to'g'rilab boramiz.

## Asosiy Qarorlar

- Bitta backend bo'ladi. Elektr, suv va gaz uchun alohida backend qilinmaydi.
- Har bir dom tizimdagi asosiy model bo'ladi.
- Har bir domga elektr, suv va gaz monitoring modullari ulanadi.
- Har bir sensor yoki hisoblagich alohida `measurement point` sifatida yuritiladi.
- Har bir asosiy yo'nalish uchun alohida ESP32 ishlatiladi:
  - elektr uchun alohida ESP32
  - suv uchun alohida ESP32
  - gaz uchun alohida ESP32
- MQTT broker ishlatilmaydi.
- Hamma ESP32 ma'lumotni HTTP orqali backendga yuboradi.
- ESP32 bir nechta serverga yubora olishi kerak:
  - 1 ta asosiy server
  - 2-3 ta optional backup server
  - asosiy server ishlamasa, backup serverlar ma'lumotni qabul qiladi
- Eski ESP32 elektr payloadlari buzilmasdan ishlashi kerak.
- Backend production uslubda ajratiladi:
  - models
  - schemas
  - repositories
  - services
  - controllers/routers
  - workers

## Real Hayotdagi Sensor Joylashuvi

### Elektr

Har bir dom uchun:

- 1 ta asosiy elektr hisoblagich bo'ladi.
- Bu hisoblagich domga kirayotgan umumiy elektrni o'lchaydi.
- Elektr uchun alohida ESP32 bo'ladi.
- Xonadon bo'yicha alohida hisoblagichlar keyingi bosqichda qo'shilishi mumkin.

Minimal model:

```text
Dom
  -> Elektr ESP32
      -> Asosiy elektr hisoblagich
```

### Suv

Har bir dom uchun:

- Pastda 1 ta suv bosimi sensori bo'ladi.
- Yuqorida 1 ta suv bosimi sensori bo'ladi.
- Sabab: yuqori qavatlarga suv chiqyaptimi yoki yo'qmi, shuni real analiz qilish.
- Suv uchun alohida ESP32 bo'ladi.
- Suv ESP32 ikkita sensorni ham o'qishi yoki har sensor uchun alohida ESP32 ishlatilishi mumkin. Boshlang'ich qaror: suv moduli bitta ESP32, pastki va yuqori sensorlar unga ulanadi.

Minimal model:

```text
Dom
  -> Suv ESP32
      -> Pastki suv bosimi sensori
      -> Yuqori suv bosimi sensori
```

Analiz misoli:

- Pastda bosim bor, yuqorida bosim yo'q: suv yuqoriga chiqmayapti.
- Pastda ham yuqorida ham bosim past: umumiy suv ta'minotida muammo.
- Pastda normal, yuqorida vaqti-vaqti bilan tushib ketyapti: nasos yoki quvur muammosi bo'lishi mumkin.

### Gaz

Har bir dom uchun:

- 1 ta gaz bosimi sensori bo'ladi.
- Gaz uchun alohida ESP32 bo'ladi.
- Keyingi bosqichda leak sensor yoki valve control qo'shilishi mumkin.

Minimal model:

```text
Dom
  -> Gaz ESP32
      -> Gaz bosimi sensori
```

## High-Level Architecture

```text
ESP32 Devices
  Electricity ESP32
  Water ESP32
  Gas ESP32
        |
        | HTTP POST
        | primary server + optional backup servers
        v
Unified Backend
  Controllers / Routers
  Services
  Repositories
  Models
  Workers
        |
        v
Database
  Buildings
  Utility modules
  Measurement points
  Devices
  Readings
  Alerts
  Users
  OTA versions
        |
        v
Frontend / Admin Dashboard
```

## Device Provisioning Flow

Productionda ESP32lar umumiy parol bilan doimiy ishlamasligi kerak. Shuning uchun backendda bir martalik provisioning token modeli bor.

Admin quyidagilarni oldindan tanlaydi:

- `device_id` optional scope
- `building_id`
- `point_id`
- `utility_type`: `electricity`, `water`, `gas`
- `device_role`: masalan `electricity_node`, `water_node`, `gas_node`
- `firmware_mode`: `electricity`, `water`, `gas`, `auto`
- token muddati (`ttl_sec`)

ESP32 birinchi ishga tushganda:

1. `POST /api/register` ga `provisioning_token` yuboradi.
2. Backend tokenni tekshiradi va ishlatilgan deb belgilaydi.
3. Backend token scope bo'yicha device’ni building/measurement point/utility bilan bog'laydi.
4. Backend shu ESP32 uchun alohida `device_token` yaratib qaytaradi.
5. ESP32 keyingi barcha HTTP requestlarda `X-Device-Token: <device_token>` ishlatadi.

Tokenlar jadvali:

- `device_provisioning_tokens`
- token plaintext saqlanmaydi, faqat hash saqlanadi
- `used_at` va `used_by_device_id` orqali qayta ishlatish bloklanadi
- `revoked_at` orqali admin bekor qilgan tokenlar bloklanadi
- list API token hash yoki plaintextni qaytarmaydi

Bu printer driverlariga o'xshash provisioning modeli: admin oldindan qaysi sensor qaysi dom, qaysi nuqta, qaysi firmware mode bilan ishlashini belgilaydi; ESP32 esa birinchi register paytida shu scope’ni oladi.

## Backend Domain Model

### Building Model

Har bir dom uchun bitta asosiy model.

Maydonlar:

- `id`
- `name`
- `address`
- `floors`
- `entrances_count`
- `description`
- `is_active`
- `created_at`
- `updated_at`

Misol:

```json
{
  "id": 1,
  "name": "12-dom",
  "address": "Toshkent, Yunusobod",
  "floors": 9,
  "entrances_count": 2,
  "is_active": true
}
```

### Building Utility Module

Har bir domga ulangan elektr/suv/gaz moduli.

Bu model dom bilan utilityni bog'laydi.

Maydonlar:

- `id`
- `building_id`
- `utility_type`: `electricity`, `water`, `gas`
- `name`
- `status`: `active`, `disabled`, `maintenance`
- `created_at`
- `updated_at`

Misol:

```json
{
  "id": 10,
  "building_id": 1,
  "utility_type": "water",
  "name": "12-dom suv monitoring",
  "status": "active"
}
```

### Measurement Point Model

Sensor yoki hisoblagich turgan real nuqta.

Maydonlar:

- `id`
- `building_id`
- `utility_module_id`
- `device_id`
- `utility_type`: `electricity`, `water`, `gas`
- `sensor_type`
- `role`
- `location_name`
- `floor`
- `is_active`
- `created_at`
- `updated_at`

`role` variantlari:

- `electricity_main_meter`
- `water_pressure_bottom`
- `water_pressure_top`
- `gas_pressure_main`
- `water_flow`
- `gas_flow`
- `gas_leak`

Elektr measurement point:

```json
{
  "building_id": 1,
  "utility_type": "electricity",
  "sensor_type": "electric_meter",
  "role": "electricity_main_meter",
  "location_name": "Podvaldagi asosiy elektr hisoblagich"
}
```

Suv pastki sensor:

```json
{
  "building_id": 1,
  "utility_type": "water",
  "sensor_type": "pressure_sensor",
  "role": "water_pressure_bottom",
  "location_name": "Pastki suv kirish nuqtasi",
  "floor": 1
}
```

Suv yuqori sensor:

```json
{
  "building_id": 1,
  "utility_type": "water",
  "sensor_type": "pressure_sensor",
  "role": "water_pressure_top",
  "location_name": "Yuqori qavat suv nuqtasi",
  "floor": 9
}
```

Gaz sensor:

```json
{
  "building_id": 1,
  "utility_type": "gas",
  "sensor_type": "pressure_sensor",
  "role": "gas_pressure_main",
  "location_name": "Asosiy gaz kirish nuqtasi"
}
```

### Device Model

ESP32 qurilmasi.

Har bir ESP32 o'z vazifasiga ega bo'ladi, lekin firmware framework bitta bo'ladi.

Maydonlar:

- `id`
- `building_id`
- `utility_type`: `electricity`, `water`, `gas`
- `device_role`: `electricity_node`, `water_node`, `gas_node`
- `mac_address`
- `serial_number`
- `hardware_version`
- `software_version`
- `firmware_mode`
- `ip`
- `rssi`
- `last_seen`
- `status`: `online`, `offline`, `maintenance`
- `is_active`
- `created_at`
- `updated_at`

`firmware_mode` variantlari:

- `electricity`
- `water`
- `gas`
- `auto`

Misol:

```json
{
  "id": "ESP32-001",
  "building_id": 1,
  "utility_type": "water",
  "device_role": "water_node",
  "hardware_version": "HW-1.0",
  "software_version": "FW-1.3.2",
  "firmware_mode": "water"
}
```

### Reading Models

Backend sensor turiga qarab readinglarni modelga ajratadi. API bitta bo'lishi mumkin, lekin ichki model utility bo'yicha ajratiladi.

#### Common Reading

Hamma readinglar uchun umumiy fieldlar:

- `id`
- `building_id`
- `device_id`
- `measurement_point_id`
- `utility_type`
- `sensor_type`
- `ts`
- `raw_payload`
- `created_at`

#### Electricity Reading

Elektr hisoblagichdan keladigan ma'lumot.

Maydonlar:

- `voltage_l1`
- `voltage_l2`
- `voltage_l3`
- `current_l1`
- `current_l2`
- `current_l3`
- `power_w`
- `power_var`
- `frequency`
- `pf`
- `energy_kwh`
- `energy_t1`
- `energy_t2`
- `energy_t3`
- `energy_t4`
- `relay_on`

#### Water Reading

Suv sensorlaridan keladigan ma'lumot.

Maydonlar:

- `pressure_bottom_bar`
- `pressure_top_bar`
- `pressure_bar`
- `flow_rate`
- `volume_m3`
- `temperature_c`

Izoh:

- Agar bitta payloadda pastki va yuqori sensor qiymati kelsa, `pressure_bottom_bar` va `pressure_top_bar` to'ldiriladi.
- Agar har sensor alohida yuborsa, `measurement_point.role` orqali pastki yoki yuqori ekanligi aniqlanadi va `pressure_bar` ishlatiladi.

#### Gas Reading

Gaz sensorlaridan keladigan ma'lumot.

Maydonlar:

- `pressure_bar`
- `flow_rate`
- `volume_m3`
- `temperature_c`
- `leak_detected`
- `valve_open`

## ESP32 Unified Firmware Framework

ESP32lar uchun bitta umumiy firmware codebase bo'ladi. U konfiguratsiyaga qarab elektr, suv yoki gaz vazifasini bajaradi.

### Firmware Core

Hamma rejimlarda umumiy bo'ladigan qismlar:

- Wi-Fi ulanish
- device config saqlash
- serverlar ro'yxatini saqlash
- HTTP client
- retry/fallback logic
- time sync
- device registration
- health/status yuborish
- OTA check va OTA update
- hardware/software version yuborish
- local config portal yoki serial config
- log/debug mode

### Firmware Modes

Firmware ichida mode tanlanadi:

- `electricity`
- `water`
- `gas`

Tanlash usullari:

- config file
- serial command
- web config portal
- backenddan kelgan provisioning response
- compile-time default

### Electricity Mode

Vazifalar:

- TE71/TE73 hisoblagichni o'qish
- voltage/current/power/energy qiymatlarini olish
- relay holatini o'qish/boshqarish
- `/api/readings` ga HTTP yuborish
- `/api/commands/{device_id}` orqali command polling

### Water Mode

Vazifalar:

- pastki bosim sensorini o'qish
- yuqori bosim sensorini o'qish
- kerak bo'lsa flow sensorni o'qish
- bosim farqini payloadga qo'shish
- `/api/readings` ga HTTP yuborish

### Gas Mode

Vazifalar:

- gaz bosim sensorini o'qish
- kerak bo'lsa flow/leak sensorni o'qish
- valve holatini o'qish
- `/api/readings` ga HTTP yuborish

## HTTP Multi-Server Delivery

MQTT ishlatilmaydi. ESP32 faqat HTTP orqali ishlaydi.

ESP32 config:

```json
{
  "servers": [
    {
      "url": "https://main.example.uz",
      "priority": 1,
      "enabled": true
    },
    {
      "url": "https://backup1.example.uz",
      "priority": 2,
      "enabled": true
    },
    {
      "url": "https://backup2.example.uz",
      "priority": 3,
      "enabled": false
    }
  ]
}
```

Yuborish qoidasi:

1. Avval asosiy serverga yuboradi.
2. Asosiy server javob bermasa, backup serverga yuboradi.
3. Agar hammasi ishlamasa, local queuega yozadi.
4. Internet tiklanganda queue qayta yuboriladi.
5. Readingda `reading_id` yoki `sequence_no` bo'ladi, backend duplicate readingni aniqlay oladi.

HTTP endpointlar:

```text
GET  /api/device-config/{device_id}
POST /api/register
POST /api/readings
POST /api/readings/batch
POST /api/device-status
GET  /api/commands/{device_id}
POST /api/commands/{command_id}/ack
GET  /api/ota/check/{device_id}
GET  /api/ota/firmware/{filename}
```

ESP32 uchun aniq HTTP contract: `backend/ESP32_API_CONTRACT.md`.

`GET /api/device-config/{device_id}` ESP32 unified firmware uchun startup config qaytaradi:

- `firmware_mode`: `electricity`, `water`, `gas`, `auto`
- `utility_type`
- `building_id`
- `measurement_point_id`
- telemetry/status/command polling intervallari
- asosiy va backup serverlar ro'yxati
- ishlatiladigan HTTP endpoint pathlari
- `token_required`

`POST /api/readings/batch` ESP32 local queue uchun ishlatiladi. Internet uzilib qayta tiklanganda ESP32 bir nechta readingni bitta requestda yuboradi.

Batch payload:

```json
{
  "device_id": "WATER-01",
  "readings": [
    {
      "device_id": "WATER-01",
      "reading_id": "WATER-01-1001",
      "utility_type": "water",
      "pressure_bottom_bar": 2.4,
      "pressure_top_bar": 0.3
    }
  ]
}
```

`reading_id` majburiy bo'lishi tavsiya qilinadi. Bir xil `device_id + reading_id` qayta kelsa backend duplicate sifatida skip qiladi.

## API Design

### Auth

```text
POST /api/auth/login
POST /api/auth/refresh
POST /api/auth/logout
GET  /api/auth/me
```

### Buildings

```text
POST   /api/buildings
GET    /api/buildings
GET    /api/buildings/{id}
PUT    /api/buildings/{id}
DELETE /api/buildings/{id}
POST   /api/buildings/{id}/provision-defaults
```

`POST /api/buildings/{id}/provision-defaults` admin uchun tez sozlash endpointi. U quyidagilarni yaratadi:

- electricity utility module
- water utility module
- gas utility module
- `electricity_main_meter` point
- `water_pressure_bottom` point
- `water_pressure_top` point
- `gas_pressure_main` point

Payload:

```json
{
  "electricity_device_id": "ELEC-01",
  "water_device_id": "WATER-01",
  "gas_device_id": "GAS-01",
  "top_floor": 9
}
```

### Building Utility Modules

```text
POST /api/buildings/{building_id}/utilities
GET  /api/buildings/{building_id}/utilities
PUT  /api/buildings/{building_id}/utilities/{utility_id}
```

### Measurement Points

```text
POST   /api/measurement-points
GET    /api/measurement-points
GET    /api/measurement-points/{id}
PUT    /api/measurement-points/{id}
DELETE /api/measurement-points/{id}
```

### Devices

```text
POST /api/register
GET  /api/devices
GET  /api/devices/{id}
PUT  /api/devices/{id}
POST /api/device-status
```

### Readings

```text
POST /api/readings
GET  /api/readings
GET  /api/buildings/{building_id}/readings/latest
GET  /api/buildings/{building_id}/readings/history
GET  /api/buildings/{building_id}/analytics
GET  /api/devices/{device_id}/latest
GET  /api/devices/{device_id}/history
```

Building analytics quyidagilarni qaytaradi:

- elektr: sample count, umumiy/oxirgi energy, average/max power, average voltage
- suv: pastki bosim, yuqori bosim, bosim farqi, yuqoriga suv chiqmagan holatlar soni
- gaz: average/min/max pressure, leak count

### Commands

```text
POST /api/devices/{device_id}/commands
GET  /api/commands/admin/list
GET  /api/commands/{device_id}
POST /api/commands/{command_id}/ack
```

Command lifecycle:

- admin command yaratganda `expires_at` qo'yiladi
- ESP32 command poll qilganda `sent`, `attempts`, `status=sent` yangilanadi
- ESP32 ack yuborsa `status=acked`
- `COMMAND_TTL_SEC` tugagan command `expired` bo'ladi
- `COMMAND_MAX_PENDING_PER_DEVICE` bitta qurilmaga osilib qolgan commandlar limitini himoya qiladi
- Celery `maintenance.expire_commands` har 60 sekundda expired commandlarni yopadi

### OTA

```text
POST   /api/ota/upload
GET    /api/ota/list
GET    /api/ota/check/{device_id}
GET    /api/ota/firmware/{filename}
POST   /api/ota/push/{device_id}
DELETE /api/ota/{id}
```

## User Roles

Login faqat oddiy `username + password` orqali bo'ladi. Google, OAuth, Telegram yoki boshqa external login kerak emas.

Xavfsizlik qoidalari:

- parol databasega plain text yozilmaydi
- parol PBKDF2 hash + random salt bilan saqlanadi
- login token server secret bilan imzolanadi
- 5 marta xato paroldan keyin account vaqtincha bloklanadi
- minimal parol uzunligi talab qilinadi
- admin yaratish productionda faqat environment orqali bootstrap qilinadi

Endpoint permission qoidalari:

- Dashboard va ko'rish endpointlari login talab qiladi.
- Admin sozlash, command, OTA upload/delete/push va alert clear qila oladi.
- Oddiy user faqat ko'radi.
- ESP32 compatibility endpointlari user login talab qilmaydi.
- Productionda ESP32 endpointlari `X-Device-Token` orqali himoyalanadi.
- `DEVICE_API_TOKEN` global provisioning/emergency token sifatida ishlaydi.
- Admin `POST /api/devices/{device_id}/token` orqali har ESP32 uchun alohida token yaratadi.
- Device token faqat bir marta plaintext qaytadi; DBda hash saqlanadi.
- Agar devicega alohida token berilgan bo'lsa, ESP32 o'sha token bilan ishlaydi.
- Agar tokenlar sozlanmagan bo'lsa, development uchun ESP32 endpointlari ochiq ishlaydi.
- ESP32 endpointlari:
  - `GET /api/device-config/{device_id}`
  - `POST /api/register`
  - `POST /api/readings`
  - `POST /api/readings/batch`
  - `POST /api/device-status`
  - `GET /api/commands/{device_id}`
  - `POST /api/commands/{command_id}/ack`
  - `GET /api/ota/check/{device_id}`
  - `GET /api/ota/firmware/{filename}`

Admin device token endpoint:

```text
POST /api/devices/{device_id}/token
```

Response:

```json
{
  "device_id": "WATER-01",
  "device_token": "plain-token-only-once",
  "token_type": "device"
}
```

### Admin

Admin hammasini boshqara oladi:

- dom yaratish/o'zgartirish/o'chirish
- ESP32 qo'shish/o'zgartirish/o'chirish
- measurement point yaratish
- utility module sozlash
- OTA yuklash
- command yuborish
- alertlarni clear qilish
- userlarni boshqarish

### Oddiy User

Oddiy user faqat ko'ra oladi:

- domlar ro'yxati
- sensor holati
- readinglar
- alertlar
- dashboard analytics

Oddiy user qila olmaydi:

- device qo'shish
- command yuborish
- OTA qilish
- sozlamani o'zgartirish
- user boshqarish

## OTA va Versioning

Har bir ESP32 quyidagilarni backendga yuboradi:

- `hardware_version`
- `software_version`
- `firmware_mode`
- `device_role`
- `build_number`

OTA modeli printer driver katalogi kabi ishlaydi. Admin serverga `.bin` firmware yuklaydi va shu paket qaysi plata, qaysi sensor, qaysi konvertor va qaysi vazifa uchun ekanini yozadi. ESP32 OTA check qilganda backend device profilini o'qib aynan mos firmware paketni qaytaradi.

Device profil:

- `hardware_version`: masalan `HW-1.0`, `ESP32-WROOM-RS485-v1`
- `software_version`: hozir ishlayotgan firmware versiyasi
- `firmware_mode`: `auto`, `electricity`, `water`, `gas`
- `utility_type`: `electricity`, `water`, `gas`
- `device_role`: `main_meter`, `apartment_meter`, `water_pressure_bottom`, `water_pressure_top`, `gas_pressure_main`
- `sensor_type`: masalan `PZEM-004T`, `TE73`, `pressure_4_20ma`, `gas_pressure_0_10bar`
- `converter_type`: masalan `MAX485`, `ADS1115`, `RS485-TTL`, `4-20mA-to-ADC`
- `build_number`: firmware build identifikatori

OTA firmware catalog:

- `id`
- `version`
- `hardware_version`
- `firmware_mode`
- `utility_type`
- `device_role`
- `sensor_type`
- `converter_type`
- `file_name`
- `sha256`
- `size`
- `is_active`
- `description`: paket nima uchun ekanini tushuntiradi
- `release_notes`
- `compatibility_notes`: qaysi sensor/konvertor/plata kombinatsiyasi bilan ishlashini aniq yozadi
- `uploaded_by`
- `created_at`

Firmware compatibility row:

- `firmware_id`
- `hardware_version`
- `firmware_mode`
- `utility_type`
- `device_role`
- `sensor_type`
- `converter_type`
- `notes`

Moslik qoidasi:

- `None`, `any`, `all`, `*` qiymatlari wildcard hisoblanadi.
- `firmware_mode=auto` umumiy firmware sifatida barcha mode'larga mos kelishi mumkin.
- Aniq paket yuklanganda shu tuple bo'yicha eski aktiv paket deaktiv qilinadi.
- Bir xil versiya allaqachon device'da bo'lsa `update=false` qaytadi.

OTA check qoidasi:

1. ESP32 `/api/ota/check/{device_id}` ga so'rov yuboradi.
2. Backend `Device` va unga bog'langan `MeasurementPoint` profilini oladi.
3. `hardware_version`, `firmware_mode`, `utility_type`, `device_role`, `sensor_type`, `converter_type` bo'yicha eng yangi aktiv mos firmware tanlanadi.
4. Mos firmware bo'lsa `url`, `sha256`, `size`, izohlar va moslik metadata qaytariladi.
5. Mos bo'lmasa update yo'q.

Misol response:

```json
{
  "update": true,
  "version": "1.4.0",
  "hardware_version": "HW-1.0",
  "firmware_mode": "water",
  "utility_type": "water",
  "device_role": "water_pressure_top",
  "sensor_type": "pressure_4_20ma",
  "converter_type": "ADS1115",
  "description": "ESP32 suv bosim yuqori nuqta firmware",
  "compatibility_notes": "ESP32-WROOM HW-1.0 + 4-20mA pressure sensor + ADS1115",
  "url": "/api/ota/firmware/water_hw1_v1_4_0.bin?device_id=esp32-water-top-01",
  "size": 902144,
  "sha256": "..."
}
```

## Backend Folder Structure

```text
backend/
  app.py
  core/
    config.py
    database.py
    security.py
    logging.py
  models/
    user.py
    building.py
    building_utility.py
    measurement_point.py
    device.py
    reading.py
    alert.py
    command.py
    ota.py
  schemas/
    auth.py
    building.py
    building_utility.py
    measurement_point.py
    device.py
    reading.py
    alert.py
    command.py
    ota.py
  repositories/
    building_repository.py
    building_utility_repository.py
    measurement_point_repository.py
    device_repository.py
    reading_repository.py
    alert_repository.py
    command_repository.py
    ota_repository.py
    user_repository.py
  services/
    auth_service.py
    building_service.py
    building_utility_service.py
    measurement_point_service.py
    device_service.py
    reading_service.py
    alert_service.py
    command_service.py
    ota_service.py
    analytics_service.py
  routers/
    auth.py
    buildings.py
    building_utilities.py
    measurement_points.py
    devices.py
    readings.py
    alerts.py
    commands.py
    ota.py
    health.py
  workers/
    celery_app.py
    maintenance_tasks.py
    alert_processor.py
  tasks/
    maintenance.py
  tests/
```

## Worker Architecture

Production rejimda backend ichidagi og'ir va periodik ishlar Celery orqali yuradi:

- `Redis`: Celery broker va result backend
- `celery-worker`: tasklarni bajaradi
- `celery-beat`: periodik tasklarni reja bo'yicha queue'ga qo'yadi
- `Flower`: Celery task monitoring UI

Joriy periodik tasklar:

- `maintenance.detect_offline_devices`: har 60 sekundda offline device alertlarini yaratadi
- `maintenance.cleanup_old_data`: har kuni eski reading va tozalangan alertlarni o'chiradi
- `backup.create`: admin trigger qiladigan JSON gzip backup export
- `backup.cleanup_old`: `BACKUP_KEEP_DAYS` bo'yicha eski backup fayllarni o'chiradi
- `maintenance.cleanup_old_audit_logs`: `AUDIT_KEEP_DAYS` bo'yicha eski audit loglarni o'chiradi

FastAPI ichida `RUN_INLINE_WORKERS=true` bo'lsa eski inline background loop ishlaydi. Docker production stackda `RUN_INLINE_WORKERS=false`, shuning uchun offline detector va cleanup faqat Celery orqali yuradi.

## Reading Processing Flow

```text
1. ESP32 sensorni o'qiydi
2. Firmware mode bo'yicha payload tayyorlaydi
3. Asosiy serverga HTTP POST qiladi
4. Asosiy server ishlamasa backup serverga yuboradi
5. Backend device va measurement pointni aniqlaydi
6. Payload utility type bo'yicha normalize qilinadi
7. Reading mos modelga saqlanadi
8. Alert service tekshiradi
9. Dashboardga real-time yoki polling orqali ma'lumot chiqadi
```

### Reading Validation

Backend ESP32 payloadlarini saqlashdan oldin fizik range bo'yicha tekshiradi:

- voltage/current/frequency/pf uchun maksimal/minimal guard
- energiya, bosim, flow, volume manfiy bo'lmasligi
- pressure qiymatlari `MAX_PRESSURE_BAR`dan oshmasligi
- temperature `MIN_TEMPERATURE_C` va `MAX_TEMPERATURE_C` oralig'ida bo'lishi

Noto'g'ri qiymat 422 bilan qaytariladi va DBga yozilmaydi. Eski elektr payloadlar buzilmasligi uchun optional fieldlar majburiy qilinmaydi.

## Alert Rules

### Elektr

- kuchlanish past
- kuchlanish yuqori
- chastota normadan tashqari
- quvvat oshib ketgan
- device offline

### Suv

- pastki bosim past
- yuqori bosim past
- pastda bosim bor, yuqorida yo'q
- pastki va yuqori bosim farqi katta
- flow yo'q
- device offline

### Gaz

- bosim past
- bosim yuqori
- leak detected
- valve error
- device offline

Bir xil `device_id + alert kind` bo'yicha ochiq alert `ALERT_DEDUPE_SEC` ichida qayta yaratilmaydi. Bu sensor bir xil muammoni har 30 sekundda yuborganda alert spam bo'lishining oldini oladi.

## Production Talablar

### Database

Boshlanishda SQLite ishlashi mumkin.

Production uchun:

- PostgreSQL
- Alembic migration
- indexes
- backup strategy
- reading retention policy

Docker production stack:

- `postgres:16-alpine`
- `redis:7-alpine`
- backend image `backend/Dockerfile` orqali build qilinadi
- FastAPI, Celery worker, Celery Beat va Flower bir xil backend image'dan ishlaydi
- backend `DATABASE_URL=postgresql+asyncpg://...` orqali ulanadi
- backend start vaqtida `alembic upgrade head` ishlaydi
- dependency install runtime startda emas, image build vaqtida bajariladi
- Mosquitto ishlatilmaydi

Local development:

- SQLite ishlashi mumkin
- Alembic migration temp/prod DBlar uchun ishlatiladi
- `init_db()` fallback development uchun saqlanadi

### Security

- JWT auth
- admin/user role
- admin user yaratadi, role/password/status update qiladi
- admin o'zini deaktiv qila olmaydi yoki o'z rolini pasaytira olmaydi
- ESP32 uchun device token
- API request signature yoki token
- OTA faqat admin uchun
- command faqat admin uchun
- CORS `CORS_ORIGINS` env orqali boshqariladi
- `TRUSTED_HOSTS` env orqali Host header himoyasi
- API va ESP32 endpointlari uchun alohida rate limit
- Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- `APP_ENV=production` bo'lsa default `SECRET_KEY`, `DEVICE_API_TOKEN`, `BOOTSTRAP_ADMIN_PASSWORD`, wildcard CORS/hosts bilan backend start bo'lmaydi

### Reliability

- ESP32 local queue
- HTTP retry
- multi-server fallback
- admin-triggered JSON gzip backup export
- duplicate reading protection
- Celery offline detector
- Celery Beat data cleanup
- Flower worker monitoring
- health endpoint
- readiness endpoint: `/ready`
- metrics endpoint: `/metrics` Prometheus text format
- request id: har response'da `X-Request-ID`
- access log: method, path, status, latency, request id
- audit logs

### Database Performance

Production querylar uchun alohida operational indexlar bor:

- device online/offline querylari: `is_active`, `last_seen`
- device filterlari: `utility_type`, `building_id`
- measurement point filterlari: `building_id`, `utility_type`, `role`
- reading analytics: `ts`, `building_id`, `utility_type`
- alert list/offline detector: `device_id`, `kind`, `cleared`, `ts`
- command polling: `device_id`, `status`, `id`
- OTA lookup: `active`, `uploaded`

### Backup API

- `POST /api/backups?reason=manual`: admin backup job yaratadi
- `GET /api/backups`: mavjud backup fayllar ro'yxati
- `GET /api/backups/tasks/{task_id}`: Celery task statusini ko'rsatadi
- `POST /api/backups/cleanup?keep_days=14`: cleanup job yaratadi
- `GET /api/backups/download/{filename}`: tayyor backup faylni yuklab beradi
- `DELETE /api/backups/{filename}`: backup faylni o'chiradi

Backup formati `meter-monitor-json-v1`. Har bir export ichida metadata, app version, jadval nomlari va jadval qatorlari JSON ko'rinishida saqlanadi, fayl gzip bilan siqiladi va SHA256 checksum qaytadi.
Retention `BACKUP_KEEP_DAYS` orqali boshqariladi.

### User Management API

- `GET /api/auth/users`: admin userlar ro'yxati
- `POST /api/auth/users`: yangi admin yoki oddiy user yaratish
- `GET /api/auth/users/{user_id}`: user profilini ko'rish
- `PUT /api/auth/users/{user_id}`: password, role, active status update

User update audit logga yoziladi, password qiymati audit detail ichiga yozilmaydi.

### Audit API

- `GET /api/audit-logs`: admin audit loglarni ko'radi
- filterlar: `action`, `entity_type`, `entity_id`, `username`, `user_id`, `since_ts`, `until_ts`
- pagination: `page`, `limit`
- retention: `AUDIT_KEEP_DAYS`

### Analytics

Kerakli analizlar:

- dom bo'yicha elektr sarfi
- suv pastki/yuqori bosim farqi
- yuqori qavatga suv chiqmagan vaqtlar
- gaz bosim stabil holati
- device offline statistikasi
- kunlik/haftalik/oylik trendlar

## Implementation Phases

### Phase 1 - Architecture Finalization

- Shu hujjatni to'g'rilash.
- Domain modelni yakunlash.
- API kontraktlarni yakunlash.
- ESP32 HTTP payload formatlarini yakunlash.

### Phase 2 - Backend Refactor

- `app.py`ni kichraytirish.
- models/schemas/repositories/services/routers ajratish.
- eski endpointlarni saqlash.
- SQLite schema yoki SQLAlchemy model yaratish.

### Phase 3 - HTTP ESP32 Framework

- umumiy ESP32 firmware core
- mode tanlash: electricity/water/gas
- multi-server HTTP fallback
- OTA
- hardware/software version
- local queue

### Phase 4 - Electricity Production

- mavjud elektr payloadni yangi modelga moslash
- TE71/TE73 reading processing
- alertlar
- command polling
- OTA

### Phase 5 - Water/Gas

- suv pastki/yuqori pressure sensor
- suv analytics
- gaz pressure sensor
- gaz alertlar

### Phase 6 - Admin Dashboard

- admin login
- oddiy user view-only
- domlar
- devices
- measurement points
- readings
- alerts
- OTA

Frontend auth:

- Login faqat username/password
- token `Authorization: Bearer ...` header bilan yuboriladi
- admin bo'lmagan userlarda command, edit, OTA upload, alert clear tugmalari ko'rinmaydi
- ESP32 endpointlari frontend tokeniga bog'lanmaydi, `X-Device-Token` orqali alohida himoyalanadi

## Compatibility Rules

Eski elektr ESP32lar uchun quyidagilar buzilmasligi kerak:

```text
POST /api/register
POST /api/readings
GET  /api/commands/{device_id}
POST /api/commands/{command_id}/ack
GET  /api/ota/check/{device_id}
```

Agar eski payloadda `utility_type` bo'lmasa:

```text
utility_type = electricity
```

Agar eski payloadda `measurement_point_id` bo'lmasa:

```text
backend device_id orqali pointni topadi
```

## Hozirgi Muhim Xulosa

Tizimning markazida `Building` turadi. Har bir buildingga elektr, suv va gaz modullari ulanadi. Har bir modulda sensorlar `MeasurementPoint` sifatida saqlanadi. Har bir ESP32 bitta umumiy firmware frameworkdan foydalanadi, lekin mode bo'yicha elektr, suv yoki gaz vazifasini bajaradi. Backend esa bitta bo'ladi va kelgan HTTP payloadni sensor turiga qarab mos modelga ajratadi.
