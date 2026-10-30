"""
Tests for Identity and Argon2id Password Management
"""

import pytest
from security.identity.passwords import (
    hash_password,
    verify_password,
    needs_rehash,
    benchmark_argon2id,
)


def test_password_hash_and_verify():
    pwd = "CorrectOrbitronPassword#2026"
    h = hash_password(pwd)
    assert h.startswith("$argon2id$")

    assert verify_password(pwd, h) is True
    assert verify_password("WrongPassword123", h) is False
    assert verify_password("", h) is False
    assert verify_password(pwd, "") is False


def test_needs_rehash():
    pwd = "ValidPasswordToRehash1!"
    h = hash_password(pwd)
    assert needs_rehash(h) is False
    assert needs_rehash("corrupted_hash") is True


def test_empty_password_rejected():
    with pytest.raises(ValueError):
        hash_password("")


def test_benchmark_argon2id():
    bench = benchmark_argon2id(iterations=1)
    assert bench["algorithm"] == "Argon2id"
    assert bench["time_cost"] == 2
    assert bench["memory_cost_kib"] == 19456
    assert bench["parallelism"] == 1
    assert bench["avg_duration_ms"] > 0
