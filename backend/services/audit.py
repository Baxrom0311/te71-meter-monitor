import json

from sqlalchemy import desc, select

from core.database import SessionLocal
from core.time import now_ts
from models.entities import AuditLog
from repositories.base import model_to_dict


async def record(
    payload: dict,
    action: str,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    detail: dict | None = None,
) -> None:
    async with SessionLocal() as session:
        session.add(
            AuditLog(
                ts=now_ts(),
                user_id=payload.get("sub"),
                username=payload.get("username"),
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id is not None else None,
                detail=json.dumps(detail, ensure_ascii=False) if detail else None,
            )
        )
        await session.commit()


async def list_logs(limit: int = 100) -> dict:
    async with SessionLocal() as session:
        rows = (await session.scalars(select(AuditLog).order_by(desc(AuditLog.ts)).limit(limit))).all()
    return {"audit_logs": [model_to_dict(row) for row in rows]}
