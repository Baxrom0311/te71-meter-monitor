# WebSocket Contract

Frontend WebSocketdan real-time signal layer sifatida foydalanadi. Initial ma'lumotlar HTTP orqali olinadi, WebSocket esa React Query cache'ni yangilaydi yoki kerakli querylarni invalidate qiladi.

Endpoint:

```text
WS /ws?token=<access_token>
```

Token oddiy login orqali olingan JWT access token bo'lishi kerak. Token noto'g'ri yoki muddati tugagan bo'lsa server connectionni `1008` code bilan yopadi.

## Frontend Cache Qoidasi

Frontendda global `RealtimeSync` listener ishlaydi:

- `snapshot`: devices va alerts cache'ni boshlang'ich ma'lumot bilan to'ldiradi.
- `status`, `device_online`, `device_offline`: device online/last_seen cache'ni yangilaydi.
- `device_updated`: devices, single device va summary querylarni invalidate qiladi.
- `reading`: latest reading cache'ni yangilaydi, history/hourly/summary querylarni invalidate qiladi.
- `readings_batch`: devices, summary va hourly stats querylarni invalidate qiladi.
- `alert`, `alert_notification`: alerts va summary querylarni invalidate qiladi.
- `firmware`: firmware va OTA batch cache'larini invalidate qiladi.
- `ota_batch`, `ota_report`: firmware/OTA batch cache'larini invalidate qiladi.

Polling real-time uchun asosiy mexanizm emas. Muhim querylarda polling 5 daqiqalik fallback sifatida qoldirilgan. OTA batch query ham WebSocket eventlar bilan yangilanadi, 60 soniyalik refresh faqat xavfsizlik fallbackidir.

## Eventlar

### `snapshot`

Client WebSocketga ulanganda server yuboradi.

```json
{
  "type": "snapshot",
  "data": {
    "devices": [],
    "alerts": []
  }
}
```

Frontend ta'siri:

| Cache | Amal |
|---|---|
| `["devices", ...]` | agar cache bo'sh bo'lsa to'ldiriladi |
| `["alerts", ...]` | agar cache bo'sh bo'lsa to'ldiriladi |
| `["summary"]` | invalidate |

### `device_online`

Qurilma register bo'lganda yoki serverga online signal berganda yuboriladi.

```json
{
  "type": "device_online",
  "device_id": "F42DC96D5820",
  "utility_type": "electricity",
  "firmware_mode": "electricity"
}
```

Frontend ta'siri:

| Cache | Amal |
|---|---|
| `["devices", ...]` | mos device `online=true`, `last_seen=now` |
| `["device", device_id]` | mos device `online=true`, `last_seen=now` |
| `["summary"]` | invalidate |

### `device_updated`

Admin device yaratganda yoki sozlamalarini o'zgartirganda yuboriladi.

```json
{
  "type": "device_updated",
  "event": "created",
  "device_id": "F42DC96D5820"
}
```

Frontend ta'siri:

| Cache | Amal |
|---|---|
| `["devices", ...]` | invalidate |
| `["device", device_id]` | invalidate |
| `["summary"]` | invalidate |

### `device_offline`

Qurilma offline deb topilganda yuborilishi mumkin.

```json
{
  "type": "device_offline",
  "device_id": "F42DC96D5820"
}
```

Frontend ta'siri:

| Cache | Amal |
|---|---|
| `["devices", ...]` | mos device `online=false` |
| `["device", device_id]` | mos device `online=false` |
| `["summary"]` | invalidate |

### `status`

ESP32 `/api/device-status` yuborganda backend broadcast qiladi.

```json
{
  "type": "status",
  "device_id": "F42DC96D5820",
  "online": true
}
```

Frontend ta'siri:

| Cache | Amal |
|---|---|
| `["devices", ...]` | mos device `online=<online>`, online bo'lsa `last_seen=now` |
| `["device", device_id]` | mos device update |
| `["summary"]` | invalidate |

### `reading`

ESP32 bitta reading yuborganda backend broadcast qiladi.

```json
{
  "type": "reading",
  "device_id": "F42DC96D5820",
  "ts": 1783535127,
  "data": {
    "device_id": "F42DC96D5820",
    "utility_type": "electricity",
    "voltage_l1": 224.5,
    "power_w": 518.7,
    "energy_kwh": 1234.56
  }
}
```

Suv reading namunasi:

```json
{
  "type": "reading",
  "device_id": "WATER-01",
  "ts": 1783535127,
  "data": {
    "device_id": "WATER-01",
    "utility_type": "water",
    "pressure_bottom_bar": 2.1,
    "pressure_top_bar": 1.4,
    "flow_rate": 0.8
  }
}
```

Gaz reading namunasi:

```json
{
  "type": "reading",
  "device_id": "GAS-01",
  "ts": 1783535127,
  "data": {
    "device_id": "GAS-01",
    "utility_type": "gas",
    "pressure_bar": 0.04,
    "flow_rate": 0.2
  }
}
```

Frontend ta'siri:

| Cache | Amal |
|---|---|
| `["devices", ...]` | mos device online/last_seen update |
| `["device", device_id]` | online/last_seen update |
| `["device-latest", device_id]` | latest reading bevosita cache'ga yoziladi |
| `["device-history", device_id, ...]` | invalidate |
| `["hourly-stats", ...]` | invalidate |
| `["summary"]` | invalidate |

### `readings_batch`

ESP32 queued/batch reading yuborganda backend broadcast qiladi.

```json
{
  "type": "readings_batch",
  "device_id": "F42DC96D5820",
  "result": {
    "ok": true,
    "saved": 10,
    "skipped": 0
  }
}
```

Frontend ta'siri:

| Cache | Amal |
|---|---|
| `["devices", ...]` | invalidate |
| `["summary"]` | invalidate |
| `["hourly-stats", ...]` | invalidate |

### `alert` va `alert_notification`

Alert yaratilganda yoki notification/escalation eventida yuboriladi.

Reading alert namunasi:

```json
{
  "type": "alert",
  "kind": "offline",
  "severity": "warning",
  "utility_type": "electricity",
  "device_id": "F42DC96D5820",
  "message": "F42DC96D5820 offline"
}
```

Alert clear namunasi:

```json
{
  "type": "alert",
  "event": "cleared",
  "alert_id": 15
}
```

Clear-all namunasi:

```json
{
  "type": "alert",
  "event": "cleared_all",
  "device_id": "F42DC96D5820"
}
```

Notification event namunasi:

```json
{
  "type": "alert_notification",
  "status": "sent",
  "notification": {
    "alert_id": 1,
    "device_id": "F42DC96D5820",
    "severity": "critical",
    "kind": "voltage_high"
  }
}
```

Frontend ta'siri:

| Cache | Amal |
|---|---|
| `["alerts", ...]` | invalidate |
| `["summary"]` | invalidate |

### `firmware`

Firmware upload yoki delete qilinganda backend broadcast qiladi.

```json
{
  "type": "firmware",
  "event": "uploaded",
  "firmware_id": 4,
  "firmware": {
    "id": 4,
    "version": "3.4.0",
    "firmware_mode": "electricity",
    "utility_type": "electricity",
    "active": true
  }
}
```

```json
{
  "type": "firmware",
  "event": "deleted",
  "firmware_id": 4
}
```

Frontend ta'siri:

| Cache | Amal |
|---|---|
| `["firmware"]` | invalidate |
| `["ota-batches"]` | invalidate |

### `ota_batch`

OTA batch yaratilganda, process qilinganda, cancel bo'lganda yoki device OTA report yuborganda backend broadcast qiladi.

Batch yaratish namunasi:

```json
{
  "type": "ota_batch",
  "event": "created",
  "batch_id": 12,
  "batch": {
    "id": 12,
    "name": "Elektr stable rollout",
    "firmware_id": 4,
    "status": "pending",
    "total_devices": 24,
    "progress_percentage": 0
  }
}
```

Process/cancel/report eventlari:

```json
{
  "type": "ota_batch",
  "event": "processed",
  "batch_id": 12,
  "queued": 10,
  "skipped": 0,
  "remaining": 14,
  "retry_reset": 0,
  "retry_skipped": 0
}
```

```json
{
  "type": "ota_batch",
  "event": "cancelled",
  "batch_id": 12,
  "status": "cancelled"
}
```

Frontend ta'siri:

| Cache | Amal |
|---|---|
| `["ota-batches"]` | invalidate |
| `["firmware"]` | invalidate |

### `ota_report`

ESP32 OTA install holatini `/api/ota/report` orqali yuborganda broadcast qilinadi.

```json
{
  "type": "ota_report",
  "event_id": 44,
  "batch_id": 12,
  "device_id": "F42DC96D5820",
  "firmware_id": 4,
  "status": "success",
  "target_version": "3.4.0",
  "ts": 1783535127
}
```

Frontend ta'siri:

| Cache | Amal |
|---|---|
| `["ota-batches"]` | invalidate |
| `["firmware"]` | invalidate |
| `["devices", ...]` | invalidate |
| `["device", device_id]` | invalidate |

## Event Qo'shish Qoidasi

Yangi WebSocket event qo'shilsa:

1. Backend event payloadini shu hujjatga yozish.
2. `meter-frontend/src/types/api.ts` ichidagi `WebSocketMessage.type` unioniga qo'shish.
3. `meter-frontend/src/components/RealtimeSync.tsx` ichida cache update/invalidate qoidasini qo'shish.
4. Agar event dashboardda ko'rinishi kerak bo'lsa, tegishli query keyni invalidate qilish yoki `setQueryData` bilan bevosita update qilish.
