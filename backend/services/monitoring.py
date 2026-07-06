from sqlalchemy import and_, desc, func, inspect, select

from core.config import settings
from core.database import SessionLocal
from core.metrics import render_http_metrics
from core.time import now_ts
from models.entities import Alert, Building, Command, Device, MeasurementPoint, Reading
from services import devices as devices_service
from services.websocket import ws_manager


def _as_dict(obj) -> dict:
    return {attr.key: getattr(obj, attr.key) for attr in inspect(obj).mapper.column_attrs}


async def build_snapshot() -> dict:
    async with SessionLocal() as session:
        devices = (await session.scalars(select(Device).where(Device.is_active.is_(True)))).all()
        alerts = (await session.scalars(select(Alert).order_by(desc(Alert.ts)).limit(20))).all()
    device_rows = [_as_dict(device) | {"online": devices_service.online_status(device.last_seen)} for device in devices]
    return {"devices": device_rows, "alerts": [_as_dict(alert) for alert in alerts]}


async def summary() -> dict:
    n = now_ts()
    async with SessionLocal() as session:
        total = await session.scalar(select(func.count()).select_from(Device).where(Device.is_active.is_(True))) or 0
        online = (
            await session.scalar(
                select(func.count()).select_from(Device).where(
                    and_(Device.is_active.is_(True), Device.last_seen > n - settings.offline_sec)
                )
            )
            or 0
        )
        active_alerts = (
            await session.scalar(select(func.count()).select_from(Alert).where(and_(Alert.cleared.is_(False), Alert.ts > n - 86400)))
            or 0
        )
        reads_last_hour = await session.scalar(select(func.count()).select_from(Reading).where(Reading.ts > n - 3600)) or 0
        total_energy = await session.scalar(select(func.sum(Reading.energy_kwh))) or 0
        buildings = await session.scalar(select(func.count()).select_from(Building)) or 0
        points = await session.scalar(select(func.count()).select_from(MeasurementPoint).where(MeasurementPoint.is_active.is_(True))) or 0
    return {
        "devices_total": total,
        "devices_online": online,
        "devices_offline": total - online,
        "alerts_active": active_alerts,
        "reads_last_hour": reads_last_hour,
        "total_energy_kwh": round(total_energy, 2),
        "buildings": buildings,
        "measurement_points": points,
        "ws_clients": ws_manager.count,
    }


async def health() -> dict:
    async with SessionLocal() as session:
        dev_count = await session.scalar(select(func.count()).select_from(Device)) or 0
        reading_count = await session.scalar(select(func.count()).select_from(Reading)) or 0
        alert_count = await session.scalar(select(func.count()).select_from(Alert).where(Alert.cleared.is_(False))) or 0
        command_count = await session.scalar(
            select(func.count()).select_from(Command).where(Command.status.in_(["pending", "sent"]))
        ) or 0
    return {
        "status": "ok",
        "ts": now_ts(),
        "devices": dev_count,
        "readings": reading_count,
        "open_alerts": alert_count,
        "pending_commands": command_count,
        "ws_clients": ws_manager.count,
        "version": settings.app_version,
        "data_keep_days": settings.data_keep_days,
        "workers": {
            "inline": settings.run_inline_workers,
            "celery_broker": bool(settings.celery_broker_url),
        },
    }


async def metrics_text() -> str:
    data = await health()
    lines = [
        "# HELP meter_monitor_devices_total Total registered devices.",
        "# TYPE meter_monitor_devices_total gauge",
        f"meter_monitor_devices_total {data['devices']}",
        "# HELP meter_monitor_readings_total Total stored readings.",
        "# TYPE meter_monitor_readings_total gauge",
        f"meter_monitor_readings_total {data['readings']}",
        "# HELP meter_monitor_open_alerts Open alerts.",
        "# TYPE meter_monitor_open_alerts gauge",
        f"meter_monitor_open_alerts {data['open_alerts']}",
        "# HELP meter_monitor_pending_commands Pending commands.",
        "# TYPE meter_monitor_pending_commands gauge",
        f"meter_monitor_pending_commands {data['pending_commands']}",
        "# HELP meter_monitor_ws_clients Connected websocket clients.",
        "# TYPE meter_monitor_ws_clients gauge",
        f"meter_monitor_ws_clients {data['ws_clients']}",
    ]
    lines.extend(render_http_metrics())
    return "\n".join(lines) + "\n"
