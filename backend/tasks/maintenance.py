import asyncio

from core.celery_app import celery_app
from core.database import init_db
from services.background import cleanup_old_data_once, detect_offline_devices_once


async def _with_db(coro):
    await init_db()
    return await coro


@celery_app.task(name="maintenance.detect_offline_devices")
def detect_offline_devices() -> dict:
    created = asyncio.run(_with_db(detect_offline_devices_once()))
    return {"offline_alerts_created": created}


@celery_app.task(name="maintenance.cleanup_old_data")
def cleanup_old_data() -> dict:
    return asyncio.run(_with_db(cleanup_old_data_once()))
