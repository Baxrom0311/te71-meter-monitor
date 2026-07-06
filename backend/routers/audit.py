from typing import Optional

from fastapi import APIRouter, Depends, Query

from core.security import require_admin
from services import audit

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
