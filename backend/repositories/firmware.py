from sqlalchemy import and_, desc, select

from models.entities import Firmware
from repositories.base import BaseRepository


class FirmwareRepository(BaseRepository[Firmware]):
    model = Firmware

    async def list_latest(self) -> list[Firmware]:
        return list((await self.session.scalars(select(Firmware).order_by(desc(Firmware.uploaded)))).all())

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
