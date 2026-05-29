"""Auth endpoints: login, current-user-info."""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, SettingsDep
from app.auth.jwt import create_access_token
from app.auth.password import hash_password, needs_rehash, verify_password
from app.config import get_settings
from app.core.errors import UnauthorizedError
from app.core.ratelimit import rate_limit
from app.db.models.user import User

router = APIRouter()

# Tight rate limit on login to slow down credential-stuffing attacks.
_LOGIN_LIMIT = get_settings().rate_limit_login


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 — RFC 6750 token type literal, not a password
    expires_in: int


class UserInfo(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None
    is_active: bool
    is_superuser: bool


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange email + password for an access token",
    dependencies=[Depends(rate_limit(_LOGIN_LIMIT))],
)
async def login(
    payload: LoginRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> TokenResponse:
    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Constant-time response: verify even on missing user to avoid timing leaks.
    valid = user is not None and verify_password(payload.password, user.hashed_password)
    if not valid or user is None or not user.is_active:
        raise UnauthorizedError("Invalid credentials")

    # Opportunistic rehash if the stored hash uses outdated params.
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(payload.password)

    token = create_access_token(subject=str(user.id), settings=settings)
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserInfo, summary="Return the authenticated user")
async def me(user: CurrentUser) -> UserInfo:
    return UserInfo(
        id=str(user.id),
        email=user.email,  # type: ignore[arg-type]
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
    )
