from sqlalchemy import and_, desc, select

from models.entities import Command, Device
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


class CommandRepository(BaseRepository[Command]):
    model = Command

    async def pending_for_device(self, device_id: str, limit: int = 5) -> list[Command]:
        return list(
            (
                await self.session.scalars(
                    select(Command)
                    .where(and_(Command.device_id == device_id, Command.acked.is_(None)))
                    .order_by(Command.id)
                    .limit(limit)
                )
            ).all()
        )
