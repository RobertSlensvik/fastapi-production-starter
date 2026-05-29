"""FastAPI dependencies: settings, DB session, current user, API key.

Use these via `Depends()` in route handlers. They handle the auth + DB
plumbing so handlers stay focused on business logic.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.apikey import is_valid_api_key
from app.auth.jwt import InvalidTokenError, decode_token
from app.config import Settings
from app.db.models.user import User
from app.db.session import get_session

# ─── Config ─────────────────────────────────────────────────────────────────


def get_app_settings(request: Request) -> Settings:
    """Pull settings from app.state (set by factory). Use this instead of
    re-calling `get_settings()` to keep tests deterministic."""
    return request.app.state.settings  # type: ignore[no-any-return]


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


# ─── JWT bearer ─────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    settings: SettingsDep,
    session: SessionDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Resolve the user from the Bearer token. Raises 401 if missing/invalid."""
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(creds.credentials, settings)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_superuser(user: CurrentUser) -> User:
    """Same as CurrentUser but additionally requires `is_superuser=True`."""
    if not user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser required")
    return user


SuperUser = Annotated[User, Depends(require_superuser)]


# ─── API key ────────────────────────────────────────────────────────────────


async def require_api_key(
    settings: SettingsDep,
    api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> str:
    """Validate the X-API-Key header. Returns the key on success.

    Use this for service-to-service endpoints where JWT doesn't fit.
    """
    if not is_valid_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": settings.api_key_header},
        )
    return api_key or ""  # mypy: not-None already ensured by is_valid_api_key


ApiKey = Annotated[str, Depends(require_api_key)]
