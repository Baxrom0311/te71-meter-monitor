from fastapi import APIRouter, Depends

from core.security import current_token_payload, require_admin
from schemas.auth import LoginRequest, UserCreate
from services import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(body: LoginRequest):
    return await auth.login(body)


@router.get("/me")
async def me(payload: dict = Depends(current_token_payload)):
    return await auth.me(payload["sub"])


@router.post("/users")
async def create_user(body: UserCreate, _: dict = Depends(require_admin)):
    return await auth.create_user(body)


@router.get("/users")
async def list_users(_: dict = Depends(require_admin)):
    return await auth.list_users()
