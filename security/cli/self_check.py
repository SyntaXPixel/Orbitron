"""
Self-check CLI for Orbitron Security Module
Exercises cryptographic primitives, token lifecycle, and negative challenges using ephemeral keys.
Prints only non-secret results.
"""

import hashlib
import os
import sys
from datetime import datetime, timezone, timedelta

from security.api import (
    capabilities,
    evaluate_contact,
    issue_contact_token,
    verify_contact_token,
    encrypt_payload,
    decrypt_payload,
    canonical_payload_aad,
    build_security_challenge,
)
from security.tokens.keys import (
    generate_keypair,
    private_key_to_pem,
    public_key_to_pem,
)
from security.contracts import to_iso_z, parse_iso
from security.exceptions import PayloadIntegrityError


def run_self_check():
    print("==================================================")
    print("    Orbitron Security Module - Self Check        ")
    print("==================================================")

    # 1. Capabilities
    caps = capabilities()
    print("[1/5] Capabilities Check:")
    for k, v in caps.items():
        print(f"      {k}: {v}")
    assert caps["contact_authorization"] is True
    assert caps["payload_encryption"] is True

    # 2. Ephemeral Keypair
    print("\n[2/5] Ephemeral Cryptographic Key Initialization:")
    priv_key, pub_key = generate_keypair()
    priv_pem = private_key_to_pem(priv_key)
    pub_pem = public_key_to_pem(pub_key)
    aes_key = os.urandom(32)
    print(f"      Generated Ed25519 issuer keypair: [OK]")
    print(f"      Generated 32-byte AES-256 payload key: [OK]")

    # 3. Policy & Token Lifecycle
    print("\n[3/5] Contact Policy & Token Verification Lifecycle:")
    base_time = datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)
    srv_time_str = to_iso_z(base_time)
    sim_time_str = to_iso_z(base_time + timedelta(minutes=10))

    ctx = {
        "scenario_id": "scen-selfcheck-01",
        "authorization_id": "auth-selfcheck-01",
        "server_time": srv_time_str,
        "simulation_time": sim_time_str,
        "satellite": {
            "id": "sat-demo-01",
            "owner_org_id": "org-alpha",
            "operational_status": "operational",
            "usable": True,
        },
        "station": {
            "id": "gs-demo-01",
            "owner_org_id": "org-alpha",
            "operational_status": "operational",
            "usable": True,
            "sharing_enabled": True,
        },
        "antenna": {
            "id": "ant-demo-01",
            "station_id": "gs-demo-01",
            "supported_bands": ["X", "S"],
            "operational_status": "operational",
            "usable": True,
        },
        "job": {
            "id": "job-demo-01",
            "satellite_id": "sat-demo-01",
            "owner_org_id": "org-alpha",
            "status": "scheduled",
        },
        "contact": {
            "id": "contact-demo-01",
            "job_id": "job-demo-01",
            "satellite_id": "sat-demo-01",
            "station_id": "gs-demo-01",
            "antenna_id": "ant-demo-01",
            "band": "X",
            "start_at": to_iso_z(base_time + timedelta(minutes=5)),
            "end_at": to_iso_z(base_time + timedelta(minutes=25)),
            "status": "confirmed",
            "schedule_version": 1,
        },
    }

    policy_result = evaluate_contact(ctx)
    assert policy_result["allowed"] is True, f"Policy failed: {policy_result}"
    print(f"      Contact policy evaluation: [PASSED]")

    grant = issue_contact_token(ctx, priv_pem)
    assert "token" in grant and "expires_at" in grant
    print(f"      Token issuance (EdDSA / Ed25519): [PASSED]")

    verification = verify_contact_token(
        token=grant["token"],
        public_key=pub_pem,
        expected_scope=grant["scope"],
        server_time=srv_time_str,
        simulation_time=sim_time_str,
    )
    assert verification["allowed"] is True, f"Token verification failed: {verification}"
    print(f"      Token verification against trusted scope: [PASSED]")

    # 4. Authenticated Payload Encryption & Decryption
    print("\n[4/5] AES-256-GCM Payload Protection & Canonical AAD:")
    plaintext = b"Sample satellite telemetry data payload for Orbitron demonstration"
    plaintext_sha256 = hashlib.sha256(plaintext).hexdigest()

    aad_fields = {
        "scenario_id": ctx["scenario_id"],
        "transfer_id": "transfer-demo-001",
        "contact_id": ctx["contact"]["id"],
        "satellite_id": ctx["satellite"]["id"],
        "station_id": ctx["station"]["id"],
        "owner_org_id": ctx["satellite"]["owner_org_id"],
        "expected_plaintext_sha256": plaintext_sha256,
    }
    aad_bytes = canonical_payload_aad(aad_fields)
    assert len(aad_bytes) > 0

    envelope = encrypt_payload(plaintext, aes_key, aad_bytes)
    assert envelope["algorithm"] == "AES-256-GCM"
    assert envelope["version"] == "orbitron.payload.v1"
    print(f"      AES-256-GCM encryption with fresh nonce: [PASSED]")

    recovered = decrypt_payload(envelope, aes_key, aad_bytes)
    assert recovered == plaintext
    print(f"      AES-256-GCM authenticated decryption: [PASSED]")

    # 5. Negative Security Checks
    print("\n[5/5] Negative Security Checks (Enforcement Verification):")
    # Expired token challenge
    exp_challenge = build_security_challenge("expired_authorization", ctx, priv_pem)
    exp_verify = verify_contact_token(
        token=exp_challenge["token"],
        public_key=pub_pem,
        expected_scope=exp_challenge["expected_scope"],
        server_time=exp_challenge["server_time"],
        simulation_time=exp_challenge["simulation_time"],
    )
    assert exp_verify["allowed"] is False
    assert any(r["code"] == "TOKEN_EXPIRED" for r in exp_verify["reasons"])
    print(f"      Negative check 'expired_authorization': correctly rejected [PASSED]")

    # Wrong station challenge
    ws_challenge = build_security_challenge("wrong_station", ctx, priv_pem)
    ws_verify = verify_contact_token(
        token=ws_challenge["token"],
        public_key=pub_pem,
        expected_scope=ws_challenge["expected_scope"],
        server_time=ws_challenge["server_time"],
        simulation_time=ws_challenge["simulation_time"],
    )
    assert ws_verify["allowed"] is False
    assert any(r["code"] == "WRONG_STATION" for r in ws_verify["reasons"])
    print(f"      Negative check 'wrong_station': correctly rejected [PASSED]")

    # Tampered payload challenge
    tamper_challenge = build_security_challenge("tampered_payload", ctx, priv_pem)
    tamper_failed = False
    try:
        decrypt_payload(
            envelope=tamper_challenge["envelope"],
            key=tamper_challenge["key"],
            associated_data=tamper_challenge["associated_data"],
        )
    except PayloadIntegrityError:
        tamper_failed = True
    assert tamper_failed is True
    print(f"      Negative check 'tampered_payload': correctly rejected [PASSED]")

    print("\n==================================================")
    print("  ALL CRYPTOGRAPHIC CONTROLS VERIFIED SUCCESSFULLY")
    print("  (Note: Backend runtime integration is tested separately)")
    print("==================================================")


if __name__ == "__main__":
    try:
        run_self_check()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n[SELF-CHECK FAILED]: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR]: {e}", file=sys.stderr)
        sys.exit(1)
