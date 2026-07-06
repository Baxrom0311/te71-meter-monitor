from sqlalchemy import desc, select

from models.entities import Alert, AlertNotification, AlertRule
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


class AlertNotificationRepository(BaseRepository[AlertNotification]):
    model = AlertNotification

    async def list_filtered(self, status: str | None = None, limit: int = 100) -> list[AlertNotification]:
        stmt = select(AlertNotification).order_by(desc(AlertNotification.created_at)).limit(limit)
        if status:
            stmt = stmt.where(AlertNotification.status == status)
        return list((await self.session.scalars(stmt)).all())

    async def pending(self, limit: int = 100) -> list[AlertNotification]:
        return list(
            (
                await self.session.scalars(
                    select(AlertNotification)
                    .where(AlertNotification.status == "pending")
                    .order_by(AlertNotification.created_at)
                    .limit(limit)
                )
            ).all()
        )

    async def has_escalation(self, alert_id: int) -> bool:
        existing = await self.session.scalar(
            select(AlertNotification.id).where(
                AlertNotification.alert_id == alert_id,
                AlertNotification.status == "escalated",
            )
        )
        return existing is not None


class AlertRuleRepository(BaseRepository[AlertRule]):
    model = AlertRule

    async def list_filtered(
        self,
        utility_type: str | None = None,
        building_id: int | None = None,
        enabled: bool | None = None,
        limit: int = 200,
    ) -> list[AlertRule]:
        stmt = select(AlertRule).order_by(desc(AlertRule.id)).limit(limit)
        if utility_type:
            stmt = stmt.where(AlertRule.utility_type == utility_type)
        if building_id is not None:
            stmt = stmt.where(AlertRule.building_id == building_id)
        if enabled is not None:
            stmt = stmt.where(AlertRule.enabled.is_(enabled))
        return list((await self.session.scalars(stmt)).all())
