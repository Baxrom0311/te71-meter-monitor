import gzip
import hashlib
import json
import re
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select

from core.config import settings
from core.database import SessionLocal
from core.time import now_ts
from models.entities import Base

BACKUP_RE = re.compile(r"^meter_backup_(?P<ts>\d+)_[a-f0-9]{12}\.json\.gz$")
RESTORE_TABLE_ORDER = [
    "users",
    "buildings",
    "firmware",
    "building_utilities",
    "premises",
    "measurement_points",
    "devices",
    "device_provisioning_tokens",
    "firmware_compatibilities",
    "readings",
    "hourly_utility_stats",
    "alerts",
    "commands",
    "audit_logs",
]


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


def _load_backup_payload(filename: str) -> dict:
    path = backup_file_path(filename)
    try:
        with gzip.open(path, "rb") as fh:
            payload = json.loads(fh.read().decode())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Backup fayl o'qilmadi") from exc
    if payload.get("metadata", {}).get("format") != "meter-monitor-json-v1":
        raise ValueError("Backup formati noto'g'ri")
    if not isinstance(payload.get("tables"), dict):
        raise ValueError("Backup tables bo'limi noto'g'ri")
    return payload


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


async def restore_backup_once(filename: str, confirm: str | None = None) -> dict:
    if confirm != "RESTORE":
        raise HTTPException(400, "Restore uchun confirm=RESTORE kerak")

    try:
        payload = _load_backup_payload(filename)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "Backup topilmadi yoki yaroqsiz") from exc

    pre_restore = await create_backup_once(f"pre_restore:{filename}")
    tables_payload: dict = payload["tables"]
    restored: dict[str, int] = {}

    sorted_tables = _restore_tables()
    async with SessionLocal() as session:
        for table in reversed(sorted_tables):
            await session.execute(table.delete())

        for table in sorted_tables:
            rows = tables_payload.get(table.name, [])
            if not rows:
                restored[table.name] = 0
                continue
            insert_rows = [_restore_insert_row(table.name, row) for row in rows]
            await session.execute(table.insert(), insert_rows)
            restored[table.name] = len(rows)

        for table in sorted_tables:
            rows = tables_payload.get(table.name, [])
            if table.name == "devices":
                for row in rows:
                    if row.get("point_id") is not None:
                        await session.execute(
                            table.update().where(table.c.id == row["id"]).values(point_id=row["point_id"])
                        )
            elif table.name == "measurement_points":
                for row in rows:
                    if row.get("device_id") is not None:
                        await session.execute(
                            table.update().where(table.c.id == row["id"]).values(device_id=row["device_id"])
                        )

        await session.commit()

    return {
        "ok": True,
        "restored_from": filename,
        "pre_restore_backup": pre_restore["filename"],
        "tables": restored,
    }


def _restore_insert_row(table_name: str, row: dict) -> dict:
    data = dict(row)
    if table_name == "devices":
        data["point_id"] = None
    elif table_name == "measurement_points":
        data["device_id"] = None
    return data


def _restore_tables() -> list:
    tables_by_name = Base.metadata.tables
    ordered = [tables_by_name[name] for name in RESTORE_TABLE_ORDER if name in tables_by_name]
    ordered_names = {table.name for table in ordered}
    ordered.extend(table for name, table in tables_by_name.items() if name not in ordered_names)
    return ordered
