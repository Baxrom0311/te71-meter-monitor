from sqlalchemy import and_, desc, func, select, update

from models.entities import Command, Device, DeviceProvisioningToken
from repositories.base import BaseRepository


class DeviceRepository(BaseRepository[Device]):
    model = Device

    async def list_filtered(
        self,
        meter_type: str | None = None,
        group: str | None = None,
        building: str | None = None,
        utility_type: str | None = None,
    ) -> list[Device]:
        stmt = select(Device).where(Device.is_active.is_(True)).order_by(desc(Device.last_seen))
        if meter_type:
            stmt = stmt.where(Device.meter_type == meter_type)
        if group:
            stmt = stmt.where(Device.group_name == group)
        if building:
            stmt = stmt.where(Device.building_text == building)
        if utility_type:
            stmt = stmt.where(Device.utility_type == utility_type)
        return list((await self.session.scalars(stmt)).all())

    async def list_active_by_ids(self, device_ids: list[str]) -> list[Device]:
        if not device_ids:
            return []
        return list(
            (
                await self.session.scalars(
                    select(Device).where(and_(Device.id.in_(device_ids), Device.is_active.is_(True)))
                )
            ).all()
        )


class DeviceProvisioningTokenRepository(BaseRepository[DeviceProvisioningToken]):
    model = DeviceProvisioningToken

    async def active_candidates(self, now: int) -> list[DeviceProvisioningToken]:
        return list(
            (
                await self.session.scalars(
                    select(DeviceProvisioningToken).where(
                        and_(
                            DeviceProvisioningToken.used_at.is_(None),
                            DeviceProvisioningToken.revoked_at.is_(None),
                            DeviceProvisioningToken.expires_at > now,
                        )
                    )
                )
            ).all()
        )

    async def list_filtered(self, active_only: bool = True, limit: int = 100, now: int | None = None) -> list[DeviceProvisioningToken]:
        stmt = select(DeviceProvisioningToken).order_by(desc(DeviceProvisioningToken.id)).limit(limit)
        if active_only:
            stmt = stmt.where(
                and_(
                    DeviceProvisioningToken.used_at.is_(None),
                    DeviceProvisioningToken.revoked_at.is_(None),
                    DeviceProvisioningToken.expires_at > (now or 0),
                )
            )
        return list((await self.session.scalars(stmt)).all())


class CommandRepository(BaseRepository[Command]):
    model = Command

    async def active_pending_count(self, device_id: str, now: int) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(Command).where(
                and_(
                    Command.device_id == device_id,
                    Command.acked.is_(None),
                    Command.status.in_(["pending", "sent"]),
                    (Command.expires_at.is_(None)) | (Command.expires_at > now),
                )
            )
        ) or 0

    async def expire_due(self, now: int, device_id: str | None = None) -> int:
        stmt = (
            update(Command)
            .where(
                and_(
                    Command.acked.is_(None),
                    Command.status.in_(["pending", "sent"]),
                    Command.expires_at.is_not(None),
                    Command.expires_at <= now,
                )
            )
            .values(status="expired", ack_result="expired")
        )
        if device_id:
            stmt = stmt.where(Command.device_id == device_id)
        result = await self.session.execute(stmt)
        return result.rowcount or 0

    async def pollable_for_device(self, device_id: str, now: int, limit: int = 5) -> list[Command]:
        return list(
            (
                await self.session.scalars(
                    select(Command)
                    .where(
                        and_(
                            Command.device_id == device_id,
                            Command.acked.is_(None),
                            Command.status.in_(["pending", "sent"]),
                            (Command.expires_at.is_(None)) | (Command.expires_at > now),
                            Command.attempts < Command.max_attempts,
                        )
                    )
                    .order_by(Command.id)
                    .limit(limit)
                )
            ).all()
        )

    async def list_filtered(
        self,
        device_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Command]:
        stmt = select(Command).order_by(desc(Command.id)).offset(offset).limit(limit)
        if device_id:
            stmt = stmt.where(Command.device_id == device_id)
        if status:
            stmt = stmt.where(Command.status == status)
        return list((await self.session.scalars(stmt)).all())
