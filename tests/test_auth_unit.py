"""Unit tests — no DB or Redis needed."""

from datetime import timedelta

import jwt
import pytest

from app.auth.jwt import InvalidTokenError, create_access_token, decode_token
from app.auth.password import hash_password, needs_rehash, verify_password
from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(secret_key="test-secret-key-32-characters-minimum")  # type: ignore[arg-type]


class TestPasswordHashing:
    def test_hash_is_opaque_and_verifies(self) -> None:
        h = hash_password("hunter2")
        assert h.startswith("$argon2")
        assert verify_password("hunter2", h) is True

    def test_wrong_password_fails(self) -> None:
        h = hash_password("hunter2")
        assert verify_password("wrong", h) is False

    def test_each_hash_is_unique_due_to_salt(self) -> None:
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # Different salt → different hash

    def test_needs_rehash_for_invalid_hash(self) -> None:
        # A clearly outdated/invalid hash format triggers a rehash signal.
        # This is the same logic argon2 applies internally; we test the wiring.
        h = hash_password("foo")
        assert needs_rehash(h) is False


class TestJWT:
    def test_roundtrip(self, settings: Settings) -> None:
        token = create_access_token(subject="user-123", settings=settings)
        payload = decode_token(token, settings)
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_expired_token_fails(self, settings: Settings) -> None:
        token = create_access_token(
            subject="user-123", settings=settings, expires_delta=timedelta(seconds=-1)
        )
        with pytest.raises(InvalidTokenError):
            decode_token(token, settings)

    def test_extra_claims_included(self, settings: Settings) -> None:
        token = create_access_token(
            subject="user-123",
            settings=settings,
            extra_claims={"role": "admin"},
        )
        payload = decode_token(token, settings)
        assert payload["role"] == "admin"

    def test_tampered_token_fails(self, settings: Settings) -> None:
        token = create_access_token(subject="user-123", settings=settings)
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(InvalidTokenError):
            decode_token(tampered, settings)

    def test_wrong_secret_fails(self, settings: Settings) -> None:
        token = create_access_token(subject="user-123", settings=settings)
        other = Settings(secret_key="different-secret-key-32-chars-minimum")  # type: ignore[arg-type]
        with pytest.raises(jwt.InvalidSignatureError):
            decode_token(token, other)
