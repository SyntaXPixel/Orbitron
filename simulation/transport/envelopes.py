"""Packaging and helpers for cryptographic envelopes and associated data."""

from __future__ import annotations

import base64
import json
from typing import Any, Dict
from simulation.contracts import PAYLOAD_ENVELOPE_VERSION, PayloadAssociatedData, PayloadEnvelope


def create_payload_envelope(nonce: bytes, ciphertext: bytes) -> Dict[str, Any]:
    """Package nonce and ciphertext into standard orbitron.payload.v1 dictionary."""
    return {
        "version": PAYLOAD_ENVELOPE_VERSION,
        "algorithm": "AES-256-GCM",
        "nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
    }


def parse_payload_envelope(data: Dict[str, Any]) -> PayloadEnvelope:
    """Parse and validate envelope format."""
    return PayloadEnvelope(**data)


def parse_associated_data(data: Dict[str, Any]) -> PayloadAssociatedData:
    """Parse and validate canonical associated data."""
    return PayloadAssociatedData(**data)

