"""API key authentication.

This starter uses an in-memory set of valid keys for simplicity. For
production with many keys or per-key permissions, store hashed keys in the
database — see the User model for the pattern.

Configure keys via env var: `API_KEYS=key1,key2,key3` (or empty to disable).
"""

import hmac
import os


def _load_keys() -> set[str]:
    raw = os.environ.get("API_KEYS", "")
    return {k.strip() for k in raw.split(",") if k.strip()}


_VALID_KEYS = _load_keys()


def is_valid_api_key(provided: str | None) -> bool:
    """Constant-time check against the configured keys."""
    if not provided or not _VALID_KEYS:
        return False
    # hmac.compare_digest gives constant-time comparison per key.
    return any(hmac.compare_digest(provided, k) for k in _VALID_KEYS)


def reload_keys() -> None:
    """Re-read API_KEYS env var. Useful in tests."""
    global _VALID_KEYS
    _VALID_KEYS = _load_keys()
