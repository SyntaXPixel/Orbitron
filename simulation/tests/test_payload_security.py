"""Tests for encrypted sample transfer, gateway relay, owner decryption, and negative security checks."""

import base64
import hashlib
import os
import pytest
from starlette.testclient import TestClient

from simulation.actors.owner import OwnerReceiverActor
from simulation.actors.satellite import VirtualSatelliteActor
from simulation.contracts import PayloadAssociatedData
from simulation.transport.gateway_server import create_gateway_app
from simulation.transport.receiver_server import create_receiver_app


def test_end_to_end_payload_transport(tmp_path):
    owner_key = os.urandom(32)
    sample_plaintext = b"ORBITRON_CONFIDENTIAL_MISSION_TELEMETRY_DATA_XYZ_12345"

    sat = VirtualSatelliteActor(satellite_id="sat-a-001", owner_org_id="org-a")

    # 1. Satellite encrypts sample
    prep = sat.prepare_encrypted_sample(
        sample_plaintext=sample_plaintext,
        owner_payload_key=owner_key,
        scenario_id="scenario-test",
        transfer_id="xfer-001",
        contact_id="contact-001",
        station_id="station-01",
    )

    envelope = prep["envelope"]
    ciphertext_bytes = prep["ciphertext_bytes"]
    expected_plaintext_sha256 = prep["expected_plaintext_sha256"]

    # 2. Setup Receiver
    verified_dir = tmp_path / "verified"
    receiver_actor = OwnerReceiverActor(
        owner_org_id="org-a",
        payload_key=owner_key,
        verified_storage_dir=verified_dir,
    )

    # 3. Owner decrypts and verifies valid sample
    receipt = receiver_actor.receive_and_verify(
        transfer_id="xfer-001",
        envelope=envelope,
        aad=prep["aad"],
        scenario_id="scenario-test",
        event_id="ev-001",
    )

    assert receipt.integrity_status == "verified"
    assert receipt.owner_decryption_status == "success"
    assert receipt.owner_plaintext_sha256 == expected_plaintext_sha256

    # Verify decrypted file was saved
    saved_file = verified_dir / "xfer-001.bin"
    assert saved_file.exists()
    assert saved_file.read_bytes() == sample_plaintext


def test_tampered_ciphertext_fails_authenticated_decryption(tmp_path):
    owner_key = os.urandom(32)
    sample_plaintext = b"SENSITIVE_EARTH_OBSERVATION_PAYLOAD"

    sat = VirtualSatelliteActor(satellite_id="sat-a-001", owner_org_id="org-a")
    prep = sat.prepare_encrypted_sample(
        sample_plaintext=sample_plaintext,
        owner_payload_key=owner_key,
        scenario_id="scenario-test",
        transfer_id="xfer-tamper",
        contact_id="contact-001",
        station_id="station-01",
    )

    envelope = prep["envelope"]
    # Tamper with one byte of ciphertext
    ct = bytearray(base64.b64decode(envelope["ciphertext_b64"]))
    ct[0] ^= 0xFF
    envelope["ciphertext_b64"] = base64.b64encode(ct).decode("ascii")

    verified_dir = tmp_path / "verified"
    receiver_actor = OwnerReceiverActor(
        owner_org_id="org-a",
        payload_key=owner_key,
        verified_storage_dir=verified_dir,
    )

    receipt = receiver_actor.receive_and_verify(
        transfer_id="xfer-tamper",
        envelope=envelope,
        aad=prep["aad"],
        scenario_id="scenario-test",
        event_id="ev-tamper",
    )

    # Decryption must fail and no unverified plaintext should be saved
    assert receipt.owner_decryption_status == "failed"
    assert receipt.integrity_status == "corrupted"
    assert not (verified_dir / "xfer-tamper.bin").exists()


def test_gateway_rejection_of_expired_or_mismatched_token(tmp_path):
    buffer_dir = tmp_path / "gateway_buf"
    app = create_gateway_app(
        station_id="station-01",
        buffer_dir=buffer_dir,
        public_verification_key=b"public_key_mock",
    )
    client = TestClient(app)

    # 1. Missing token -> 401
    resp1 = client.post(
        "/relay/xfer-1",
        content=b"some_ciphertext",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert resp1.status_code == 401

    # 2. Token intended for another station -> 403
    resp2 = client.post(
        "/relay/xfer-2",
        content=b"some_ciphertext",
        headers={
            "Content-Type": "application/octet-stream",
            "X-Contact-Authorization": "valid-token",
            "X-Transfer-Station-ID": "station-99",  # Mismatched station
        },
    )
    assert resp2.status_code == 403

    # 3. Expired token -> 403
    resp3 = client.post(
        "/relay/xfer-3",
        content=b"some_ciphertext",
        headers={
            "Content-Type": "application/octet-stream",
            "X-Contact-Authorization": "expired-token",
            "X-Transfer-Station-ID": "station-01",
        },
    )
    assert resp3.status_code == 403

