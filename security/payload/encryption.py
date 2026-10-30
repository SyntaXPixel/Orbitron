"""
Authenticated Encryption and Decryption for Orbitron Payloads (AES-256-GCM)
"""

import os
from typing import Dict, Any, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from security.contracts import (
    KEY_SIZE_BYTES,
    MAX_AAD_BYTES,
    MAX_PLAINTEXT_BYTES,
    NONCE_SIZE_BYTES,
)
from security.exceptions import (
    EnvelopeValidationError,
    PayloadIntegrityError,
    SecurityConfigurationError,
)
from security.payload.envelopes import (
    build_envelope,
    parse_and_validate_envelope,
)


def encrypt_payload(
    plaintext: bytes,
    key: bytes,
    associated_data: bytes,
) -> Dict[str, str]:
    """
    Encrypt plaintext bytes using AES-256-GCM with fresh secure nonce and authenticated associated data.

    Args:
        plaintext: Raw data bytes (up to 1 MiB).
        key: 32-byte secret AES-256 key.
        associated_data: Authenticated associated data bytes (up to 4 KiB).

    Returns:
        dict: Standard Orbitron payload envelope.

    Raises:
        SecurityConfigurationError: If key is not exactly 32 bytes.
        ValueError: If plaintext or associated data exceeds permitted size limits.
        TypeError: If arguments are of incorrect types.
    """
    if not isinstance(key, (bytes, bytearray)) or len(key) != KEY_SIZE_BYTES:
        raise SecurityConfigurationError(f"AES-256 key must be exactly {KEY_SIZE_BYTES} bytes, got {len(key) if isinstance(key, (bytes, bytearray)) else type(key).__name__}")

    if not isinstance(plaintext, (bytes, bytearray)):
        raise TypeError(f"Plaintext must be bytes, got {type(plaintext).__name__}")

    if len(plaintext) > MAX_PLAINTEXT_BYTES:
        raise ValueError(f"Plaintext size ({len(plaintext)} bytes) exceeds limit ({MAX_PLAINTEXT_BYTES} bytes)")

    if not isinstance(associated_data, (bytes, bytearray)):
        raise TypeError(f"Associated data must be bytes, got {type(associated_data).__name__}")

    if len(associated_data) > MAX_AAD_BYTES:
        raise ValueError(f"Associated data size ({len(associated_data)} bytes) exceeds limit ({MAX_AAD_BYTES} bytes)")

    # Cryptographically secure fresh nonce
    nonce = os.urandom(NONCE_SIZE_BYTES)

    aesgcm = AESGCM(bytes(key))
    ciphertext_with_tag = aesgcm.encrypt(nonce, bytes(plaintext), bytes(associated_data))

    return build_envelope(nonce=nonce, ciphertext_with_tag=ciphertext_with_tag)


def decrypt_payload(
    envelope: Dict[str, Any],
    key: bytes,
    associated_data: bytes,
) -> bytes:
    """
    Decrypt and verify an AES-256-GCM encrypted payload envelope.

    Args:
        envelope: Standard payload envelope dictionary.
        key: 32-byte secret AES-256 key.
        associated_data: Canonical associated data bytes.

    Returns:
        bytes: Verified recovered plaintext.

    Raises:
        SecurityConfigurationError: If key length is invalid.
        EnvelopeValidationError: If envelope structure, algorithm, or base64 encoding is invalid.
        PayloadIntegrityError: If cryptographic authentication / integrity tag fails.
    """
    if not isinstance(key, (bytes, bytearray)) or len(key) != KEY_SIZE_BYTES:
        raise SecurityConfigurationError(f"AES-256 key must be exactly {KEY_SIZE_BYTES} bytes")

    if not isinstance(associated_data, (bytes, bytearray)):
        raise TypeError("Associated data must be bytes")

    if len(associated_data) > MAX_AAD_BYTES:
        raise ValueError(f"Associated data size exceeds limit ({MAX_AAD_BYTES} bytes)")

    nonce, ciphertext = parse_and_validate_envelope(envelope)

    aesgcm = AESGCM(bytes(key))
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, bytes(associated_data))
        return plaintext
    except Exception:
        # Prevent key material or ciphertext leakage in exceptions; return no plaintext
        raise PayloadIntegrityError("Payload integrity verification failed: ciphertext or associated data has been tampered with") from None
