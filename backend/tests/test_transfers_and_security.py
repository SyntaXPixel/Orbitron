import pytest
from tests.conftest import login_user, TEST_ADMIN_PASSWORD, TEST_ALPHA_PASSWORD, TEST_GATEWAY_TOKEN, TEST_OWNER_TOKEN
from app.workers.operations_worker import worker
from app.db.session import SessionLocal
from app.db.models import Contact, Job, ApplicationState
from datetime import datetime, timezone, timedelta
from sqlalchemy import func

def test_transfers_and_owner_evidence(client, TestingSessionLocal):
    db = TestingSessionLocal()
    import secrets
    job_id = f"job-trans-{secrets.token_hex(4)}"
    contact_id = f"contact-trans-{secrets.token_hex(4)}"
    base_start = datetime(2026, 10, 31, 6, 0, 0, tzinfo=timezone.utc)
    max_seq = db.query(func.coalesce(func.max(Job.arrival_sequence), 0)).scalar() or 0
    job = Job(
        id=job_id,
        satellite_id="sat-a-001",
        owner_org_id="org-alpha",
        requested_bytes=1000,
        delivered_bytes=0,
        remaining_bytes=1000,
        priority="routine",
        deadline_at=base_start + timedelta(hours=2),
        allow_split=True,
        status="scheduled",
        reasons_json=[],
        arrival_sequence=max_seq + 1,
        created_at=base_start,
        updated_at=base_start
    )
    db.add(job)
    contact = Contact(
        id=contact_id,
        job_id=job_id,
        satellite_id="sat-a-001",
        station_id="gs-a-001",
        antenna_id="ant-a-001",
        opportunity_id="opp-001",
        band="X",
        window_start_at=base_start + timedelta(minutes=15),
        window_end_at=base_start + timedelta(minutes=30),
        setup_start_at=base_start + timedelta(minutes=15),
        start_at=base_start + timedelta(minutes=16),
        end_at=base_start + timedelta(minutes=26),
        expected_rate_bps=150_000_000,
        allocated_bytes=1000,
        transferred_bytes=0,
        status="confirmed",
        authorization_status="allowed",
        schedule_version=1,
        reasons_json=[]
    )
    db.add(contact)
    db.commit()
    db.close()

    login_data = login_user(client, "operator@alpha.local", TEST_ALPHA_PASSWORD)
    csrf = login_data["csrf_token"]

    resp = client.post(
        "/api/v1/transfers",
        json={"contact_id": contact_id},
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"key-transfer-{secrets.token_hex(4)}"
        }
    )
    assert resp.status_code == 202
    op = resp.json()
    transfer_id = op["resource_id"]

    # Gateway reports forwarding
    resp_fwd = client.post(
        "/api/v1/ingest/transfer-progress",
        json={
            "event_id": "tp-ev-1",
            "scenario_id": "scenario-001",
            "transfer_id": transfer_id,
            "forwarded_bytes": 50,
            "ciphertext_sha256": "abcdef123456"
        },
        headers={"Authorization": f"Bearer {TEST_GATEWAY_TOKEN}"}
    )
    assert resp_fwd.status_code == 200

    # Gateway cannot report owner delivery receipt (Forbidden)
    resp_bad_receipt = client.post(
        "/api/v1/ingest/delivery-receipts",
        json={
            "event_id": "dr-ev-bad",
            "scenario_id": "scenario-001",
            "transfer_id": transfer_id,
            "owner_plaintext_sha256": "sample_hash",
            "integrity_status": "verified",
            "owner_decryption_status": "succeeded"
        },
        headers={"Authorization": f"Bearer {TEST_GATEWAY_TOKEN}"}
    )
    assert resp_bad_receipt.status_code == 403

    # Owner receiver submits receipt
    resp_receipt = client.post(
        "/api/v1/ingest/delivery-receipts",
        json={
            "event_id": "dr-ev-1",
            "scenario_id": "scenario-001",
            "transfer_id": transfer_id,
            "owner_plaintext_sha256": "valid_hash",
            "integrity_status": "verified",
            "owner_decryption_status": "succeeded"
        },
        headers={"Authorization": f"Bearer {TEST_OWNER_TOKEN}"}
    )
    assert resp_receipt.status_code == 200

    # Execute transfer operation
    worker.process_next_operation()

    # Check snapshot
    snap = client.get("/api/v1/snapshot").json()
    t = next(tr for tr in snap["transfers"] if tr["id"] == transfer_id)
    assert t["status"] == "delivered"
    assert t["integrity_status"] == "verified"
    assert t["owner_decryption_status"] == "succeeded"

def test_security_checks(client):
    login_data = login_user(client, "admin@orbitron.local", TEST_ADMIN_PASSWORD)
    csrf = login_data["csrf_token"]

    test_cases = ["expired_authorization", "wrong_station", "tampered_payload"]
    for tc in test_cases:
        resp = client.post(
            "/api/v1/security/checks",
            json={"test_case": tc},
            headers={
                "Origin": "http://localhost:5173",
                "X-CSRF-Token": csrf,
                "Idempotency-Key": f"key-sec-check-{tc}"
            }
        )
        assert resp.status_code == 202
        worker.process_next_operation()

    snap = client.get("/api/v1/snapshot").json()
    assert len(snap["security_checks"]) >= 3
    for ck in snap["security_checks"]:
        assert ck["status"] == "completed"
        assert ck["passed"] is True
