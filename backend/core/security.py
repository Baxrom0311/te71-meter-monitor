import base64
import hashlib
import hmac
import json
import os

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings
from core.time import now_ts

bearer_scheme = HTTPBearer(auto_error=False)
device_token_scheme = APIKeyHeader(name="X-Device-Token", auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"pbkdf2_sha256${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


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


def create_access_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
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


async def current_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if not credentials:
        raise HTTPException(401, "Authorization token kerak")
    return decode_access_token(credentials.credentials)


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
