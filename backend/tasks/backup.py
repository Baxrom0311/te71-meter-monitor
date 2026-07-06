import asyncio

from core.celery_app import celery_app
from core.database import init_db
from services.backup import create_backup_once


async def _run_backup(reason: str | None):
    await init_db()
    return await create_backup_once(reason)


@celery_app.task(name="backup.create")
def create_backup(reason: str | None = None) -> dict:
    return asyncio.run(_run_backup(reason))
