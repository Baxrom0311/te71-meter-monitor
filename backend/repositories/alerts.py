from sqlalchemy import and_, desc, or_, select, update

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
            stmt = stmt.where(Alert.kind.like(f"{kind}%"))
        return list((await self.session.scalars(stmt)).all())

    async def has_recent_duplicate(self, alert: Alert, since_ts: int) -> bool:
        existing = await self.session.scalar(
            select(Alert.id).where(
                and_(
                    Alert.device_id == alert.device_id,
                    Alert.kind == alert.kind,
                    Alert.cleared.is_(False),
                    Alert.ts > since_ts,
                )
            )
        )
        return existing is not None

    async def open_critical_due_for_escalation(self, cutoff: int, limit: int = 100) -> list[Alert]:
        return list(
            (
                await self.session.scalars(
                    select(Alert)
                    .where(and_(Alert.cleared.is_(False), Alert.severity == "critical", Alert.ts <= cutoff))
                    .order_by(Alert.ts)
                    .limit(limit)
                )
            ).all()
        )

    async def clear_all(self, ts: int, device_id: str | None = None) -> int:
        stmt = update(Alert).values(cleared=True, cleared_at=ts)
        if device_id:
            stmt = stmt.where(Alert.device_id == device_id)
        result = await self.session.execute(stmt)
        return result.rowcount or 0

    async def clear_offline_for_device(self, device_id: str, ts: int) -> int:
        result = await self.session.execute(
            update(Alert)
            .where(and_(Alert.device_id == device_id, Alert.kind == "offline", Alert.cleared.is_(False)))
            .values(cleared=True, cleared_at=ts)
        )
        return result.rowcount or 0


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

    async def matching_for_reading(
        self,
        utility_type: str,
        building_id: int | None,
        allowed_kinds: set[str],
    ) -> list[AlertRule]:
        stmt = select(AlertRule).where(
            and_(
                AlertRule.enabled.is_(True),
                AlertRule.kind.in_(allowed_kinds),
                or_(AlertRule.utility_type.is_(None), AlertRule.utility_type == utility_type),
            )
        )
        if building_id is not None:
            stmt = stmt.where(or_(AlertRule.building_id.is_(None), AlertRule.building_id == building_id))
        else:
            stmt = stmt.where(AlertRule.building_id.is_(None))
        return list((await self.session.scalars(stmt)).all())
