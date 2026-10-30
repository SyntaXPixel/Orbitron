"""
Argon2id Password Hashing and Verification for Orbitron
"""

import time
from typing import Dict, Any
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError, InvalidHash

# Configuration adhering to Section 8:
# Minimum: memory: 19 MiB (19456 KiB), iterations: 2, parallelism: 1
DEFAULT_TIME_COST = 2
DEFAULT_MEMORY_COST = 19456  # 19 MiB
DEFAULT_PARALLELISM = 1
DEFAULT_HASH_LEN = 32
DEFAULT_SALT_LEN = 16

_hasher = PasswordHasher(
    time_cost=DEFAULT_TIME_COST,
    memory_cost=DEFAULT_MEMORY_COST,
    parallelism=DEFAULT_PARALLELISM,
    hash_len=DEFAULT_HASH_LEN,
    salt_len=DEFAULT_SALT_LEN,
    type=Type.ID,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2id using library-managed salts."""
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored Argon2 hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return _hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHash, Exception):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Determine whether a stored hash needs upgrading to current parameters."""
    try:
        return _hasher.check_needs_rehash(hashed_password)
    except Exception:
        return True


def benchmark_argon2id(iterations: int = 3) -> Dict[str, Any]:
    """Benchmark the Argon2id parameter configuration on the local machine."""
    sample = "OrbitronBenchmarkPassword123!"
    timings = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        h = _hasher.hash(sample)
        _hasher.verify(h, sample)
        t1 = time.perf_counter()
        timings.append((t1 - t0) * 1000.0)

    avg_ms = sum(timings) / len(timings)
    return {
        "time_cost": DEFAULT_TIME_COST,
        "memory_cost_kib": DEFAULT_MEMORY_COST,
        "parallelism": DEFAULT_PARALLELISM,
        "algorithm": "Argon2id",
        "avg_duration_ms": round(avg_ms, 2),
    }
