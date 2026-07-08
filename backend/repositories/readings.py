from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import aliased

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

    async def latest_by_point_ids(self, point_ids: list[int]) -> dict[int, Reading]:
        if not point_ids:
            return {}
        r_inner = aliased(Reading)
        latest_subq = (
            select(func.max(r_inner.ts).label("max_ts"), r_inner.point_id)
            .where(r_inner.point_id.in_(point_ids))
            .group_by(r_inner.point_id)
            .subquery()
        )
        stmt = select(Reading).join(
            latest_subq,
            and_(Reading.point_id == latest_subq.c.point_id, Reading.ts == latest_subq.c.max_ts),
        )
        return {row.point_id: row for row in (await self.session.scalars(stmt)).all()}

    async def building_history(
        self,
        building_id: int,
        offset: int,
        limit: int,
        utility_type: str | None = None,
        cutoff: int | None = None,
    ) -> list[Reading]:
        stmt = select(Reading).where(Reading.building_id == building_id)
        if utility_type:
            stmt = stmt.where(Reading.utility_type == utility_type)
        if cutoff:
            stmt = stmt.where(Reading.ts > cutoff)
        return list((await self.session.scalars(stmt.order_by(desc(Reading.ts)).limit(limit).offset(offset))).all())

    async def count_building_history(
        self,
        building_id: int,
        utility_type: str | None = None,
        cutoff: int | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(Reading).where(Reading.building_id == building_id)
        if utility_type:
            stmt = stmt.where(Reading.utility_type == utility_type)
        if cutoff:
            stmt = stmt.where(Reading.ts > cutoff)
        return await self.session.scalar(stmt) or 0

    async def export_for_device(self, device_id: str, cutoff: int) -> list[Reading]:
        return list(
            (
                await self.session.scalars(
                    select(Reading).where(and_(Reading.device_id == device_id, Reading.ts > cutoff)).order_by(Reading.ts)
                )
            ).all()
        )
