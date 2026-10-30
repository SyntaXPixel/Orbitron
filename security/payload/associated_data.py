"""
Canonical Associated Data (AAD) Encoding for Orbitron Payloads
"""

import json
from typing import Dict, Any

from security.contracts import MAX_AAD_BYTES
from security.exceptions import EnvelopeValidationError

REQUIRED_AAD_FIELDS = (
    "contact_id",
    "expected_plaintext_sha256",
    "owner_org_id",
    "satellite_id",
    "scenario_id",
    "station_id",
    "transfer_id",
)


def canonical_payload_aad(fields: Dict[str, Any]) -> bytes:
    """
    Encode canonical associated data for AES-256-GCM encryption/decryption.

    Args:
        fields: Dictionary containing exactly the 7 required metadata fields.

    Returns:
        bytes: UTF-8 encoded compact JSON with sorted keys.

    Raises:
        EnvelopeValidationError: If required fields are missing, unrecognized fields exist,
                                or values are not strings.
        ValueError: If encoded AAD exceeds maximum allowed size (4 KiB).
    """
    if not isinstance(fields, dict):
        raise EnvelopeValidationError("AAD fields must be provided as a dictionary")

    provided_keys = set(fields.keys())
    required_keys = set(REQUIRED_AAD_FIELDS)

    if provided_keys != required_keys:
        missing = sorted(list(required_keys - provided_keys))
        extra = sorted(list(provided_keys - required_keys))
        err_parts = []
        if missing:
            err_parts.append(f"missing fields: {missing}")
        if extra:
            err_parts.append(f"unrecognized fields: {extra}")
        raise EnvelopeValidationError(f"Invalid AAD fields: {', '.join(err_parts)}")

    # Strict string validation
    for k in REQUIRED_AAD_FIELDS:
        val = fields[k]
        if not isinstance(val, str):
            raise EnvelopeValidationError(f"AAD field '{k}' must be a string, got {type(val).__name__}")

    encoded = json.dumps(fields, sort_keys=True, separators=(',', ':')).encode("utf-8")

    if len(encoded) > MAX_AAD_BYTES:
        raise ValueError(f"Canonical AAD size ({len(encoded)} bytes) exceeds maximum limit ({MAX_AAD_BYTES} bytes)")

    return encoded
