from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.orm import selectinload

from models.entities import Firmware
from models.entities import FirmwareInstallEvent, OTABatch, OTABatchDevice
from repositories.base import BaseRepository


class FirmwareInstallEventRepository(BaseRepository[FirmwareInstallEvent]):
    model = FirmwareInstallEvent

    async def list_filtered(
        self,
        device_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[FirmwareInstallEvent]:
        stmt = select(FirmwareInstallEvent).order_by(desc(FirmwareInstallEvent.ts)).limit(limit)
        if device_id:
            stmt = stmt.where(FirmwareInstallEvent.device_id == device_id)
        if status:
            stmt = stmt.where(FirmwareInstallEvent.status == status)
        return list((await self.session.scalars(stmt)).all())


class OTABatchRepository(BaseRepository[OTABatch]):
    model = OTABatch

    async def list_filtered(self, status: str | None = None, limit: int = 100) -> list[OTABatch]:
        stmt = select(OTABatch).order_by(desc(OTABatch.created_at)).limit(limit)
        if status:
            stmt = stmt.where(OTABatch.status == status)
        return list((await self.session.scalars(stmt)).all())

    async def get_detail(self, batch_id: int) -> OTABatch | None:
        return await self.session.scalar(
            select(OTABatch)
            .options(selectinload(OTABatch.firmware).selectinload(Firmware.compatibilities), selectinload(OTABatch.devices))
            .where(OTABatch.id == batch_id)
        )

    async def get_with_firmware(self, batch_id: int) -> OTABatch | None:
        return await self.session.scalar(
            select(OTABatch)
            .options(selectinload(OTABatch.firmware).selectinload(Firmware.compatibilities))
            .where(OTABatch.id == batch_id)
        )

    async def list_refresh_targets(
        self,
        firmware_id: int | None = None,
        batch_id: int | None = None,
    ) -> list[OTABatch]:
        stmt = select(OTABatch)
        if firmware_id:
            stmt = stmt.where(OTABatch.firmware_id == firmware_id)
        if batch_id:
            stmt = stmt.where(OTABatch.id == batch_id)
        return list((await self.session.scalars(stmt)).all())

    async def due_ids(self, ts: int) -> list[int]:
        return list(
            (
                await self.session.scalars(
                    select(OTABatch.id)
                    .where(
                        and_(
                            OTABatch.status.in_(["pending", "in_progress"]),
                            (OTABatch.scheduled_at.is_(None)) | (OTABatch.scheduled_at <= ts),
                        )
                    )
                    .order_by(OTABatch.scheduled_at.is_(None), OTABatch.scheduled_at, OTABatch.id)
                )
            ).all()
        )


class OTABatchDeviceRepository(BaseRepository[OTABatchDevice]):
    model = OTABatchDevice

    async def latest_for_report(self, firmware_id: int, device_id: str) -> OTABatchDevice | None:
        return await self.session.scalar(
            select(OTABatchDevice)
            .join(OTABatch, OTABatchDevice.batch_id == OTABatch.id)
            .where(
                and_(
                    OTABatch.firmware_id == firmware_id,
                    OTABatchDevice.device_id == device_id,
                    OTABatchDevice.status.in_(["pending", "processing", "notified", "downloading", "failed"]),
                )
            )
            .order_by(desc(OTABatchDevice.id))
            .limit(1)
        )

    async def status_count(self, batch_id: int, status: str, min_retry_count: int | None = None) -> int:
        stmt = select(func.count()).select_from(OTABatchDevice).where(
            and_(OTABatchDevice.batch_id == batch_id, OTABatchDevice.status == status)
        )
        if min_retry_count is not None:
            stmt = stmt.where(OTABatchDevice.retry_count >= min_retry_count)
        return await self.session.scalar(stmt) or 0

    async def total_count(self, batch_id: int) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(OTABatchDevice).where(OTABatchDevice.batch_id == batch_id)
        ) or 0

    async def retryable(self, batch_id: int) -> list[OTABatchDevice]:
        return list(
            (
                await self.session.scalars(
                    select(OTABatchDevice).where(
                        and_(
                            OTABatchDevice.batch_id == batch_id,
                            OTABatchDevice.status.in_(["failed", "processing", "notified", "downloading"]),
                        )
                    )
                )
            ).all()
        )

    async def candidate_pending_ids(self, batch_id: int, limit: int) -> list[int]:
        if limit <= 0:
            return []
        return list(
            (
                await self.session.scalars(
                    select(OTABatchDevice.id)
                    .where(and_(OTABatchDevice.batch_id == batch_id, OTABatchDevice.status == "pending"))
                    .order_by(OTABatchDevice.id)
                    .limit(limit)
                )
            ).all()
        )

    async def claim_pending(self, row_id: int, ts: int) -> bool:
        result = await self.session.execute(
            update(OTABatchDevice)
            .where(and_(OTABatchDevice.id == row_id, OTABatchDevice.status == "pending"))
            .values(status="processing", updated_at=ts)
        )
        return bool(result.rowcount)

    async def claimed_processing(self, batch_id: int, claimed_ids: list[int]) -> list[OTABatchDevice]:
        if not claimed_ids:
            return []
        return list(
            (
                await self.session.scalars(
                    select(OTABatchDevice)
                    .where(
                        and_(
                            OTABatchDevice.batch_id == batch_id,
                            OTABatchDevice.id.in_(claimed_ids),
                            OTABatchDevice.status == "processing",
                        )
                    )
                    .order_by(OTABatchDevice.id)
                )
            ).all()
        )

    async def notified_count_since(self, batch_id: int, since_ts: int) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(OTABatchDevice).where(
                and_(OTABatchDevice.batch_id == batch_id, OTABatchDevice.notified_at > since_ts)
            )
        ) or 0

    async def pending_count(self, batch_id: int) -> int:
        return await self.status_count(batch_id, "pending")

    async def pending_rows(self, batch_id: int) -> list[OTABatchDevice]:
        return list(
            (
                await self.session.scalars(
                    select(OTABatchDevice).where(
                        and_(OTABatchDevice.batch_id == batch_id, OTABatchDevice.status == "pending")
                    )
                )
            ).all()
        )
