import gzip
import hashlib
import json
from pathlib import Path

from sqlalchemy import select

from core.config import settings
from core.database import SessionLocal
from core.time import now_ts
from models.entities import Base


def _json_default(value):
    return str(value)


def _safe_backup_path(filename: str) -> Path:
    name = Path(filename).name
    path = settings.backup_dir / name
    if path.suffixes[-2:] != [".json", ".gz"]:
        raise ValueError("Backup fayl formati noto'g'ri")
    return path


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
