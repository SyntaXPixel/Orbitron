"""
Tests for Controlled Security Challenges and Evidence
"""

import pytest
from security.tokens.keys import generate_keypair, private_key_to_pem, public_key_to_pem
from security.tokens.verifier import verify_contact_token
from security.payload.encryption import decrypt_payload
from security.testing.challenges import build_security_challenge
from security.testing.evidence import sanitize_audit_context, build_evidence_record
from security.exceptions import PayloadIntegrityError


@pytest.fixture
def keypair():
    priv, pub = generate_keypair()
    return private_key_to_pem(priv), public_key_to_pem(pub)


def test_expired_authorization_challenge(keypair):
    priv_pem, pub_pem = keypair
    challenge = build_security_challenge("expired_authorization", {}, priv_pem)

    assert challenge["test_case"] == "expired_authorization"
    assert challenge["expected_reason_code"] == "TOKEN_EXPIRED"

    res = verify_contact_token(
        token=challenge["token"],
        public_key=pub_pem,
        expected_scope=challenge["expected_scope"],
        server_time=challenge["server_time"],
        simulation_time=challenge["simulation_time"],
    )
    assert res["allowed"] is False
    assert any(r["code"] == "TOKEN_EXPIRED" for r in res["reasons"])


def test_wrong_station_challenge(keypair):
    priv_pem, pub_pem = keypair
    challenge = build_security_challenge("wrong_station", {}, priv_pem)

    assert challenge["test_case"] == "wrong_station"
    assert challenge["expected_reason_code"] == "WRONG_STATION"

    res = verify_contact_token(
        token=challenge["token"],
        public_key=pub_pem,
        expected_scope=challenge["expected_scope"],
        server_time=challenge["server_time"],
        simulation_time=challenge["simulation_time"],
    )
    assert res["allowed"] is False
    assert any(r["code"] == "WRONG_STATION" for r in res["reasons"])


def test_tampered_payload_challenge(keypair):
    priv_pem, _ = keypair
    challenge = build_security_challenge("tampered_payload", {}, priv_pem)

    assert challenge["test_case"] == "tampered_payload"
    assert challenge["expected_reason_code"] == "PAYLOAD_INTEGRITY_FAILED"

    with pytest.raises(PayloadIntegrityError):
        decrypt_payload(
            envelope=challenge["envelope"],
            key=challenge["key"],
            associated_data=challenge["associated_data"],
        )


def test_unsupported_challenge_raises(keypair):
    priv_pem, _ = keypair
    with pytest.raises(ValueError) as exc:
        build_security_challenge("fake_exploit", {}, priv_pem)
    assert "Unsupported security test case" in str(exc.value)


def test_sanitize_audit_context():
    sensitive = {
        "user_id": "usr-1",
        "private_key": b"secret_key_bytes",
        "password": "plain_password",
        "plaintext": b"secret_file_bytes",
        "sub_record": {
            "token": "secret_jwt",
            "station_id": "gs-1",
        }
    }
    cleaned = sanitize_audit_context(sensitive)
    assert "private_key" not in cleaned
    assert "password" not in cleaned
    assert "plaintext" not in cleaned
    assert "token" not in cleaned["sub_record"]
    assert cleaned["user_id"] == "usr-1"
    assert cleaned["sub_record"]["station_id"] == "gs-1"


def test_build_evidence_record():
    rec = build_evidence_record(
        check_id="chk-001",
        test_case="expired_authorization",
        passed=True,
        expected_outcome="Rejection expected",
        observed_outcome="Rejected with TOKEN_EXPIRED",
    )
    assert rec["id"] == "chk-001"
    assert rec["status"] == "completed"
    assert rec["passed"] is True
    assert "timestamp" in rec
