"""
Controlled Security Challenge Builders for Orbitron
"""

import base64
import os
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Union
import jwt

from security.contracts import (
    ACTION_RECEIVE_AND_FORWARD,
    PAYLOAD_VERSION,
    PAYLOAD_ALGORITHM,
    TOKEN_ALGORITHM,
    TOKEN_HEADER_TYP,
    TOKEN_ISSUER,
    TOKEN_AUDIENCE,
    to_iso_z,
    parse_iso,
    REASON_TOKEN_EXPIRED,
    REASON_WRONG_STATION,
    REASON_PAYLOAD_INTEGRITY_FAILED,
)
from security.payload.associated_data import canonical_payload_aad
from security.payload.encryption import encrypt_payload
from security.policy.scopes import build_scope
from security.tokens.keys import (
    derive_public_key_fingerprint,
    load_private_key_pem,
)


def _ensure_mock_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure context contains standard valid baseline records for isolated testing."""
    ctx = dict(context or {})
    base_time = parse_iso(ctx.get("server_time") or "2026-10-31T06:00:00Z")

    ctx.setdefault("scenario_id", "scenario-test-sec")
    ctx.setdefault("authorization_id", "auth-test-sec-001")
    ctx.setdefault("server_time", to_iso_z(base_time))
    ctx.setdefault("simulation_time", to_iso_z(base_time + timedelta(minutes=10)))

    ctx.setdefault("satellite", {
        "id": "sat-test-01",
        "owner_org_id": "org-alpha",
        "operational_status": "operational",
        "usable": True,
    })
    ctx.setdefault("station", {
        "id": "gs-a-001",
        "owner_org_id": "org-alpha",
        "operational_status": "operational",
        "usable": True,
        "sharing_enabled": True,
    })
    ctx.setdefault("antenna", {
        "id": "ant-a-001",
        "station_id": ctx["station"]["id"],
        "supported_bands": ["X", "S"],
        "operational_status": "operational",
        "usable": True,
    })
    ctx.setdefault("job", {
        "id": "job-test-01",
        "satellite_id": ctx["satellite"]["id"],
        "owner_org_id": "org-alpha",
        "status": "scheduled",
    })
    ctx.setdefault("contact", {
        "id": "contact-test-01",
        "job_id": ctx["job"]["id"],
        "satellite_id": ctx["satellite"]["id"],
        "station_id": ctx["station"]["id"],
        "antenna_id": ctx["antenna"]["id"],
        "band": "X",
        "start_at": to_iso_z(base_time + timedelta(minutes=5)),
        "end_at": to_iso_z(base_time + timedelta(minutes=25)),
        "status": "confirmed",
        "schedule_version": 1,
    })
    return ctx


def build_security_challenge(
    test_case: str,
    context: Dict[str, Any],
    private_key: Union[bytes, str],
) -> Dict[str, Any]:
    """
    Prepare an isolated negative security challenge.

    Supported test cases:
    - 'expired_authorization': Validly signed token with expiration in the past.
    - 'wrong_station': Valid token issued for Station A, challenged against Station B.
    - 'tampered_payload': Valid envelope with modified ciphertext byte failing AES-GCM tag verification.

    Args:
        test_case: Name of the security check test case.
        context: Context dictionary (can be partial; defaults applied for missing entities).
        private_key: Ed25519 issuer private key for token signing.

    Returns:
        dict: Challenge specification containing test payload, expected outcome, and verification parameters.
    """
    ctx = _ensure_mock_context(context)
    priv_key_obj = load_private_key_pem(private_key)
    kid = derive_public_key_fingerprint(priv_key_obj.public_key())
    srv_dt = parse_iso(ctx["server_time"])

    contact = ctx["contact"]
    scope = build_scope(
        scenario_id=ctx["scenario_id"],
        authorization_id=ctx["authorization_id"],
        satellite_id=ctx["satellite"]["id"],
        station_id=ctx["station"]["id"],
        antenna_id=ctx["antenna"]["id"],
        contact_id=contact["id"],
        owner_org_id=ctx["job"]["owner_org_id"],
        contact_start_at=contact["start_at"],
        contact_end_at=contact["end_at"],
        schedule_version=contact.get("schedule_version", 1),
        allowed_action=ACTION_RECEIVE_AND_FORWARD,
    )

    if test_case == "expired_authorization":
        # Create token with expiry in the past relative to server_time
        t_server = int(srv_dt.timestamp())
        exp = t_server - 30        # Expired 30 seconds ago
        iat = exp - 300            # Issued 330 seconds ago
        nbf = iat

        claims = {
            "iss": TOKEN_ISSUER,
            "aud": TOKEN_AUDIENCE,
            "sub": f"station:{scope['station_id']}",
            "jti": scope["authorization_id"],
            "iat": iat,
            "nbf": nbf,
            "exp": exp,
            "contract_version": "orbitron.v1",
            "scope": scope,
        }
        token = jwt.encode(
            claims,
            priv_key_obj,
            algorithm=TOKEN_ALGORITHM,
            headers={"typ": TOKEN_HEADER_TYP, "alg": TOKEN_ALGORITHM, "kid": kid},
        )
        return {
            "test_case": "expired_authorization",
            "token": token,
            "expected_outcome": "Request rejected due to expired credentials or authorization window",
            "expected_reason_code": REASON_TOKEN_EXPIRED,
            "expected_scope": scope,
            "server_time": ctx["server_time"],
            "simulation_time": ctx["simulation_time"],
        }

    elif test_case == "wrong_station":
        # Create valid token for Station A
        t_server = int(srv_dt.timestamp())
        iat = t_server
        nbf = iat
        exp = iat + 300

        claims = {
            "iss": TOKEN_ISSUER,
            "aud": TOKEN_AUDIENCE,
            "sub": f"station:{scope['station_id']}",
            "jti": scope["authorization_id"],
            "iat": iat,
            "nbf": nbf,
            "exp": exp,
            "contract_version": "orbitron.v1",
            "scope": scope,
        }
        token = jwt.encode(
            claims,
            priv_key_obj,
            algorithm=TOKEN_ALGORITHM,
            headers={"typ": TOKEN_HEADER_TYP, "alg": TOKEN_ALGORITHM, "kid": kid},
        )

        # Expected scope presented at Station B
        target_station_id = "gs-b-001"
        station_b_scope = dict(scope)
        station_b_scope["station_id"] = target_station_id

        return {
            "test_case": "wrong_station",
            "token": token,
            "target_station_id": target_station_id,
            "expected_outcome": "Execution rejected due to station identity and scope mismatch",
            "expected_reason_code": REASON_WRONG_STATION,
            "expected_scope": station_b_scope,
            "server_time": ctx["server_time"],
            "simulation_time": ctx["simulation_time"],
        }

    elif test_case == "tampered_payload":
        # Create encrypted sample, then tamper with ciphertext byte
        key = os.urandom(32)
        plaintext = b"Orbitron mission test telemetry sample: " + os.urandom(256)
        plaintext_hash = hashlib.sha256(plaintext).hexdigest()

        aad_fields = {
            "contact_id": scope["contact_id"],
            "expected_plaintext_sha256": plaintext_hash,
            "owner_org_id": scope["owner_org_id"],
            "satellite_id": scope["satellite_id"],
            "scenario_id": scope["scenario_id"],
            "station_id": scope["station_id"],
            "transfer_id": "trans-test-tampered-001",
        }
        aad_bytes = canonical_payload_aad(aad_fields)
        valid_envelope = encrypt_payload(plaintext, key, aad_bytes)

        # Decode ciphertext, modify one byte, re-encode preserving envelope structure
        raw_ct = bytearray(base64.b64decode(valid_envelope["ciphertext_b64"]))
        raw_ct[0] ^= 0xFF  # Flip bits in first ciphertext byte
        tampered_envelope = {
            "version": PAYLOAD_VERSION,
            "algorithm": PAYLOAD_ALGORITHM,
            "nonce_b64": valid_envelope["nonce_b64"],
            "ciphertext_b64": base64.b64encode(bytes(raw_ct)).decode("ascii"),
        }

        return {
            "test_case": "tampered_payload",
            "envelope": tampered_envelope,
            "key": key,
            "associated_data": aad_bytes,
            "expected_outcome": "Integrity check failed: ciphertext SHA-256 does not match digest",
            "expected_reason_code": REASON_PAYLOAD_INTEGRITY_FAILED,
        }

    else:
        raise ValueError(f"Unsupported security test case: '{test_case}'. Supported cases: 'expired_authorization', 'wrong_station', 'tampered_payload'")
