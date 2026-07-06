from fastapi import HTTPException
from sqlalchemy import select

from core.config import settings
from core.database import SessionLocal
from core.security import create_access_token, hash_password, validate_password, verify_password
from core.time import now_ts
from models.entities import User
from repositories.base import model_to_dict
from schemas.auth import LoginRequest, UserCreate, UserUpdate


def _public_user(user: User) -> dict:
    data = model_to_dict(user)
    data.pop("password_hash", None)
    data.pop("failed_login_count", None)
    data.pop("locked_until", None)
    data.pop("created_at", None)
    data.pop("updated_at", None)
    return data


async def bootstrap_admin() -> None:
    if not settings.bootstrap_admin_password:
        return
    validate_password(settings.bootstrap_admin_password)
    ts = now_ts()
    async with SessionLocal() as session:
        existing = await session.scalar(
            select(User).where(User.username == settings.bootstrap_admin_username)
        )
        if existing:
            return
        session.add(
            User(
                username=settings.bootstrap_admin_username,
                password_hash=hash_password(settings.bootstrap_admin_password),
                role="admin",
                is_active=True,
                created_at=ts,
                updated_at=ts,
            )
        )
        await session.commit()


async def login(body: LoginRequest) -> dict:
    async with SessionLocal() as session:
        user = await session.scalar(select(User).where(User.username == body.username))
        if not user or not user.is_active:
            raise HTTPException(401, "Login yoki parol noto'g'ri")

        n = now_ts()
        if user.locked_until and user.locked_until > n:
            raise HTTPException(423, "Akkount vaqtincha bloklangan. Keyinroq urinib ko'ring")

        if not verify_password(body.password, user.password_hash):
            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= settings.max_login_attempts:
                user.locked_until = n + settings.login_lock_sec
            await session.commit()
            raise HTTPException(401, "Login yoki parol noto'g'ri")

        user.failed_login_count = 0
        user.locked_until = None
        user.last_login = n
        user.updated_at = n
        await session.commit()
        token = create_access_token(user.id, user.username, user.role)
        return {"access_token": token, "token_type": "bearer", "user": _public_user(user)}


async def me(user_id: int) -> dict:
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "User topilmadi")
    return _public_user(user)


async def create_user(body: UserCreate) -> dict:
    if body.role not in ("admin", "user"):
        raise HTTPException(400, "role faqat admin yoki user bo'lishi mumkin")
    validate_password(body.password)
    ts = now_ts()
    async with SessionLocal() as session:
        existing = await session.scalar(select(User.id).where(User.username == body.username))
        if existing:
            raise HTTPException(400, "Username band")
        user = User(
            username=body.username,
            password_hash=hash_password(body.password),
            role=body.role,
            is_active=True,
            created_at=ts,
            updated_at=ts,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return _public_user(user)


async def list_users() -> dict:
    async with SessionLocal() as session:
        users = (await session.scalars(select(User).order_by(User.id))).all()
    return {"users": [_public_user(user) for user in users]}


async def get_user(user_id: int) -> dict:
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "User topilmadi")
    return _public_user(user)


async def update_user(user_id: int, body: UserUpdate, actor_id: int | None = None) -> dict:
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(400, "Yangilanadigan maydon yo'q")
    if "role" in fields and fields["role"] not in ("admin", "user"):
        raise HTTPException(400, "role faqat admin yoki user bo'lishi mumkin")
    if "password" in fields:
        validate_password(fields["password"])

    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(404, "User topilmadi")
        if actor_id == user_id and fields.get("is_active") is False:
            raise HTTPException(400, "Admin o'zini deaktiv qila olmaydi")
        if actor_id == user_id and fields.get("role") == "user":
            raise HTTPException(400, "Admin o'z rolini pasaytira olmaydi")

        if "password" in fields:
            user.password_hash = hash_password(fields["password"])
            user.failed_login_count = 0
            user.locked_until = None
        if "role" in fields:
            user.role = fields["role"]
        if "is_active" in fields:
            user.is_active = fields["is_active"]
        user.updated_at = now_ts()
        await session.commit()
        await session.refresh(user)
    return _public_user(user)
