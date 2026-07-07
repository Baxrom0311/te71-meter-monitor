from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from core.security import require_admin
from models.schemas import (
    BackupCleanupResponse,
    BackupCreateResponse,
    BackupDeleteResponse,
    BackupListResponse,
    BackupRestoreResponse,
)
from services import audit
from services.backup import (
    backup_file_path,
    cleanup_old_backups_once,
    create_backup_once,
    delete_backup,
    list_backups,
    restore_backup_once,
)

router = APIRouter(prefix="/api")


@router.post("/backups", response_model=BackupCreateResponse)
async def create_backup(reason: str = "manual", admin: dict = Depends(require_admin)):
    result = await create_backup_once(reason)
    await audit.record(admin, "backup.create", "backup", result["filename"], {"reason": reason, "size": result["size"]})
    return result


@router.get("/backups", response_model=BackupListResponse)
async def backups(limit: int = Query(100, ge=1, le=500), _: dict = Depends(require_admin)):
    return list_backups(limit)


@router.post("/backups/cleanup", response_model=BackupCleanupResponse)
async def cleanup_backups(keep_days: Optional[int] = None, admin: dict = Depends(require_admin)):
    result = cleanup_old_backups_once(keep_days)
    await audit.record(admin, "backup.cleanup", "backup", None, {"keep_days": keep_days, "deleted": result["deleted_count"]})
    return result


@router.post("/backups/restore/{filename}", response_model=BackupRestoreResponse)
async def restore_backup(filename: str, confirm: str = "", admin: dict = Depends(require_admin)):
    result = await restore_backup_once(filename, confirm)
    await audit.record(admin, "backup.restore", "backup", filename, {"pre_restore": result.get("pre_restore_backup")})
    return result


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
