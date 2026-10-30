"""
Tests for Authenticated Payload Encryption (AES-256-GCM) and Canonical AAD
"""

import os
import base64
import pytest
import hashlib

from security.payload.encryption import encrypt_payload, decrypt_payload
from security.payload.associated_data import canonical_payload_aad
from security.exceptions import (
    EnvelopeValidationError,
    PayloadIntegrityError,
    SecurityConfigurationError,
)
from security.contracts import MAX_PLAINTEXT_BYTES


@pytest.fixture
def sample_aad():
    fields = {
        "scenario_id": "scenario-test-01",
        "transfer_id": "trans-001",
        "contact_id": "contact-001",
        "satellite_id": "sat-001",
        "station_id": "gs-001",
        "owner_org_id": "org-alpha",
        "expected_plaintext_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    }
    return canonical_payload_aad(fields)


@pytest.fixture
def valid_key():
    return os.urandom(32)


def test_encryption_decryption_roundtrip(valid_key, sample_aad):
    plaintext = b"Orbitron satellite payload telemetry test data roundtrip."
    envelope = encrypt_payload(plaintext, valid_key, sample_aad)

    assert envelope["version"] == "orbitron.payload.v1"
    assert envelope["algorithm"] == "AES-256-GCM"
    assert "nonce_b64" in envelope
    assert "ciphertext_b64" in envelope

    # Plaintext and key must not be present in envelope
    assert "plaintext" not in envelope
    assert "key" not in envelope

    recovered = decrypt_payload(envelope, valid_key, sample_aad)
    assert recovered == plaintext


def test_invalid_key_length_rejected(sample_aad):
    plaintext = b"test"
    bad_key = os.urandom(16)  # 16 bytes instead of 32

    with pytest.raises(SecurityConfigurationError):
        encrypt_payload(plaintext, bad_key, sample_aad)

    valid_env = encrypt_payload(plaintext, os.urandom(32), sample_aad)
    with pytest.raises(SecurityConfigurationError):
        decrypt_payload(valid_env, bad_key, sample_aad)


def test_tampered_ciphertext_fails_integrity(valid_key, sample_aad):
    plaintext = b"Confidential telemetry bytes"
    envelope = encrypt_payload(plaintext, valid_key, sample_aad)

    # Tamper with raw ciphertext byte
    raw_ct = bytearray(base64.b64decode(envelope["ciphertext_b64"]))
    raw_ct[4] ^= 0xFF
    tampered_envelope = dict(envelope)
    tampered_envelope["ciphertext_b64"] = base64.b64encode(bytes(raw_ct)).decode("ascii")

    with pytest.raises(PayloadIntegrityError):
        decrypt_payload(tampered_envelope, valid_key, sample_aad)


def test_tampered_aad_fails_integrity(valid_key, sample_aad):
    plaintext = b"Confidential telemetry bytes"
    envelope = encrypt_payload(plaintext, valid_key, sample_aad)

    tampered_aad = sample_aad + b"tamper"

    with pytest.raises(PayloadIntegrityError):
        decrypt_payload(envelope, valid_key, tampered_aad)


def test_wrong_key_fails_integrity(valid_key, sample_aad):
    plaintext = b"Confidential telemetry bytes"
    envelope = encrypt_payload(plaintext, valid_key, sample_aad)

    wrong_key = os.urandom(32)
    with pytest.raises(PayloadIntegrityError):
        decrypt_payload(envelope, wrong_key, sample_aad)


def test_malformed_envelope_rejected(valid_key, sample_aad):
    # Non-dictionary
    with pytest.raises(EnvelopeValidationError):
        decrypt_payload("not-a-dict", valid_key, sample_aad)

    # Unsupported version
    with pytest.raises(EnvelopeValidationError):
        decrypt_payload({
            "version": "orbitron.payload.v2",
            "algorithm": "AES-256-GCM",
            "nonce_b64": base64.b64encode(os.urandom(12)).decode("ascii"),
            "ciphertext_b64": base64.b64encode(os.urandom(32)).decode("ascii"),
        }, valid_key, sample_aad)

    # Unsupported algorithm
    with pytest.raises(EnvelopeValidationError):
        decrypt_payload({
            "version": "orbitron.payload.v1",
            "algorithm": "CHACHA20-POLY1305",
            "nonce_b64": base64.b64encode(os.urandom(12)).decode("ascii"),
            "ciphertext_b64": base64.b64encode(os.urandom(32)).decode("ascii"),
        }, valid_key, sample_aad)

    # Invalid base64
    with pytest.raises(EnvelopeValidationError):
        decrypt_payload({
            "version": "orbitron.payload.v1",
            "algorithm": "AES-256-GCM",
            "nonce_b64": "!!!not_valid_b64!!!",
            "ciphertext_b64": base64.b64encode(os.urandom(32)).decode("ascii"),
        }, valid_key, sample_aad)


def test_plaintext_size_limit_enforced(valid_key, sample_aad):
    oversized = b"x" * (MAX_PLAINTEXT_BYTES + 1)
    with pytest.raises(ValueError):
        encrypt_payload(oversized, valid_key, sample_aad)


def test_canonical_aad_field_validation():
    valid_fields = {
        "scenario_id": "s1",
        "transfer_id": "t1",
        "contact_id": "c1",
        "satellite_id": "sat1",
        "station_id": "gs1",
        "owner_org_id": "org1",
        "expected_plaintext_sha256": "abc",
    }
    aad = canonical_payload_aad(valid_fields)
    assert isinstance(aad, bytes)

    # Missing field
    missing_fields = dict(valid_fields)
    del missing_fields["satellite_id"]
    with pytest.raises(EnvelopeValidationError):
        canonical_payload_aad(missing_fields)

    # Unrecognized extra field
    extra_fields = dict(valid_fields)
    extra_fields["secret_key"] = "leak"
    with pytest.raises(EnvelopeValidationError):
        canonical_payload_aad(extra_fields)


def test_unique_nonces_generated(valid_key, sample_aad):
    plaintext = b"Identical plaintext for nonce uniqueness check"
    env1 = encrypt_payload(plaintext, valid_key, sample_aad)
    env2 = encrypt_payload(plaintext, valid_key, sample_aad)

    # Fresh random nonces ensure ciphertexts and nonces differ
    assert env1["nonce_b64"] != env2["nonce_b64"]
    assert env1["ciphertext_b64"] != env2["ciphertext_b64"]
