from sqlalchemy import and_, desc, select
from sqlalchemy.orm import selectinload

from models.entities import Firmware, FirmwareCompatibility
from repositories.base import BaseRepository


class FirmwareRepository(BaseRepository[Firmware]):
    model = Firmware

    async def list_latest(self) -> list[Firmware]:
        return list((await self.session.scalars(select(Firmware).order_by(desc(Firmware.uploaded)))).all())

    async def list_latest_with_compatibilities(self) -> list[Firmware]:
        return list(
            (
                await self.session.scalars(
                    select(Firmware)
                    .options(selectinload(Firmware.compatibilities))
                    .order_by(desc(Firmware.uploaded))
                )
            ).all()
        )

    async def list_active_with_compatibilities(self) -> list[Firmware]:
        return list(
            (
                await self.session.scalars(
                    select(Firmware)
                    .options(selectinload(Firmware.compatibilities))
                    .where(Firmware.active.is_(True))
                    .order_by(desc(Firmware.uploaded))
                )
            ).all()
        )

    async def active_for_device(self, firmware_mode: str, hardware_version: str | None) -> Firmware | None:
        return await self.session.scalar(
            select(Firmware)
            .where(
                and_(
                    Firmware.active.is_(True),
                    Firmware.firmware_mode.in_([firmware_mode, "auto"]),
                    (Firmware.hardware_version == hardware_version) | (Firmware.hardware_version.is_(None)),
                )
            )
            .order_by(desc(Firmware.uploaded))
            .limit(1)
        )


class FirmwareCompatibilityRepository(BaseRepository[FirmwareCompatibility]):
    model = FirmwareCompatibility
