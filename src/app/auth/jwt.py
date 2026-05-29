"""JWT token issuance and validation.

Tokens include `sub` (user id), `iat`, `exp`, and `type=access`. Refresh
tokens follow the same pattern with `type=refresh` and a longer expiry —
not implemented here; add when you need it.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError

from app.config import Settings


def create_access_token(
    *,
    subject: str,
    settings: Settings,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Issue a signed JWT access token for the given subject (user id)."""
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": datetime.now(UTC),
        "exp": expire,
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str, settings: Settings) -> dict[str, Any]:
    """Decode and verify signature + expiry. Raises InvalidTokenError on failure."""
    return jwt.decode(
        token,
        settings.secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
    )


__all__ = ["InvalidTokenError", "create_access_token", "decode_token"]
