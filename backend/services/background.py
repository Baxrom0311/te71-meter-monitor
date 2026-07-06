import asyncio
import logging

from sqlalchemy import and_, delete, select

from core.config import settings
from core.database import SessionLocal
from core.time import now_ts
from models.entities import Alert, Device, Reading
from services.websocket import ws_manager

logger = logging.getLogger(__name__)


async def offline_detector() -> None:
    await asyncio.sleep(30)
    while True:
        try:
            n = now_ts()
            cutoff = n - settings.offline_sec
            async with SessionLocal() as session:
                devices = (
                    await session.scalars(
                        select(Device).where(
                            and_(
                                Device.is_active.is_(True),
                                Device.last_seen >= cutoff - settings.offline_sec,
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
                                Alert.ts > n - 3600,
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
                    await ws_manager.broadcast(
                        {
                            "type": "alert",
                            "kind": "offline",
                            "device_id": device.id,
                            "message": message,
                        }
                    )
                await session.commit()
        except Exception as exc:
            logger.warning("offline_detector error: %s", exc)
        await asyncio.sleep(60)


async def data_cleanup() -> None:
    await asyncio.sleep(10)
    while True:
        try:
            cutoff = now_ts() - settings.data_keep_days * 86400
            async with SessionLocal() as session:
                await session.execute(delete(Reading).where(Reading.ts < cutoff))
                await session.execute(delete(Alert).where(and_(Alert.ts < cutoff, Alert.cleared.is_(True))))
                await session.commit()
        except Exception as exc:
            logger.warning("data_cleanup error: %s", exc)
        await asyncio.sleep(86400)
