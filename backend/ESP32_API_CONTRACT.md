# ESP32 HTTP API Contract

Bu hujjat ESP32 unified firmware framework uchun backend HTTP contractidir. MQTT ishlatilmaydi.

## Auth

ESP32 endpointlari `X-Device-Token` header orqali himoyalanadi.

```http
X-Device-Token: <device-token>
```

Token tekshirish tartibi:

1. Agar device uchun per-device token bor bo'lsa, shu token ishlatiladi.
2. Aks holda global `DEVICE_API_TOKEN` provisioning/emergency token sifatida ishlaydi.
3. Birinchi install paytida admin yaratgan `provisioning_token` bilan `POST /api/register` chaqirilsa `X-Device-Token` shart emas.
4. Token noto'g'ri bo'lsa `401`.

Production tartib:

- Admin panel yoki API orqali bir martalik provisioning token yaratiladi.
- ESP32 birinchi marta shu token bilan register qiladi.
- Backend ESP32 uchun alohida `device_token` qaytaradi.
- ESP32 keyingi barcha requestlarda shu `device_token`ni `X-Device-Token` headerida yuboradi.

## Server Fallback

Firmware bir nechta server URL bilan ishlaydi:

- primary server: birinchi URL
- backup serverlar: keyingi URLlar

Yuborish algoritmi:

1. primary serverga HTTP request yuborish
2. timeout/network error/5xx bo'lsa keyingi serverga o'tish
3. `reading_id` ishlatilsa duplicate request backendda skip qilinadi

## Startup Flow

1. WiFi ulanadi.
2. ESP32 `GET /api/device-config/{device_id}` chaqiradi.
3. Agar registered bo'lmasa, `POST /api/register`.
4. Sensor mode bo'yicha telemetry yuboradi.
5. Periodik `POST /api/device-status`.
6. Periodik `GET /api/commands/{device_id}`.
7. Periodik `GET /api/ota/check/{device_id}?current_version=...`.

## Device Config

```http
GET /api/device-config/{device_id}
```

Response:

```json
{
  "device_id": "esp32-water-top-01",
  "registered": true,
  "firmware_mode": "water",
  "utility_type": "water",
  "device_role": "water_node",
  "building_id": 1,
  "measurement_point_id": 10,
  "hardware_version": "HW-1.0",
  "software_version": "1.0.0",
  "token_required": true,
  "intervals": {
    "telemetry_sec": 30,
    "status_sec": 60,
    "command_poll_sec": 10
  },
  "servers": [
    {"url": "https://main.example.uz", "priority": 1, "enabled": true},
    {"url": "https://backup.example.uz", "priority": 2, "enabled": true}
  ],
  "endpoints": {
    "register": "/api/register",
    "readings": "/api/readings",
    "status": "/api/device-status",
    "commands": "/api/commands/esp32-water-top-01",
    "ota_check": "/api/ota/check/esp32-water-top-01"
  }
}
```

## Register

```http
POST /api/register
```

Payload:

```json
{
  "device_id": "esp32-water-top-01",
  "name": "Top water pressure",
  "utility_type": "water",
  "device_role": "water_node",
  "firmware_mode": "water",
  "hardware_version": "HW-1.0",
  "software_version": "1.0.0",
  "build_number": "2026.07.06.1",
  "chip_model": "ESP32-WROOM",
  "rssi": -61,
  "ip": "192.168.1.50",
  "building_id": 1,
  "point_id": 10
}
```

Provisioning bilan birinchi register:

```json
{
  "device_id": "esp32-water-top-01",
  "provisioning_token": "one-time-token",
  "hardware_version": "HW-1.0",
  "software_version": "1.0.0",
  "build_number": "2026.07.06.1",
  "chip_model": "ESP32-WROOM"
}
```

Provisioning response:

```json
{
  "ok": true,
  "device_id": "esp32-water-top-01",
  "provisioned": true,
  "device_token": "per-device-token",
  "token_type": "device"
}
```

`device_token` faqat shu response’da ochiq qaytadi. ESP32 uni NVS/flash ichida saqlab, keyingi `readings`, `status`, `commands`, `ota` requestlarida ishlatadi.

## Reading

```http
POST /api/readings
```

Common fields:

```json
{
  "device_id": "esp32-water-top-01",
  "reading_id": "esp32-water-top-01-000001",
  "sequence_no": 1,
  "building_id": 1,
  "point_id": 10,
  "utility_type": "water",
  "sensor_type": "pressure_4_20ma",
  "hardware_version": "HW-1.0",
  "software_version": "1.0.0"
}
```

Elektr fields:

```json
{
  "utility_type": "electricity",
  "voltage_l1": 221.4,
  "voltage_l2": 222.1,
  "voltage_l3": 220.7,
  "current_l1": 12.3,
  "current_l2": 11.9,
  "current_l3": 12.1,
  "power_w": 7800,
  "power_var": 120,
  "frequency": 50.01,
  "pf": 0.98,
  "energy_kwh": 1834.55,
  "energy_t1": 900.1,
  "energy_t2": 600.2,
  "energy_t3": 300.3,
  "energy_t4": 34.0,
  "relay_on": true
}
```

Suv fields:

```json
{
  "utility_type": "water",
  "pressure_bar": 2.1,
  "pressure_bottom_bar": 2.4,
  "pressure_top_bar": 0.8,
  "flow_rate": 1.2,
  "volume_m3": 129.4,
  "temperature_c": 18.5,
  "leak_detected": false,
  "valve_open": true
}
```

Gaz fields:

```json
{
  "utility_type": "gas",
  "pressure_bar": 0.18,
  "flow_rate": 0.4,
  "volume_m3": 350.2,
  "temperature_c": 20.1,
  "leak_detected": false,
  "valve_open": true
}
```

Validation:

- `device_id` majburiy.
- Optional fieldlar yuborilmasa xato emas.
- Fizik range buzilsa `422`.
- `reading_id` duplicate bo'lsa backend qayta yozmaydi.

## Batch Reading

```http
POST /api/readings/batch
```

Payload:

```json
{
  "device_id": "esp32-water-top-01",
  "readings": [
    {
      "device_id": "esp32-water-top-01",
      "reading_id": "esp32-water-top-01-000001",
      "utility_type": "water",
      "pressure_bar": 2.1
    }
  ]
}
```

Response:

```json
{
  "ok": true,
  "accepted": 1,
  "skipped": 0,
  "errors": [],
  "timestamps": [1783340000]
}
```

## Device Status

```http
POST /api/device-status
```

Payload:

```json
{
  "device_id": "esp32-water-top-01",
  "ip": "192.168.1.50",
  "rssi": -61,
  "online": true,
  "hardware_version": "HW-1.0",
  "software_version": "1.0.0",
  "firmware_mode": "water",
  "build_number": "2026.07.06.1"
}
```

## Commands

```http
GET /api/commands/{device_id}
POST /api/commands/{command_id}/ack?result=ok
```

Poll response:

```json
{
  "commands": [
    {
      "id": 12,
      "action": "reboot",
      "param": null,
      "expires_at": 1783343600,
      "attempts": 1,
      "max_attempts": 3
    }
  ]
}
```

Known actions:

- `reboot`
- `ota_check`
- `relay_on`
- `relay_off`

## OTA

```http
GET /api/ota/check/{device_id}?current_version=1.0.0
GET /api/ota/firmware/{filename}?device_id={device_id}
```

Update response:

```json
{
  "update": true,
  "version": "2.0.0",
  "hardware_version": "HW-1.0",
  "firmware_mode": "water",
  "utility_type": "water",
  "device_role": "water_node",
  "sensor_type": "pressure_4_20ma",
  "converter_type": "ADS1115",
  "url": "/api/ota/firmware/water_water_water_node_HW-1.0_pressure_4_20ma_ADS1115_2.0.0.bin?device_id=esp32-water-top-01",
  "size": 902144,
  "sha256": "..."
}
```

No update response:

```json
{"update": false}
```

## Status Codes

- `200`: success
- `400`: bad command or wrong request semantics
- `401`: token missing/wrong
- `403`: admin permission required
- `404`: resource not found
- `422`: validation/range error
- `429`: rate limit or pending command limit
- `500/502/503`: retry on backup server
