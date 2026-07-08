import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings
from core.database import SessionLocal
from core.time import now_ts
from models.entities import User

bearer_scheme = HTTPBearer(auto_error=False)
device_token_scheme = APIKeyHeader(name="X-Device-Token", auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"pbkdf2_sha256${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def generate_secret_token() -> str:
    return secrets.token_urlsafe(32)


def validate_password(password: str) -> None:
    if len(password) < settings.min_password_len:
        raise HTTPException(400, f"Parol kamida {settings.min_password_len} ta belgi bo'lishi kerak")
    if password.isdigit() or password.isalpha():
        raise HTTPException(400, "Parol faqat harf yoki faqat raqamdan iborat bo'lmasin")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, salt_b64, digest_b64 = password_hash.split("$", 2)
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_access_token(user_id: int, username: str, role: str, token_version: int = 1) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "tv": token_version,
        "exp": now_ts() + settings.access_token_ttl_sec,
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    signature = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def decode_access_token(token: str) -> dict:
    try:
        body, signature = token.rsplit(".", 1)
        expected = hmac.new(settings.secret_key.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("bad signature")
        payload = json.loads(base64.urlsafe_b64decode(body.encode()).decode())
        if payload.get("exp", 0) < now_ts():
            raise ValueError("expired")
        return payload
    except Exception:
        raise HTTPException(401, "Token noto'g'ri yoki muddati tugagan")


# Oddiy TTL cache — har bir authenticated so'rovda DB query oldini olish
_user_status_cache: dict[int, tuple[float, str, str, bool, int]] = {}
_USER_CACHE_TTL = 300  # 5 daqiqa


def invalidate_user_cache(user_id: int) -> None:
    """User parol/role o'zgarganda cache ni tozalash."""
    _user_status_cache.pop(user_id, None)


async def current_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if not credentials:
        raise HTTPException(401, "Authorization token kerak")
    return await validate_access_token(credentials.credentials)


async def validate_access_token(token: str) -> dict:
    payload = decode_access_token(token)

    user_id = payload.get("sub")
    now = time.time()

    # Cache dan tekshirish
    cached = _user_status_cache.get(user_id)
    if cached:
        expire_ts, cached_username, cached_role, cached_active, cached_token_version = cached
        if now < expire_ts:
            if not cached_active:
                raise HTTPException(401, "User aktiv emas")
            if cached_username != payload.get("username") or cached_role != payload.get("role"):
                raise HTTPException(401, "Token eskirgan, qayta login qiling")
            if cached_token_version != int(payload.get("tv") or 0):
                raise HTTPException(401, "Token eskirgan, qayta login qiling")
            return payload

    # Cache da yo'q yoki eskirgan — DB dan o'qish
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
    if not user or not user.is_active:
        _user_status_cache[user_id] = (now + _USER_CACHE_TTL, "", "", False, 0)
        raise HTTPException(401, "User aktiv emas")
    if user.username != payload.get("username") or user.role != payload.get("role"):
        _user_status_cache.pop(user_id, None)
        raise HTTPException(401, "Token eskirgan, qayta login qiling")
    if user.token_version != int(payload.get("tv") or 0):
        _user_status_cache.pop(user_id, None)
        raise HTTPException(401, "Token eskirgan, qayta login qiling")

    # Cache ga saqlash
    _user_status_cache[user_id] = (now + _USER_CACHE_TTL, user.username, user.role, user.is_active, user.token_version)
    return payload


async def require_admin(payload: dict = Depends(current_token_payload)) -> dict:
    if payload.get("role") != "admin":
        raise HTTPException(403, "Admin huquqi kerak")
    return payload


async def require_device_token(token: str | None = Depends(device_token_scheme)) -> bool:
    if not settings.device_api_token:
        return True
    if not token or not hmac.compare_digest(token, settings.device_api_token):
        raise HTTPException(401, "Device token noto'g'ri")
    return True
