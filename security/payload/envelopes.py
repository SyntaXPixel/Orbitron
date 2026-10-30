"""
Orbitron Payload Envelope Definitions and Validation
"""

import base64
from typing import Dict, Any, Tuple

from security.contracts import (
    MAX_PLAINTEXT_BYTES,
    NONCE_SIZE_BYTES,
    PAYLOAD_ALGORITHM,
    PAYLOAD_VERSION,
    TAG_SIZE_BYTES,
)
from security.exceptions import EnvelopeValidationError

REQUIRED_ENVELOPE_FIELDS = ("version", "algorithm", "nonce_b64", "ciphertext_b64")


def build_envelope(nonce: bytes, ciphertext_with_tag: bytes) -> Dict[str, str]:
    """Construct a canonical payload envelope with strict base64 encoding."""
    return {
        "version": PAYLOAD_VERSION,
        "algorithm": PAYLOAD_ALGORITHM,
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext_with_tag).decode("ascii"),
    }


def parse_and_validate_envelope(envelope: Dict[str, Any]) -> Tuple[bytes, bytes]:
    """
    Validate envelope format, versions, and strictly decode nonce and ciphertext bytes.

    Returns:
        Tuple[bytes, bytes]: (nonce, ciphertext_with_tag)

    Raises:
        EnvelopeValidationError: On malformed envelope or invalid encoding.
    """
    if not isinstance(envelope, dict):
        raise EnvelopeValidationError("Payload envelope must be a dictionary")

    for f in REQUIRED_ENVELOPE_FIELDS:
        if f not in envelope or not isinstance(envelope[f], str):
            raise EnvelopeValidationError(f"Envelope missing required string field: '{f}'")

    if envelope["version"] != PAYLOAD_VERSION:
        raise EnvelopeValidationError(f"Unsupported payload version: '{envelope['version']}' (expected '{PAYLOAD_VERSION}')")

    if envelope["algorithm"] != PAYLOAD_ALGORITHM:
        raise EnvelopeValidationError(f"Unsupported algorithm: '{envelope['algorithm']}' (expected '{PAYLOAD_ALGORITHM}')")

    # Strict base64 decoding
    try:
        nonce = base64.b64decode(envelope["nonce_b64"], validate=True)
    except Exception as e:
        raise EnvelopeValidationError(f"Invalid base64 in nonce_b64: {e}") from None

    if len(nonce) != NONCE_SIZE_BYTES:
        raise EnvelopeValidationError(f"Invalid nonce length: expected {NONCE_SIZE_BYTES} bytes, got {len(nonce)}")

    try:
        ciphertext = base64.b64decode(envelope["ciphertext_b64"], validate=True)
    except Exception as e:
        raise EnvelopeValidationError(f"Invalid base64 in ciphertext_b64: {e}") from None

    if len(ciphertext) < TAG_SIZE_BYTES:
        raise EnvelopeValidationError(f"Ciphertext is shorter than minimum authentication tag ({TAG_SIZE_BYTES} bytes)")

    if len(ciphertext) > MAX_PLAINTEXT_BYTES + TAG_SIZE_BYTES:
        raise EnvelopeValidationError(f"Ciphertext exceeds maximum supported payload limit ({MAX_PLAINTEXT_BYTES} bytes)")

    return nonce, ciphertext
