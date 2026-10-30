"""
Tests for Contact Token Issuance and Strict Verification
"""

import pytest
from datetime import datetime, timezone, timedelta
import jwt

from security.tokens.keys import (
    generate_keypair,
    private_key_to_pem,
    public_key_to_pem,
    derive_public_key_fingerprint,
)
from security.tokens.issuer import issue_contact_token
from security.tokens.verifier import verify_contact_token
from security.contracts import to_iso_z, parse_iso
from security.exceptions import PolicyDeniedError


@pytest.fixture
def keypair():
    priv, pub = generate_keypair()
    return private_key_to_pem(priv), public_key_to_pem(pub)


@pytest.fixture
def token_context():
    base_time = datetime(2026, 10, 31, 14, 0, 0, tzinfo=timezone.utc)
    srv_time_str = to_iso_z(base_time)
    sim_time_str = to_iso_z(base_time + timedelta(minutes=10))

    return {
        "scenario_id": "scen-tok-01",
        "authorization_id": "auth-tok-01",
        "server_time": srv_time_str,
        "simulation_time": sim_time_str,
        "satellite": {
            "id": "sat-t-001",
            "owner_org_id": "org-alpha",
            "operational_status": "operational",
            "usable": True,
        },
        "station": {
            "id": "gs-t-001",
            "owner_org_id": "org-alpha",
            "operational_status": "operational",
            "usable": True,
            "sharing_enabled": True,
        },
        "antenna": {
            "id": "ant-t-001",
            "station_id": "gs-t-001",
            "supported_bands": ["X"],
            "operational_status": "operational",
            "usable": True,
        },
        "job": {
            "id": "job-t-001",
            "satellite_id": "sat-t-001",
            "owner_org_id": "org-alpha",
            "status": "scheduled",
        },
        "contact": {
            "id": "contact-t-001",
            "job_id": "job-t-001",
            "satellite_id": "sat-t-001",
            "station_id": "gs-t-001",
            "antenna_id": "ant-t-001",
            "band": "X",
            "start_at": to_iso_z(base_time + timedelta(minutes=5)),
            "end_at": to_iso_z(base_time + timedelta(minutes=25)),
            "status": "confirmed",
            "schedule_version": 1,
        },
    }


def test_token_issuance_and_verification_roundtrip(keypair, token_context):
    priv_pem, pub_pem = keypair
    grant = issue_contact_token(token_context, priv_pem)

    assert "token" in grant
    assert "expires_at" in grant
    assert "scope" in grant

    res = verify_contact_token(
        token=grant["token"],
        public_key=pub_pem,
        expected_scope=grant["scope"],
        server_time=token_context["server_time"],
        simulation_time=token_context["simulation_time"],
    )
    assert res["allowed"] is True
    assert res["reasons"] == []
    assert res["claims"] is not None
    assert res["claims"]["iss"] == "orbitron-local"
    assert res["claims"]["aud"] == "orbitron-payload-relay"
    assert res["claims"]["sub"] == "station:gs-t-001"
    assert res["claims"]["contract_version"] == "orbitron.v1"


def test_tampered_signature_rejected(keypair, token_context):
    priv_pem, pub_pem = keypair
    grant = issue_contact_token(token_context, priv_pem)
    raw_token = grant["token"]

    # Tamper with signature segment
    parts = raw_token.split(".")
    tampered_sig = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

    res = verify_contact_token(
        token=tampered_token,
        public_key=pub_pem,
        expected_scope=grant["scope"],
        server_time=token_context["server_time"],
        simulation_time=token_context["simulation_time"],
    )
    assert res["allowed"] is False
    assert any(r["code"] == "INVALID_SIGNATURE" for r in res["reasons"])
    assert res["claims"] is None


def test_wrong_algorithm_rejected(keypair, token_context):
    priv_pem, pub_pem = keypair
    grant = issue_contact_token(token_context, priv_pem)

    # Craft token with HS256 header and algorithm
    parts = grant["token"].split(".")
    fake_header = jwt.utils.base64url_encode(b'{"typ":"orbitron-contact+jwt","alg":"HS256"}').decode("ascii")
    fake_token = f"{fake_header}.{parts[1]}.{parts[2]}"

    res = verify_contact_token(
        token=fake_token,
        public_key=pub_pem,
        expected_scope=grant["scope"],
        server_time=token_context["server_time"],
        simulation_time=token_context["simulation_time"],
    )
    assert res["allowed"] is False
    assert any(r["code"] == "INVALID_ALGORITHM" for r in res["reasons"])


def test_wrong_issuer_and_audience_rejected(keypair, token_context):
    priv_pem, pub_pem = keypair
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    priv_obj = load_pem_private_key(priv_pem, password=None)

    # Token with wrong issuer
    claims_bad_iss = {
        "iss": "orbitron-rogue",
        "aud": "orbitron-payload-relay",
        "sub": "station:gs-t-001",
        "jti": "auth-001",
        "iat": 1700000000,
        "nbf": 1700000000,
        "exp": 1700000300,
        "contract_version": "orbitron.v1",
        "scope": token_context["contact"],
    }
    tok_bad_iss = jwt.encode(claims_bad_iss, priv_obj, algorithm="EdDSA", headers={"typ": "orbitron-contact+jwt"})

    grant_scope = {"station_id": "gs-t-001"}
    res = verify_contact_token(
        token=tok_bad_iss,
        public_key=pub_pem,
        expected_scope=grant_scope,
        server_time="2023-11-14T22:13:20Z",
        simulation_time="2023-11-14T22:15:00Z",
    )
    assert res["allowed"] is False
    assert any(r["code"] == "INVALID_TOKEN" for r in res["reasons"])


def test_real_time_expiry_enforced(keypair, token_context):
    priv_pem, pub_pem = keypair
    grant = issue_contact_token(token_context, priv_pem)

    # Verify at server_time far in the future
    future_srv_time = to_iso_z(parse_iso(token_context["server_time"]) + timedelta(minutes=10))

    res = verify_contact_token(
        token=grant["token"],
        public_key=pub_pem,
        expected_scope=grant["scope"],
        server_time=future_srv_time,
        simulation_time=token_context["simulation_time"],
    )
    assert res["allowed"] is False
    assert any(r["code"] == "TOKEN_EXPIRED" for r in res["reasons"])


def test_simulation_time_bounds_enforced(keypair, token_context):
    priv_pem, pub_pem = keypair
    grant = issue_contact_token(token_context, priv_pem)

    c_start = parse_iso(grant["scope"]["contact_start_at"])
    c_end = parse_iso(grant["scope"]["contact_end_at"])

    # Simulation time before contact start
    before_sim = to_iso_z(c_start - timedelta(seconds=10))
    res_before = verify_contact_token(
        token=grant["token"],
        public_key=pub_pem,
        expected_scope=grant["scope"],
        server_time=token_context["server_time"],
        simulation_time=before_sim,
    )
    assert res_before["allowed"] is False
    assert any(r["code"] == "CONTACT_NOT_STARTED" for r in res_before["reasons"])

    # Simulation time after contact end
    after_sim = to_iso_z(c_end + timedelta(seconds=1))
    res_after = verify_contact_token(
        token=grant["token"],
        public_key=pub_pem,
        expected_scope=grant["scope"],
        server_time=token_context["server_time"],
        simulation_time=after_sim,
    )
    assert res_after["allowed"] is False
    assert any(r["code"] == "CONTACT_ENDED" for r in res_after["reasons"])


def test_wrong_station_rejected(keypair, token_context):
    priv_pem, pub_pem = keypair
    grant = issue_contact_token(token_context, priv_pem)

    expected_scope = dict(grant["scope"])
    expected_scope["station_id"] = "gs-different-002"

    res = verify_contact_token(
        token=grant["token"],
        public_key=pub_pem,
        expected_scope=expected_scope,
        server_time=token_context["server_time"],
        simulation_time=token_context["simulation_time"],
    )
    assert res["allowed"] is False
    assert any(r["code"] == "WRONG_STATION" for r in res["reasons"])


def test_revoked_grant_rejected(keypair, token_context):
    priv_pem, pub_pem = keypair
    grant = issue_contact_token(token_context, priv_pem)

    expected_scope = dict(grant["scope"])
    expected_scope["authorization_status"] = "revoked"

    res = verify_contact_token(
        token=grant["token"],
        public_key=pub_pem,
        expected_scope=expected_scope,
        server_time=token_context["server_time"],
        simulation_time=token_context["simulation_time"],
    )
    assert res["allowed"] is False
    assert any(r["code"] == "AUTHORIZATION_REVOKED" for r in res["reasons"])


def test_stale_context_rejected(keypair, token_context):
    priv_pem, pub_pem = keypair
    grant = issue_contact_token(token_context, priv_pem)

    srv_dt = parse_iso(token_context["server_time"])
    # Context observed 10 seconds ago (> 5s limit)
    stale_observed = to_iso_z(srv_dt - timedelta(seconds=10))

    expected_scope = dict(grant["scope"])
    expected_scope["context_observed_at"] = stale_observed

    res = verify_contact_token(
        token=grant["token"],
        public_key=pub_pem,
        expected_scope=expected_scope,
        server_time=token_context["server_time"],
        simulation_time=token_context["simulation_time"],
    )
    assert res["allowed"] is False
    assert any(r["code"] == "CONTEXT_STALE" for r in res["reasons"])


def test_pre_start_issuance_timing_enforced(keypair, token_context):
    priv_pem, pub_pem = keypair
    # Set simulation time 5 minutes before contact start (pre-start is 60s)
    c_start = parse_iso(token_context["contact"]["start_at"])
    token_context["simulation_time"] = to_iso_z(c_start - timedelta(minutes=5))

    with pytest.raises(PolicyDeniedError) as exc_info:
        issue_contact_token(token_context, priv_pem)
    assert "Simulation time is outside issuance window" in str(exc_info.value)
