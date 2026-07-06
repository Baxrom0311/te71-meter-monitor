import asyncio

from core.celery_app import celery_app
from core.database import init_db
from services.backup import cleanup_old_backups_once, create_backup_once


async def _run_backup(reason: str | None):
    await init_db()
    return await create_backup_once(reason)


@celery_app.task(name="backup.create")
def create_backup(reason: str | None = None) -> dict:
    return asyncio.run(_run_backup(reason))


@celery_app.task(name="backup.cleanup_old")
def cleanup_old_backups(keep_days: int | None = None) -> dict:
    return cleanup_old_backups_once(keep_days)
