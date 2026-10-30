"""
Tests for security.api Public Interfaces and Contract Compliance
"""

import os
from datetime import datetime, timezone, timedelta
from security import api
from security.contracts import to_iso_z
from security.tokens.keys import generate_keypair, private_key_to_pem, public_key_to_pem


def test_capabilities_contract():
    caps = api.capabilities()
    assert caps["contract_version"] == "orbitron.v1"
    assert caps["contact_authorization"] is True
    assert caps["token_verification"] is True
    assert caps["payload_encryption"] is True
    assert caps["security_checks"] is True


def test_api_full_contact_and_payload_flow():
    priv_key, pub_key = generate_keypair()
    priv_pem = private_key_to_pem(priv_key)
    pub_pem = public_key_to_pem(pub_key)
    aes_key = os.urandom(32)

    base_time = datetime(2026, 10, 31, 15, 0, 0, tzinfo=timezone.utc)
    srv_time_str = to_iso_z(base_time)
    sim_time_str = to_iso_z(base_time + timedelta(minutes=10))

    ctx = {
        "scenario_id": "scen-api-01",
        "authorization_id": "auth-api-01",
        "server_time": srv_time_str,
        "simulation_time": sim_time_str,
        "satellite": {
            "id": "sat-api-01",
            "owner_org_id": "org-alpha",
            "operational_status": "operational",
            "usable": True,
        },
        "station": {
            "id": "gs-api-01",
            "owner_org_id": "org-alpha",
            "operational_status": "operational",
            "usable": True,
            "sharing_enabled": True,
        },
        "antenna": {
            "id": "ant-api-01",
            "station_id": "gs-api-01",
            "supported_bands": ["X"],
            "operational_status": "operational",
            "usable": True,
        },
        "job": {
            "id": "job-api-01",
            "satellite_id": "sat-api-01",
            "owner_org_id": "org-alpha",
            "status": "scheduled",
        },
        "contact": {
            "id": "contact-api-01",
            "job_id": "job-api-01",
            "satellite_id": "sat-api-01",
            "station_id": "gs-api-01",
            "antenna_id": "ant-api-01",
            "band": "X",
            "start_at": to_iso_z(base_time + timedelta(minutes=5)),
            "end_at": to_iso_z(base_time + timedelta(minutes=25)),
            "status": "confirmed",
            "schedule_version": 1,
        },
    }

    # 1. evaluate_contact
    pol = api.evaluate_contact(ctx)
    assert pol["allowed"] is True

    # 2. issue_contact_token
    grant = api.issue_contact_token(ctx, priv_pem)
    assert "token" in grant

    # 3. verify_contact_token
    res = api.verify_contact_token(
        token=grant["token"],
        public_key=pub_pem,
        expected_scope=grant["scope"],
        server_time=srv_time_str,
        simulation_time=sim_time_str,
    )
    assert res["allowed"] is True

    # 4. canonical_payload_aad
    aad = api.canonical_payload_aad({
        "scenario_id": ctx["scenario_id"],
        "transfer_id": "transfer-api-01",
        "contact_id": ctx["contact"]["id"],
        "satellite_id": ctx["satellite"]["id"],
        "station_id": ctx["station"]["id"],
        "owner_org_id": ctx["job"]["owner_org_id"],
        "expected_plaintext_sha256": "abcdef123456",
    })

    # 5. encrypt_payload & decrypt_payload
    msg = b"Antigravity Orbitron end-to-end integration payload test"
    env = api.encrypt_payload(msg, aes_key, aad)
    dec = api.decrypt_payload(env, aes_key, aad)
    assert dec == msg

    # 6. build_security_challenge
    chal = api.build_security_challenge("wrong_station", ctx, priv_pem)
    assert chal["test_case"] == "wrong_station"
