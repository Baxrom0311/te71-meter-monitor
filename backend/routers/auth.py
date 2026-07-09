from fastapi import APIRouter, Depends, Query

from core.security import current_token_payload, require_admin
from schemas.auth import LoginRequest, TokenResponse, UserCreate, UserListResponse, UserResponse, UserUpdate
from services import audit
from services import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    return await auth.login(body)


@router.get("/me", response_model=UserResponse)
async def me(payload: dict = Depends(current_token_payload)):
    return await auth.me(payload["sub"])


@router.post("/users", response_model=UserResponse)
async def create_user(body: UserCreate, admin: dict = Depends(require_admin)):
    result = await auth.create_user(body)
    await audit.record(admin, "user.create", "user", result.get("id"), {"username": body.username, "role": body.role})
    return result


@router.get("/users", response_model=UserListResponse)
async def list_users(
    q: str | None = None,
    role: str | None = Query(None, pattern="^(admin|user)$"),
    is_active: bool | None = None,
    sort_by: str = Query("username", pattern="^(username|role|status)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    limit: int = Query(500, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _: dict = Depends(require_admin),
):
    return await auth.list_users(q=q, role=role, is_active=is_active, sort_by=sort_by, sort_order=sort_order, limit=limit, offset=offset)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, _: dict = Depends(require_admin)):
    return await auth.get_user(user_id)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, body: UserUpdate, admin: dict = Depends(require_admin)):
    result = await auth.update_user(user_id, body, actor_id=admin.get("sub"))
    detail = body.model_dump(exclude_none=True)
    detail.pop("password", None)
    await audit.record(admin, "user.update", "user", user_id, detail)
    return result
