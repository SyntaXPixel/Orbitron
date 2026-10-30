"""
Orbitron Security Module Contracts and Constants
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union

# Shared API and Envelope Contracts
CONTRACT_VERSION = "orbitron.v1"
PAYLOAD_VERSION = "orbitron.payload.v1"

# Algorithms and JWT configuration
PAYLOAD_ALGORITHM = "AES-256-GCM"
TOKEN_ALGORITHM = "EdDSA"
TOKEN_HEADER_TYP = "orbitron-contact+jwt"
TOKEN_ISSUER = "orbitron-local"
TOKEN_AUDIENCE = "orbitron-payload-relay"

# Allowed Actions
ACTION_RECEIVE_AND_FORWARD = "receive_and_forward"
SUPPORTED_ACTIONS = {ACTION_RECEIVE_AND_FORWARD}

# Cryptographic and Operational Limits
KEY_SIZE_BYTES = 32
NONCE_SIZE_BYTES = 12
TAG_SIZE_BYTES = 16
MAX_PLAINTEXT_BYTES = 1_048_576       # 1 MiB
MAX_AAD_BYTES = 4_096                 # 4 KiB
DEFAULT_TOKEN_LIFETIME_SECONDS = 300  # 5 minutes
MAX_TOKEN_LIFETIME_SECONDS = 600      # 10 minutes
DEFAULT_PRE_START_INTERVAL_SECONDS = 60  # Simulation window advance
MAX_CONTEXT_AGE_SECONDS = 5.0         # Real-time freshness limit

# Standard Reason Codes (Section 25)
REASON_AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
REASON_PARTNER_NOT_APPROVED = "PARTNER_NOT_APPROVED"
REASON_STATION_OFFLINE = "STATION_OFFLINE"
REASON_INVALID_TOKEN = "INVALID_TOKEN"
REASON_INVALID_SIGNATURE = "INVALID_SIGNATURE"
REASON_INVALID_ALGORITHM = "INVALID_ALGORITHM"
REASON_TOKEN_EXPIRED = "TOKEN_EXPIRED"
REASON_CONTACT_NOT_STARTED = "CONTACT_NOT_STARTED"
REASON_CONTACT_ENDED = "CONTACT_ENDED"
REASON_WRONG_STATION = "WRONG_STATION"
REASON_SCOPE_MISMATCH = "SCOPE_MISMATCH"
REASON_WRONG_SCENARIO = "WRONG_SCENARIO"
REASON_AUTHORIZATION_REVOKED = "AUTHORIZATION_REVOKED"
REASON_CONTEXT_STALE = "CONTEXT_STALE"
REASON_INVALID_ENVELOPE = "INVALID_ENVELOPE"
REASON_PAYLOAD_INTEGRITY_FAILED = "PAYLOAD_INTEGRITY_FAILED"
REASON_SECURITY_UNAVAILABLE = "SECURITY_UNAVAILABLE"
REASON_UNUSABLE_RESOURCE = "UNUSABLE_RESOURCE"
REASON_UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
REASON_BAND_NOT_SUPPORTED = "BAND_NOT_SUPPORTED"
REASON_INVALID_CONTACT_BOUNDS = "INVALID_CONTACT_BOUNDS"


def make_reason(code: str, message: str, resource_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Build a structured Reason object adhering to the Orbitron data contract."""
    return {
        "code": code,
        "message": message,
        "resource_ids": resource_ids or []
    }


def parse_iso(val: Union[str, datetime]) -> datetime:
    """Parse an ISO 8601 string or normalize a datetime object into a UTC datetime."""
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, str):
        cleaned = val.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    raise ValueError(f"Cannot parse timestamp value: {val!r}")


def to_iso_z(val: Union[str, datetime]) -> str:
    """Format a UTC datetime to standard ISO 8601 string ending with 'Z'."""
    dt = parse_iso(val)
    return dt.isoformat().replace("+00:00", "Z")
