import asyncio
import logging
import os
import socket

from sqlalchemy import and_, delete, select, update
from sqlalchemy.exc import IntegrityError

from core.config import settings
from core.database import SessionLocal
from core.time import now_ts
from models.entities import (
    Alert,
    AlertNotification,
    Command,
    Device,
    FirmwareInstallEvent,
    HourlyUtilityStats,
    MeasurementPoint,
    OTABatchDevice,
    Reading,
    WorkerLock,
)
from services.websocket import ws_manager

logger = logging.getLogger(__name__)
WORKER_OWNER = f"{socket.gethostname()}:{os.getpid()}"


async def acquire_worker_lock(name: str, ttl_sec: int) -> bool:
    n = now_ts()
    lock_until = n + ttl_sec
    async with SessionLocal() as session:
        result = await session.execute(
            update(WorkerLock)
            .where(and_(WorkerLock.name == name, WorkerLock.locked_until <= n))
            .values(locked_until=lock_until, owner=WORKER_OWNER, updated_at=n)
        )
        if result.rowcount:
            await session.commit()
            return True

        session.add(WorkerLock(name=name, locked_until=lock_until, owner=WORKER_OWNER, updated_at=n))
        try:
            await session.commit()
            return True
        except IntegrityError:
            await session.rollback()
            return False


async def run_with_worker_lock(name: str, ttl_sec: int, coro):
    if not await acquire_worker_lock(name, ttl_sec):
        logger.debug("worker lock skipped: %s", name)
        return None
    return await coro()


async def detect_offline_devices_once() -> int:
    n = now_ts()
    cutoff = n - settings.offline_sec
    created = 0
    async with SessionLocal() as session:
        devices = (
            await session.scalars(
                select(Device).where(
                    and_(
                        Device.is_active.is_(True),
                        Device.last_seen <= cutoff,
                    )
                )
            )
        ).all()

        for device in devices:
            exists = await session.scalar(
                select(Alert.id).where(
                    and_(
                        Alert.device_id == device.id,
                        Alert.kind == "offline",
                        Alert.cleared.is_(False),
                    )
                )
            )
            if exists:
                continue
            message = f"{device.name or device.id} offline"
            session.add(
                Alert(
                    device_id=device.id,
                    building_id=device.building_id,
                    point_id=device.point_id,
                    utility_type=device.utility_type,
                    severity="warning",
                    ts=n,
                    kind="offline",
                    message=message,
                )
            )
            created += 1
            await ws_manager.broadcast(
                {
                    "type": "alert",
                    "kind": "offline",
                    "device_id": device.id,
                    "message": message,
                }
            )
        await session.commit()
    return created


async def cleanup_old_data_once() -> dict:
    cutoff = now_ts() - settings.data_keep_days * 86400
    async with SessionLocal() as session:
        readings = await session.execute(delete(Reading).where(Reading.ts < cutoff))
        alerts = await session.execute(delete(Alert).where(and_(Alert.ts < cutoff, Alert.cleared.is_(True))))
        await session.commit()
    return {
        "readings_deleted": readings.rowcount or 0,
        "alerts_deleted": alerts.rowcount or 0,
    }


async def cleanup_expired_test_devices_once() -> dict:
    n = now_ts()
    async with SessionLocal() as session:
        device_ids = list(
            (
                await session.scalars(
                    select(Device.id)
                    .where(
                        and_(
                            Device.is_test_device.is_(True),
                            Device.auto_cleanup_at.is_not(None),
                            Device.auto_cleanup_at <= n,
                        )
                    )
                    .limit(500)
                )
            ).all()
        )
        if not device_ids:
            return {"deleted_test_devices": 0}

        await session.execute(update(MeasurementPoint).where(MeasurementPoint.device_id.in_(device_ids)).values(device_id=None))
        await session.execute(delete(OTABatchDevice).where(OTABatchDevice.device_id.in_(device_ids)))
        await session.execute(delete(FirmwareInstallEvent).where(FirmwareInstallEvent.device_id.in_(device_ids)))
        await session.execute(delete(HourlyUtilityStats).where(HourlyUtilityStats.device_id.in_(device_ids)))
        await session.execute(delete(AlertNotification).where(AlertNotification.device_id.in_(device_ids)))
        await session.execute(delete(Alert).where(Alert.device_id.in_(device_ids)))
        await session.execute(delete(Command).where(Command.device_id.in_(device_ids)))
        await session.execute(delete(Reading).where(Reading.device_id.in_(device_ids)))
        result = await session.execute(
            delete(Device)
            .where(
                and_(
                    Device.is_test_device.is_(True),
                    Device.id.in_(device_ids),
                )
            )
        )
        await session.commit()
    return {"deleted_test_devices": result.rowcount or 0}


async def offline_detector() -> None:
    await asyncio.sleep(30)
    while True:
        try:
            await run_with_worker_lock("offline_detector", 55, detect_offline_devices_once)
        except Exception as exc:
            logger.exception("offline_detector error: %s", exc)
        await asyncio.sleep(60)


async def data_cleanup() -> None:
    await asyncio.sleep(10)
    while True:
        try:
            await run_with_worker_lock("data_cleanup", 3600, cleanup_old_data_once)
        except Exception as exc:
            logger.exception("data_cleanup error: %s", exc)
        await asyncio.sleep(86400)


async def test_device_cleanup_worker() -> None:
    """Test qurilmalarni TTL tugaganda o'chirish — har 60s."""
    await asyncio.sleep(60)
    while True:
        try:
            await run_with_worker_lock("test_device_cleanup_worker", 55, cleanup_expired_test_devices_once)
        except Exception as exc:
            logger.exception("test_device_cleanup_worker error: %s", exc)
        await asyncio.sleep(60)


async def alert_notification_worker() -> None:
    """Alert notifications va escalation — har 60s."""
    from services.alerts import process_alert_notifications_once
    await asyncio.sleep(20)
    while True:
        try:
            await run_with_worker_lock("alert_notification_worker", 55, process_alert_notifications_once)
        except Exception as exc:
            logger.exception("alert_notification_worker error: %s", exc)
        await asyncio.sleep(60)


async def command_cleanup_worker() -> None:
    """Muddati o'tgan commandlarni tozalash — har soat."""
    from services.commands import cleanup_expired_commands_once
    await asyncio.sleep(60)
    while True:
        try:
            await run_with_worker_lock("command_cleanup_worker", 1800, cleanup_expired_commands_once)
        except Exception as exc:
            logger.exception("command_cleanup_worker error: %s", exc)
        await asyncio.sleep(3600)


async def audit_cleanup_worker() -> None:
    """Eski audit loglarni tozalash — har kunda."""
    from services.audit import cleanup_old_logs_once
    await asyncio.sleep(120)
    while True:
        try:
            await run_with_worker_lock("audit_cleanup_worker", 3600, cleanup_old_logs_once)
        except Exception as exc:
            logger.exception("audit_cleanup_worker error: %s", exc)
        await asyncio.sleep(86400)


async def analytics_worker() -> None:
    """Soatlik statistika agregatsiyasi — har soat."""
    from services.analytics import aggregate_hourly_stats_once
    await asyncio.sleep(300)
    while True:
        try:
            await run_with_worker_lock("analytics_worker", 1800, aggregate_hourly_stats_once)
        except Exception as exc:
            logger.exception("analytics_worker error: %s", exc)
        await asyncio.sleep(3600)


async def ota_batch_worker() -> None:
    """Scheduled OTA batchlarni process qilish va retry qilish."""
    from services.ota import process_due_ota_batches_once
    await asyncio.sleep(30)
    while True:
        try:
            await run_with_worker_lock(
                "ota_batch_worker",
                max(settings.ota_batch_process_interval_sec - 5, 1),
                process_due_ota_batches_once,
            )
        except Exception as exc:
            logger.exception("ota_batch_worker error: %s", exc)
        await asyncio.sleep(settings.ota_batch_process_interval_sec)
