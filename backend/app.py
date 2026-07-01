"""
Meter Monitor Backend — v3
FastAPI + SQLite + WebSocket + MQTT

Endpoints:
  POST /api/register                   — ESP32 auto-registration
  POST /api/readings                   — ESP32 readings (HTTP fallback)
  GET  /api/devices                    — List devices (?online=true&type=TE71&group=X)
  GET  /api/devices/{id}               — Single device info
  PUT  /api/devices/{id}               — Update name/location/group
  GET  /api/devices/{id}/latest        — Latest reading
  GET  /api/devices/{id}/history       — Paginated history (?page=1&limit=100&hours=24)
  GET  /api/devices/{id}/stats         — Hourly aggregates for charts (?hours=24)
  GET  /api/devices/{id}/export        — CSV export (?hours=24)
  POST /api/devices/{id}/relay         — Relay on/off (MQTT + HTTP queue)
  POST /api/devices/{id}/reboot        — Reboot device via MQTT
  GET  /api/commands/{id}              — ESP32 polls commands
  POST /api/commands/{id}/ack          — ESP32 acks command
  GET  /api/alerts                     — Voltage/offline alerts (?device_id=X&limit=50)
  POST /api/alerts/{id}/clear          — Clear single alert
  POST /api/ota/upload                 — Upload firmware .bin
  GET  /api/ota/list                   — All firmware versions
  DELETE /api/ota/{id}                 — Delete firmware version
  GET  /api/ota/check/{device_id}      — ESP32 checks for update
  GET  /api/ota/firmware/{fname}       — Download firmware
  POST /api/ota/push/{device_id}       — Push OTA to device via MQTT
  GET  /api/summary                    — Dashboard overview stats
  WS   /ws                             — Real-time browser push
  GET  /health                         — System health
"""

import asyncio, csv, io, os, time, hashlib, json, logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import aiosqlite
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH        = Path(os.getenv("DB_PATH",        "data/meters.db"))
OTA_DIR        = Path(os.getenv("OTA_DIR",        "firmware"))
STATIC_DIR     = Path(os.getenv("STATIC_DIR",     "../frontend"))
MQTT_HOST      = os.getenv("MQTT_HOST",  "localhost")
MQTT_PORT      = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER      = os.getenv("MQTT_USER",  "")
MQTT_PASS      = os.getenv("MQTT_PASS",  "")
OFFLINE_SEC    = int(os.getenv("OFFLINE_SEC",   "120"))   # 2 daqiqa javob bermasа offline
DATA_KEEP_DAYS = int(os.getenv("DATA_KEEP_DAYS", "30"))   # 30 kundan eski ma'lumot o'chadi

V_MIN, V_MAX   = 195.0, 253.0   # Kuchlanish normal diapazoni

for d in [DB_PATH.parent, OTA_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ── WebSocket Manager ─────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self._sockets: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._sockets.append(ws)
        # Yangi ulanishga hozirgi holat yuboriladi
        try:
            snapshot = await _build_snapshot()
            await ws.send_text(json.dumps({"type": "snapshot", "data": snapshot}))
        except Exception:
            pass

    def disconnect(self, ws: WebSocket):
        if ws in self._sockets:
            self._sockets.remove(ws)

    async def broadcast(self, data: dict):
        if not self._sockets:
            return
        msg  = json.dumps(data, ensure_ascii=False)
        dead = []
        for ws in self._sockets:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def count(self):
        return len(self._sockets)


ws_manager = ConnectionManager()


async def _build_snapshot() -> dict:
    """Browser ulanganida yuboriluvchi to'liq holat."""
    n = now_ts()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM devices WHERE is_active=1") as cur:
            devs = [dict(r) for r in await cur.fetchall()]
        async with db.execute("SELECT * FROM alerts ORDER BY ts DESC LIMIT 20") as cur:
            alerts = [dict(r) for r in await cur.fetchall()]
    for d in devs:
        d["online"] = (n - (d.get("last_seen") or 0)) < OFFLINE_SEC
    return {"devices": devs, "alerts": alerts}


# ── DB Init ───────────────────────────────────────────────────────────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS devices (
            id           TEXT PRIMARY KEY,
            name         TEXT,
            meter_type   TEXT DEFAULT 'unknown',
            meter_serial TEXT,
            baud_rate    INTEGER DEFAULT 9600,
            chip_model   TEXT,
            rssi         INTEGER,
            ip           TEXT,
            fw_version   TEXT,
            building     TEXT,
            floor        TEXT,
            room         TEXT,
            group_name   TEXT,
            is_active    INTEGER DEFAULT 1,
            last_seen    INTEGER,
            registered   INTEGER
        );

        CREATE TABLE IF NOT EXISTS readings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id   TEXT NOT NULL,
            ts          INTEGER NOT NULL,
            voltage_l1  REAL, voltage_l2  REAL, voltage_l3  REAL,
            current_l1  REAL, current_l2  REAL, current_l3  REAL,
            power_w     REAL, power_var   REAL,
            frequency   REAL, pf          REAL,
            energy_kwh  REAL,
            energy_t1   REAL, energy_t2   REAL,
            energy_t3   REAL, energy_t4   REAL,
            relay_on    INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_rd ON readings(device_id, ts DESC);

        CREATE TABLE IF NOT EXISTS commands (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id  TEXT NOT NULL,
            action     TEXT NOT NULL,
            param      TEXT,
            created    INTEGER,
            acked      INTEGER,
            ack_result TEXT
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            ts        INTEGER NOT NULL,
            kind      TEXT NOT NULL,   -- overvoltage | undervoltage | offline | frequency
            value     REAL,
            message   TEXT,
            cleared   INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS firmware (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            version  TEXT NOT NULL,
            size     INTEGER,
            sha256   TEXT,
            uploaded INTEGER,
            active   INTEGER DEFAULT 0,
            notes    TEXT
        );
        """)
        await db.commit()

        # Migration: yangi ustunlar
        for table, col, typ in [
            ("devices",  "meter_serial", "TEXT"),
            ("devices",  "baud_rate",    "INTEGER DEFAULT 9600"),
            ("devices",  "chip_model",   "TEXT"),
            ("devices",  "rssi",         "INTEGER"),
            ("devices",  "building",     "TEXT"),
            ("devices",  "floor",        "TEXT"),
            ("devices",  "room",         "TEXT"),
            ("devices",  "group_name",   "TEXT"),
            ("devices",  "is_active",    "INTEGER DEFAULT 1"),
            ("alerts",   "cleared",      "INTEGER DEFAULT 0"),
            ("firmware", "notes",        "TEXT"),
        ]:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
                await db.commit()
            except Exception:
                pass


# ── Background Tasks ──────────────────────────────────────────────────────────
async def offline_detector():
    """Har 60s da qurilmalar online/offline holatini tekshiradi."""
    await asyncio.sleep(30)   # startup delay
    while True:
        try:
            n = now_ts()
            cutoff = n - OFFLINE_SEC
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                # Oxirgi OFFLINE_SEC*2 da ko'ringan lekin endi ko'rinmayotganlar
                async with db.execute(
                    "SELECT id,name FROM devices WHERE is_active=1 AND last_seen BETWEEN ? AND ?",
                    (cutoff - OFFLINE_SEC, cutoff)
                ) as cur:
                    offline_devs = await cur.fetchall()

                for dev in offline_devs:
                    did   = dev["id"]
                    dname = dev["name"] or did
                    # Bir soat ichida offline alert bor emasmi?
                    async with db.execute(
                        "SELECT id FROM alerts WHERE device_id=? AND kind='offline' AND ts>?",
                        (did, n - 3600)
                    ) as cur:
                        exists = await cur.fetchone()
                    if not exists:
                        await db.execute(
                            "INSERT INTO alerts (device_id,ts,kind,message) VALUES (?,?,?,?)",
                            (did, n, "offline", f"{dname} offline bo'ldi")
                        )
                        await ws_manager.broadcast({
                            "type": "alert",
                            "kind": "offline",
                            "device_id": did,
                            "message": f"{dname} offline"
                        })
                if offline_devs:
                    await db.commit()
        except Exception as e:
            logger.warning(f"offline_detector error: {e}")
        await asyncio.sleep(60)


async def data_cleanup():
    """Har kecha yarimi eski ma'lumotlarni o'chiradi (DATA_KEEP_DAYS kundan eski)."""
    await asyncio.sleep(10)
    while True:
        try:
            cutoff = now_ts() - DATA_KEEP_DAYS * 86400
            async with aiosqlite.connect(DB_PATH) as db:
                r = await db.execute("DELETE FROM readings WHERE ts < ?", (cutoff,))
                deleted = r.rowcount
                await db.execute("DELETE FROM alerts WHERE ts < ? AND cleared=1", (cutoff,))
                await db.commit()
            if deleted:
                logger.info(f"Cleanup: {deleted} eski o'qish o'chirildi")
        except Exception as e:
            logger.warning(f"data_cleanup error: {e}")
        await asyncio.sleep(86400)   # 24 soatda bir


async def mqtt_service():
    """ESP32 dan MQTT telemetriyasini qabul qiladi."""
    try:
        import aiomqtt
    except ImportError:
        logger.warning("aiomqtt o'rnatilmagan — MQTT qabul o'chirilgan")
        return

    while True:
        try:
            kwargs = {"hostname": MQTT_HOST, "port": MQTT_PORT}
            if MQTT_USER:
                kwargs["username"] = MQTT_USER
                kwargs["password"] = MQTT_PASS
            async with aiomqtt.Client(**kwargs) as client:
                logger.info(f"MQTT ulandi: {MQTT_HOST}:{MQTT_PORT}")
                await client.subscribe("meters/+/telemetry")
                await client.subscribe("meters/+/status")

                async for msg in client.messages:
                    parts = str(msg.topic).split("/")
                    if len(parts) < 3:
                        continue
                    device_id, kind = parts[1], parts[2]
                    try:
                        payload = json.loads(msg.payload)
                    except Exception:
                        continue

                    if kind == "telemetry":
                        r = MeterReading(device_id=device_id, **{
                            k: payload.get(k)
                            for k in MeterReading.model_fields
                            if k != "device_id"
                        })
                        ts = await _save_reading(r)
                        await ws_manager.broadcast({
                            "type": "reading",
                            "device_id": device_id,
                            "ts": ts,
                            "data": payload
                        })
                    elif kind == "status":
                        async with aiosqlite.connect(DB_PATH) as db:
                            await db.execute(
                                "UPDATE devices SET last_seen=?,ip=COALESCE(?,ip),rssi=COALESCE(?,rssi) WHERE id=?",
                                (now_ts(), payload.get("ip"), payload.get("rssi"), device_id)
                            )
                            await db.commit()
                        await ws_manager.broadcast({
                            "type": "status",
                            "device_id": device_id,
                            "online": payload.get("online", True),
                            "ip": payload.get("ip"),
                            "rssi": payload.get("rssi")
                        })
        except Exception as e:
            logger.warning(f"MQTT xato: {e}. 5s dan keyin qayta ulanadi...")
            await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    asyncio.create_task(mqtt_service())
    asyncio.create_task(offline_detector())
    asyncio.create_task(data_cleanup())
    yield


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Meter Monitor", version="3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return HTMLResponse(idx.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Meter Monitor v3</h1>")


def now_ts() -> int:
    return int(time.time())


# ── Schemas ───────────────────────────────────────────────────────────────────
class DeviceRegister(BaseModel):
    device_id:    str
    name:         Optional[str]   = None
    meter_type:   Optional[str]   = "unknown"
    meter_serial: Optional[str]   = None
    baud_rate:    Optional[int]   = 9600
    chip_model:   Optional[str]   = None
    rssi:         Optional[int]   = None
    fw_version:   Optional[str]   = None
    ip:           Optional[str]   = None

class DeviceUpdate(BaseModel):
    name:       Optional[str]  = None
    building:   Optional[str]  = None
    floor:      Optional[str]  = None
    room:       Optional[str]  = None
    group_name: Optional[str]  = None
    is_active:  Optional[bool] = None

class MeterReading(BaseModel):
    device_id:  str
    fw_version: Optional[str]   = None
    voltage_l1: Optional[float] = None
    voltage_l2: Optional[float] = None
    voltage_l3: Optional[float] = None
    current_l1: Optional[float] = None
    current_l2: Optional[float] = None
    current_l3: Optional[float] = None
    power_w:    Optional[float] = None
    power_var:  Optional[float] = None
    frequency:  Optional[float] = None
    pf:         Optional[float] = None
    energy_kwh: Optional[float] = None
    energy_t1:  Optional[float] = None
    energy_t2:  Optional[float] = None
    energy_t3:  Optional[float] = None
    energy_t4:  Optional[float] = None
    relay_on:   Optional[bool]  = None

class RelayCommand(BaseModel):
    action: str   # "on" | "off"


# ── Helpers ───────────────────────────────────────────────────────────────────
async def _check_alerts(db, device_id: str, r: MeterReading):
    ts = now_ts()
    for ph, v in [("L1", r.voltage_l1), ("L2", r.voltage_l2), ("L3", r.voltage_l3)]:
        if v is None:
            continue
        if v < V_MIN or v > V_MAX:
            kind = "overvoltage" if v > V_MAX else "undervoltage"
            msg  = f"{ph}: {v:.1f}V"
            await db.execute(
                "INSERT INTO alerts (device_id,ts,kind,value,message) VALUES (?,?,?,?,?)",
                (device_id, ts, kind, v, msg)
            )
            await ws_manager.broadcast({
                "type": "alert", "kind": kind,
                "device_id": device_id, "message": msg
            })
    # Chastota tekshiruvi (49–51 Hz)
    if r.frequency and (r.frequency < 49.0 or r.frequency > 51.0):
        await db.execute(
            "INSERT INTO alerts (device_id,ts,kind,value,message) VALUES (?,?,?,?,?)",
            (device_id, ts, "frequency", r.frequency, f"Chastota: {r.frequency:.2f}Hz")
        )


async def _save_reading(body: MeterReading) -> int:
    ts    = now_ts()
    relay = int(body.relay_on) if body.relay_on is not None else None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE devices SET last_seen=?,fw_version=COALESCE(?,fw_version) WHERE id=?",
            (ts, body.fw_version, body.device_id)
        )
        await db.execute("""
            INSERT INTO readings
              (device_id,ts,
               voltage_l1,voltage_l2,voltage_l3,
               current_l1,current_l2,current_l3,
               power_w,power_var,frequency,pf,
               energy_kwh,energy_t1,energy_t2,energy_t3,energy_t4,relay_on)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (body.device_id, ts,
              body.voltage_l1, body.voltage_l2, body.voltage_l3,
              body.current_l1, body.current_l2, body.current_l3,
              body.power_w, body.power_var, body.frequency, body.pf,
              body.energy_kwh, body.energy_t1, body.energy_t2,
              body.energy_t3, body.energy_t4, relay))
        await _check_alerts(db, body.device_id, body)
        await db.commit()
    return ts


async def _mqtt_pub(topic: str, payload: str):
    try:
        import aiomqtt
        kwargs = {"hostname": MQTT_HOST, "port": MQTT_PORT}
        if MQTT_USER:
            kwargs["username"] = MQTT_USER
            kwargs["password"] = MQTT_PASS
        async with aiomqtt.Client(**kwargs) as c:
            await c.publish(topic, payload.encode())
    except Exception as e:
        logger.warning(f"MQTT publish xato ({topic}): {e}")


# ── Routes ────────────────────────────────────────────────────────────────────

# WebSocket
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()   # keep-alive
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


# Registration
@app.post("/api/register")
async def register_device(body: DeviceRegister):
    ts = now_ts()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO devices
              (id,name,meter_type,meter_serial,baud_rate,chip_model,rssi,fw_version,ip,last_seen,registered)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                meter_type   = COALESCE(excluded.meter_type,   meter_type),
                meter_serial = COALESCE(excluded.meter_serial, meter_serial),
                baud_rate    = COALESCE(excluded.baud_rate,    baud_rate),
                chip_model   = COALESCE(excluded.chip_model,   chip_model),
                rssi         = excluded.rssi,
                fw_version   = COALESCE(excluded.fw_version,   fw_version),
                ip           = COALESCE(excluded.ip,           ip),
                last_seen    = excluded.last_seen
        """, (body.device_id, body.name or body.device_id,
              body.meter_type, body.meter_serial, body.baud_rate,
              body.chip_model, body.rssi, body.fw_version, body.ip, ts, ts))
        await db.commit()
    await ws_manager.broadcast({
        "type": "device_online",
        "device_id": body.device_id,
        "meter_type": body.meter_type,
        "meter_serial": body.meter_serial
    })
    return {"ok": True}


# Device list (filter qo'llab-quvvatlaydi)
@app.get("/api/devices")
async def list_devices(
    online:  Optional[bool] = None,
    type:    Optional[str]  = None,
    group:   Optional[str]  = None,
    building:Optional[str]  = None,
):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM devices WHERE is_active=1 ORDER BY last_seen DESC"
        ) as cur:
            rows = await cur.fetchall()

    n = now_ts()
    result = []
    for r in rows:
        d = dict(r)
        d["online"] = (n - (d.get("last_seen") or 0)) < OFFLINE_SEC
        if online  is not None and d["online"] != online:      continue
        if type    and d.get("meter_type") != type:            continue
        if group   and d.get("group_name") != group:           continue
        if building and d.get("building") != building:         continue
        result.append(d)
    return {"devices": result, "total": len(result)}


# Single device
@app.get("/api/devices/{device_id}")
async def get_device(device_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM devices WHERE id=?", (device_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Qurilma topilmadi")
    d = dict(row)
    d["online"] = (now_ts() - (d.get("last_seen") or 0)) < OFFLINE_SEC
    return d


# Update device
@app.put("/api/devices/{device_id}")
async def update_device(device_id: str, body: DeviceUpdate):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "Yangilanadigan maydon yo'q")
    if "is_active" in fields:
        fields["is_active"] = int(fields["is_active"])
    clause = ", ".join(f"{k}=?" for k in fields)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE devices SET {clause} WHERE id=?",
                         list(fields.values()) + [device_id])
        await db.commit()
    return {"ok": True}


# Latest reading
@app.get("/api/devices/{device_id}/latest")
async def device_latest(device_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM readings WHERE device_id=? ORDER BY ts DESC LIMIT 1",
            (device_id,)
        ) as cur:
            row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Ma'lumot yo'q")
    return dict(row)


# Paginated history
@app.get("/api/devices/{device_id}/history")
async def device_history(
    device_id: str,
    page:  int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
    hours: Optional[int] = None,
):
    offset = (page - 1) * limit
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if hours:
            cutoff = now_ts() - hours * 3600
            q = "SELECT * FROM readings WHERE device_id=? AND ts>? ORDER BY ts DESC LIMIT ? OFFSET ?"
            p = (device_id, cutoff, limit, offset)
            async with db.execute(
                "SELECT COUNT(*) FROM readings WHERE device_id=? AND ts>?", (device_id, cutoff)
            ) as cur:
                total = (await cur.fetchone())[0]
        else:
            q = "SELECT * FROM readings WHERE device_id=? ORDER BY ts DESC LIMIT ? OFFSET ?"
            p = (device_id, limit, offset)
            async with db.execute(
                "SELECT COUNT(*) FROM readings WHERE device_id=?", (device_id,)
            ) as cur:
                total = (await cur.fetchone())[0]
        async with db.execute(q, p) as cur:
            rows = await cur.fetchall()
    return {
        "readings": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }


# Hourly stats for charts
@app.get("/api/devices/{device_id}/stats")
async def device_stats(device_id: str, hours: int = Query(24, ge=1, le=720)):
    cutoff = now_ts() - hours * 3600
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT
                (ts / 3600) * 3600          AS hour_ts,
                ROUND(AVG(voltage_l1),1)    AS avg_v1,
                ROUND(MIN(voltage_l1),1)    AS min_v1,
                ROUND(MAX(voltage_l1),1)    AS max_v1,
                ROUND(AVG(voltage_l2),1)    AS avg_v2,
                ROUND(AVG(voltage_l3),1)    AS avg_v3,
                ROUND(AVG(current_l1),3)    AS avg_i1,
                ROUND(AVG(current_l2),3)    AS avg_i2,
                ROUND(AVG(current_l3),3)    AS avg_i3,
                ROUND(AVG(power_w),0)       AS avg_pw,
                ROUND(MAX(power_w),0)       AS max_pw,
                ROUND(AVG(frequency),2)     AS avg_freq,
                ROUND(AVG(pf),3)            AS avg_pf,
                ROUND(MAX(energy_kwh),3)    AS energy_kwh,
                COUNT(*)                    AS samples
            FROM readings
            WHERE device_id=? AND ts>?
            GROUP BY hour_ts
            ORDER BY hour_ts
        """, (device_id, cutoff)) as cur:
            rows = await cur.fetchall()
    return {"stats": [dict(r) for r in rows], "hours": hours}


# CSV export
@app.get("/api/devices/{device_id}/export")
async def export_csv(device_id: str, hours: int = Query(24, ge=1, le=720)):
    cutoff = now_ts() - hours * 3600
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM readings WHERE device_id=? AND ts>? ORDER BY ts",
            (device_id, cutoff)
        ) as cur:
            rows = await cur.fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    if rows:
        writer.writerow(rows[0].keys())
        for r in rows:
            writer.writerow(r)

    fname = f"{device_id.replace(':','')}_{hours}h.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )


# Dashboard summary
@app.get("/api/summary")
async def summary():
    n = now_ts()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT COUNT(*) FROM devices WHERE is_active=1") as cur:
            total = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM devices WHERE is_active=1 AND last_seen>?",
            (n - OFFLINE_SEC,)
        ) as cur:
            online = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM alerts WHERE cleared=0 AND ts>?",
            (n - 86400,)
        ) as cur:
            active_alerts = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM readings WHERE ts>?", (n - 3600,)
        ) as cur:
            reads_last_hour = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT SUM(energy_kwh) FROM (SELECT MAX(energy_kwh) as energy_kwh FROM readings GROUP BY device_id)"
        ) as cur:
            total_energy = (await cur.fetchone())[0] or 0
    return {
        "devices_total":    total,
        "devices_online":   online,
        "devices_offline":  total - online,
        "alerts_active":    active_alerts,
        "reads_last_hour":  reads_last_hour,
        "total_energy_kwh": round(total_energy, 2),
        "ws_clients":       ws_manager.count,
    }


# Relay
@app.post("/api/devices/{device_id}/relay")
async def relay_command(device_id: str, body: RelayCommand):
    if body.action not in ("on", "off"):
        raise HTTPException(400, "action: 'on' yoki 'off'")
    action = f"relay_{body.action}"
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO commands (device_id,action,created) VALUES (?,?,?) RETURNING id",
            (device_id, action, now_ts())
        )
        cmd_id = (await cur.fetchone())[0]
        await db.commit()
    asyncio.create_task(
        _mqtt_pub(f"meters/{device_id}/cmd", json.dumps({"action": action}))
    )
    return {"ok": True, "cmd_id": cmd_id}


# Reboot
@app.post("/api/devices/{device_id}/reboot")
async def reboot_device(device_id: str):
    asyncio.create_task(
        _mqtt_pub(f"meters/{device_id}/cmd", json.dumps({"action": "reboot"}))
    )
    return {"ok": True}


# Commands poll
@app.get("/api/commands/{device_id}")
async def get_commands(device_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id,action,param FROM commands WHERE device_id=? AND acked IS NULL ORDER BY id LIMIT 5",
            (device_id,)
        ) as cur:
            rows = await cur.fetchall()
    return {"commands": [dict(r) for r in rows]}


@app.post("/api/commands/{cmd_id}/ack")
async def ack_command(cmd_id: int, result: str = "ok"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE commands SET acked=?,ack_result=? WHERE id=?",
            (now_ts(), result, cmd_id)
        )
        await db.commit()
    return {"ok": True}


# Readings (HTTP fallback)
@app.post("/api/readings")
async def post_readings(body: MeterReading):
    ts = await _save_reading(body)
    await ws_manager.broadcast({
        "type": "reading", "device_id": body.device_id,
        "ts": ts, "data": body.model_dump()
    })
    return {"ok": True, "ts": ts}


# Alerts
@app.get("/api/alerts")
async def get_alerts(
    device_id: Optional[str] = None,
    kind:      Optional[str] = None,
    cleared:   bool = False,
    limit:     int  = Query(50, ge=1, le=500)
):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        conds  = ["cleared=?"]
        params = [int(cleared)]
        if device_id:
            conds.append("device_id=?"); params.append(device_id)
        if kind:
            conds.append("kind=?"); params.append(kind)
        params.append(limit)
        q = f"SELECT * FROM alerts WHERE {' AND '.join(conds)} ORDER BY ts DESC LIMIT ?"
        async with db.execute(q, params) as cur:
            rows = await cur.fetchall()
    return {"alerts": [dict(r) for r in rows]}


@app.post("/api/alerts/{alert_id}/clear")
async def clear_alert(alert_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE alerts SET cleared=1 WHERE id=?", (alert_id,))
        await db.commit()
    return {"ok": True}


@app.post("/api/alerts/clear-all")
async def clear_all_alerts(device_id: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if device_id:
            await db.execute("UPDATE alerts SET cleared=1 WHERE device_id=?", (device_id,))
        else:
            await db.execute("UPDATE alerts SET cleared=1")
        await db.commit()
    return {"ok": True}


# OTA upload
@app.post("/api/ota/upload")
async def ota_upload(
    version: str = Form(...),
    notes:   str = Form(""),
    file: UploadFile = File(...)
):
    data  = await file.read()
    sha   = hashlib.sha256(data).hexdigest()
    fname = f"firmware_{version}.bin"
    (OTA_DIR / fname).write_bytes(data)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE firmware SET active=0")
        await db.execute(
            "INSERT OR REPLACE INTO firmware (filename,version,size,sha256,uploaded,active,notes) VALUES (?,?,?,?,?,1,?)",
            (fname, version, len(data), sha, now_ts(), notes)
        )
        await db.commit()
    return {"ok": True, "version": version, "size": len(data), "sha256": sha}


@app.get("/api/ota/list")
async def ota_list():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM firmware ORDER BY uploaded DESC") as cur:
            rows = await cur.fetchall()
    return {"firmware": [dict(r) for r in rows]}


@app.delete("/api/ota/{fw_id}")
async def ota_delete(fw_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT filename,active FROM firmware WHERE id=?", (fw_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Topilmadi")
    if row["active"]:
        raise HTTPException(400, "Aktiv firmwareni o'chirib bo'lmaydi")
    fpath = OTA_DIR / row["filename"]
    if fpath.exists():
        fpath.unlink()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM firmware WHERE id=?", (fw_id,))
        await db.commit()
    return {"ok": True}


@app.get("/api/ota/check/{device_id}")
async def ota_check(device_id: str, current_version: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT version,filename,size,sha256 FROM firmware WHERE active=1 ORDER BY uploaded DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
    if not row or row["version"] == current_version:
        return {"update": False}
    return {
        "update":  True,
        "version": row["version"],
        "url":     f"/api/ota/firmware/{row['filename']}",
        "size":    row["size"],
        "sha256":  row["sha256"],
    }


@app.get("/api/ota/firmware/{filename}")
async def ota_download(filename: str):
    fpath = OTA_DIR / filename
    if not fpath.exists():
        raise HTTPException(404, "Firmware topilmadi")
    return FileResponse(str(fpath), media_type="application/octet-stream")


@app.post("/api/ota/push/{device_id}")
async def ota_push(device_id: str):
    """MQTT orqali qurilmaga OTA tekshirishni buyuradi."""
    asyncio.create_task(
        _mqtt_pub(f"meters/{device_id}/cmd", json.dumps({"action": "ota_check"}))
    )
    return {"ok": True, "message": f"{device_id} ga OTA buyrug'i yuborildi"}


# Health
@app.get("/health")
async def health():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM devices") as cur:
            dev_count = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM readings") as cur:
            rd_count = (await cur.fetchone())[0]
    return {
        "status":     "ok",
        "ts":         now_ts(),
        "devices":    dev_count,
        "readings":   rd_count,
        "ws_clients": ws_manager.count,
        "version":    "3.0",
        "data_keep_days": DATA_KEEP_DAYS,
    }
