import json

from sqlalchemy import and_, delete, desc, func, select

from core.config import settings
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


async def list_logs(
    limit: int = 100,
    page: int = 1,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    username: str | None = None,
    user_id: int | None = None,
    since_ts: int | None = None,
    until_ts: int | None = None,
) -> dict:
    conditions = []
    if action:
        conditions.append(AuditLog.action == action)
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    if entity_id:
        conditions.append(AuditLog.entity_id == str(entity_id))
    if username:
        conditions.append(AuditLog.username == username)
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if since_ts:
        conditions.append(AuditLog.ts >= since_ts)
    if until_ts:
        conditions.append(AuditLog.ts <= until_ts)

    stmt = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)
    if conditions:
        clause = and_(*conditions)
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)
    offset = (page - 1) * limit
    async with SessionLocal() as session:
        total = await session.scalar(count_stmt) or 0
        rows = (await session.scalars(stmt.order_by(desc(AuditLog.ts)).limit(limit).offset(offset))).all()
    return {
        "audit_logs": [model_to_dict(row) for row in rows],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    }


async def cleanup_old_logs_once(keep_days: int | None = None) -> dict:
    days = settings.audit_keep_days if keep_days is None else keep_days
    cutoff = now_ts() - days * 86400
    async with SessionLocal() as session:
        result = await session.execute(delete(AuditLog).where(AuditLog.ts < cutoff))
        await session.commit()
    return {"ok": True, "deleted_count": result.rowcount or 0, "keep_days": days}
