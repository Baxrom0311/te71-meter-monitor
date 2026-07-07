from sqlalchemy import select

from models.entities import User
from repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def by_username(self, username: str) -> User | None:
        return await self.session.scalar(select(User).where(User.username == username))

    async def username_exists(self, username: str) -> bool:
        existing = await self.session.scalar(select(User.id).where(User.username == username))
        return existing is not None

    async def list_ordered(self) -> list[User]:
        return list((await self.session.scalars(select(User).order_by(User.id))).all())
