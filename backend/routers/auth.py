from fastapi import APIRouter, Depends

from core.security import current_token_payload, require_admin
from schemas.auth import LoginRequest, UserCreate, UserUpdate
from services import audit
from services import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(body: LoginRequest):
    return await auth.login(body)


@router.get("/me")
async def me(payload: dict = Depends(current_token_payload)):
    return await auth.me(payload["sub"])


@router.post("/users")
async def create_user(body: UserCreate, admin: dict = Depends(require_admin)):
    result = await auth.create_user(body)
    await audit.record(admin, "user.create", "user", result.get("id"), {"username": body.username, "role": body.role})
    return result


@router.get("/users")
async def list_users(_: dict = Depends(require_admin)):
    return await auth.list_users()


@router.get("/users/{user_id}")
async def get_user(user_id: int, _: dict = Depends(require_admin)):
    return await auth.get_user(user_id)


@router.put("/users/{user_id}")
async def update_user(user_id: int, body: UserUpdate, admin: dict = Depends(require_admin)):
    result = await auth.update_user(user_id, body, actor_id=admin.get("sub"))
    detail = body.model_dump(exclude_none=True)
    detail.pop("password", None)
    await audit.record(admin, "user.update", "user", user_id, detail)
    return result
