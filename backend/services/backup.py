import gzip
import hashlib
import json
import re
from pathlib import Path

from sqlalchemy import select

from core.config import settings
from core.database import SessionLocal
from core.time import now_ts
from models.entities import Base

BACKUP_RE = re.compile(r"^meter_backup_(?P<ts>\d+)_[a-f0-9]{12}\.json\.gz$")


def _json_default(value):
    return str(value)


def _safe_backup_path(filename: str) -> Path:
    name = Path(filename).name
    path = settings.backup_dir / name
    if path.suffixes[-2:] != [".json", ".gz"]:
        raise ValueError("Backup fayl formati noto'g'ri")
    return path


def _backup_info(path: Path) -> dict:
    match = BACKUP_RE.match(path.name)
    created_at = int(match.group("ts")) if match else int(path.stat().st_mtime)
    return {
        "filename": path.name,
        "size": path.stat().st_size,
        "created_at": created_at,
    }


async def create_backup_once(reason: str | None = None) -> dict:
    ts = now_ts()
    payload: dict = {
        "metadata": {
            "created_at": ts,
            "app_version": settings.app_version,
            "reason": reason or "manual",
            "format": "meter-monitor-json-v1",
        },
        "tables": {},
    }

    async with SessionLocal() as session:
        for table in Base.metadata.tables.values():
            result = await session.execute(select(table))
            payload["tables"][table.name] = [dict(row) for row in result.mappings().all()]

    raw = json.dumps(payload, ensure_ascii=False, default=_json_default, separators=(",", ":")).encode()
    sha256 = hashlib.sha256(raw).hexdigest()
    filename = f"meter_backup_{ts}_{sha256[:12]}.json.gz"
    path = settings.backup_dir / filename
    with gzip.open(path, "wb") as fh:
        fh.write(raw)

    return {
        "ok": True,
        "filename": filename,
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": sha256,
        "created_at": ts,
        "tables": {name: len(rows) for name, rows in payload["tables"].items()},
    }


def backup_file_path(filename: str) -> Path:
    path = _safe_backup_path(filename)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(filename)
    return path


def list_backups(limit: int = 100) -> dict:
    files = [
        _backup_info(path)
        for path in settings.backup_dir.glob("meter_backup_*.json.gz")
        if path.is_file() and BACKUP_RE.match(path.name)
    ]
    files.sort(key=lambda item: item["created_at"], reverse=True)
    return {"backups": files[:limit], "total": len(files), "keep_days": settings.backup_keep_days}


def delete_backup(filename: str) -> dict:
    path = backup_file_path(filename)
    size = path.stat().st_size
    path.unlink()
    return {"ok": True, "filename": path.name, "size": size}


def cleanup_old_backups_once(keep_days: int | None = None) -> dict:
    days = settings.backup_keep_days if keep_days is None else keep_days
    cutoff = now_ts() - days * 86400
    deleted = []
    for path in settings.backup_dir.glob("meter_backup_*.json.gz"):
        if not path.is_file() or not BACKUP_RE.match(path.name):
            continue
        info = _backup_info(path)
        if info["created_at"] >= cutoff:
            continue
        path.unlink()
        deleted.append(info)
    return {"ok": True, "deleted": deleted, "deleted_count": len(deleted), "keep_days": days}
