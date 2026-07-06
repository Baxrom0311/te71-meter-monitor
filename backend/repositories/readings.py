from sqlalchemy import and_, desc, func, select

from models.entities import Reading
from repositories.base import BaseRepository


class ReadingRepository(BaseRepository[Reading]):
    model = Reading

    async def latest_for_device(self, device_id: str) -> Reading | None:
        return await self.session.scalar(
            select(Reading).where(Reading.device_id == device_id).order_by(desc(Reading.ts)).limit(1)
        )

    async def exists_external_id(self, device_id: str, reading_id: str) -> bool:
        existing = await self.session.scalar(
            select(Reading.id).where(and_(Reading.device_id == device_id, Reading.reading_id == reading_id))
        )
        return existing is not None

    async def history(self, device_id: str, offset: int, limit: int, cutoff: int | None = None) -> list[Reading]:
        stmt = select(Reading).where(Reading.device_id == device_id)
        if cutoff:
            stmt = stmt.where(Reading.ts > cutoff)
        stmt = stmt.order_by(desc(Reading.ts)).limit(limit).offset(offset)
        return list((await self.session.scalars(stmt)).all())

    async def count_history(self, device_id: str, cutoff: int | None = None) -> int:
        stmt = select(func.count()).select_from(Reading).where(Reading.device_id == device_id)
        if cutoff:
            stmt = stmt.where(Reading.ts > cutoff)
        return await self.session.scalar(stmt) or 0
