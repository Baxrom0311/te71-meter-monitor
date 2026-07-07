import asyncio

from core.celery_app import celery_app
from core.database import init_db
from services.ota import process_due_ota_batches_once


async def _with_db(coro):
    await init_db()
    return await coro


@celery_app.task(name="ota.process_due_batches")
def process_due_batches(limit_per_batch: int | None = None) -> dict:
    return asyncio.run(_with_db(process_due_ota_batches_once(limit_per_batch)))
