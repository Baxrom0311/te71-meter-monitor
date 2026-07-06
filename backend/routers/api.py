from typing import Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException
from fastapi.responses import FileResponse

from core.celery_app import celery_app
from core.security import require_admin
from models.schemas import (
    BackupDeleteResponse,
    BackupListResponse,
    BackupTaskStatusResponse,
    TaskQueuedResponse,
)
from services import audit
from services.backup import backup_file_path, delete_backup, list_backups
from tasks.backup import cleanup_old_backups as cleanup_old_backups_task
from tasks.backup import create_backup as create_backup_task
from tasks.backup import restore_backup as restore_backup_task

router = APIRouter(prefix="/api")


@router.get("/audit-logs")
async def audit_logs(
    limit: int = Query(100, ge=1, le=500),
    page: int = Query(1, ge=1),
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    since_ts: Optional[int] = None,
    until_ts: Optional[int] = None,
    _: dict = Depends(require_admin),
):
    return await audit.list_logs(limit, page, action, entity_type, entity_id, username, user_id, since_ts, until_ts)


@router.post("/backups", response_model=TaskQueuedResponse)
async def create_backup(reason: str = "manual", admin: dict = Depends(require_admin)):
    task = create_backup_task.delay(reason)
    await audit.record(admin, "backup.create", "backup", task.id, {"reason": reason})
    return {"ok": True, "task_id": task.id, "status": "queued"}


@router.get("/backups", response_model=BackupListResponse)
async def backups(limit: int = Query(100, ge=1, le=500), _: dict = Depends(require_admin)):
    return list_backups(limit)


@router.get("/backups/tasks/{task_id}", response_model=BackupTaskStatusResponse)
async def backup_status(task_id: str, _: dict = Depends(require_admin)):
    result = AsyncResult(task_id, app=celery_app)
    response = {"task_id": task_id, "status": result.status}
    if result.ready():
        if result.failed():
            response["error"] = str(result.result)
        else:
            response["result"] = result.result
    return response


@router.post("/backups/cleanup", response_model=TaskQueuedResponse)
async def cleanup_backups(keep_days: Optional[int] = None, admin: dict = Depends(require_admin)):
    task = cleanup_old_backups_task.delay(keep_days)
    await audit.record(admin, "backup.cleanup", "backup", task.id, {"keep_days": keep_days})
    return {"ok": True, "task_id": task.id, "status": "queued"}


@router.post("/backups/restore/{filename}", response_model=TaskQueuedResponse)
async def restore_backup(filename: str, confirm: str = "", admin: dict = Depends(require_admin)):
    if confirm != "RESTORE":
        raise HTTPException(400, "Restore uchun confirm=RESTORE kerak")
    try:
        backup_file_path(filename)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Backup topilmadi")
    task = restore_backup_task.delay(filename, confirm)
    await audit.record(admin, "backup.restore", "backup", filename, {"task_id": task.id})
    return {"ok": True, "task_id": task.id, "status": "queued"}


@router.get("/backups/download/{filename}")
async def download_backup(filename: str, _: dict = Depends(require_admin)):
    try:
        path = backup_file_path(filename)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Backup topilmadi")
    return FileResponse(
        str(path),
        media_type="application/gzip",
        filename=path.name,
    )


@router.delete("/backups/{filename}", response_model=BackupDeleteResponse)
async def remove_backup(filename: str, admin: dict = Depends(require_admin)):
    try:
        result = delete_backup(filename)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "Backup topilmadi")
    await audit.record(admin, "backup.delete", "backup", filename, {"size": result["size"]})
    return result
