"""Password hashing with Argon2id.

Argon2id won the Password Hashing Competition (2015) and is the modern
default. Resistant to GPU and side-channel attacks. Use this over bcrypt
for new projects.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Sensible defaults — adjust based on benchmarks on production hardware.
# Higher time_cost/memory_cost = slower hashing = more attacker work.
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(plain: str) -> str:
    """Hash a plaintext password. Result is opaque, ~97 chars."""
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time verification. Returns False on mismatch (no exception)."""
    try:
        _hasher.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False


def needs_rehash(hashed: str) -> bool:
    """True if the hash uses outdated params and should be re-hashed on next login."""
    return _hasher.check_needs_rehash(hashed)
