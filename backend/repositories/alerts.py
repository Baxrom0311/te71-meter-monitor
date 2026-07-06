from sqlalchemy import desc, select

from models.entities import Alert
from repositories.base import BaseRepository


class AlertRepository(BaseRepository[Alert]):
    model = Alert

    async def list_filtered(
        self,
        device_id: str | None = None,
        kind: str | None = None,
        cleared: bool = False,
        limit: int = 50,
    ) -> list[Alert]:
        stmt = select(Alert).where(Alert.cleared.is_(cleared)).order_by(desc(Alert.ts)).limit(limit)
        if device_id:
            stmt = stmt.where(Alert.device_id == device_id)
        if kind:
            stmt = stmt.where(Alert.kind == kind)
        return list((await self.session.scalars(stmt)).all())
