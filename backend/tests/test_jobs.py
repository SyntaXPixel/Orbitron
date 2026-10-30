import pytest
from tests.conftest import login_user, TEST_ADMIN_PASSWORD, TEST_ALPHA_PASSWORD, TEST_BETA_PASSWORD

def test_create_job_success(client):
    login_data = login_user(client, "operator@alpha.local", TEST_ALPHA_PASSWORD)
    csrf = login_data["csrf_token"]

    resp = client.post(
        "/api/v1/jobs",
        json={
            "satellite_id": "sat-a-001",
            "data_bytes": 1_000_000_000,
            "deadline_at": "2026-10-31T08:30:00Z",
            "priority": "high",
            "allow_split": True
        },
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-job-create-1"
        }
    )
    assert resp.status_code == 201
    job = resp.json()
    assert job["satellite_id"] == "sat-a-001"
    assert job["requested_bytes"] == 1_000_000_000
    assert job["delivered_bytes"] == 0
    assert job["remaining_bytes"] == 1_000_000_000
    assert job["status"] == "pending"
    assert job["priority"] == "high"
    assert job["created_at"].endswith("Z")

def test_operator_cannot_submit_other_org_satellite(client):
    # Beta operator tries to create job on Alpha satellite
    login_data = login_user(client, "operator@beta.local", TEST_BETA_PASSWORD)
    csrf = login_data["csrf_token"]

    resp = client.post(
        "/api/v1/jobs",
        json={
            "satellite_id": "sat-a-001",
            "data_bytes": 500_000_000,
            "deadline_at": "2026-10-31T08:30:00Z",
            "priority": "routine",
            "allow_split": True
        },
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-job-forbidden"
        }
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

def test_job_deadline_in_past_rejected(client):
    login_data = login_user(client, "operator@alpha.local", TEST_ALPHA_PASSWORD)
    csrf = login_data["csrf_token"]

    resp = client.post(
        "/api/v1/jobs",
        json={
            "satellite_id": "sat-a-001",
            "data_bytes": 500_000_000,
            "deadline_at": "2026-10-31T05:00:00Z",  # Before simulation_time (06:00:00Z)
            "priority": "routine",
            "allow_split": True
        },
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-job-past-deadline"
        }
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "DEADLINE_PAST"

def test_job_insufficient_onboard_data(client):
    login_data = login_user(client, "operator@alpha.local", TEST_ALPHA_PASSWORD)
    csrf = login_data["csrf_token"]

    resp = client.post(
        "/api/v1/jobs",
        json={
            "satellite_id": "sat-a-001",
            "data_bytes": 50_000_000_000,  # Exceeds 10 GB onboard
            "deadline_at": "2026-10-31T09:00:00Z",
            "priority": "routine",
            "allow_split": True
        },
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-job-too-large"
        }
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INSUFFICIENT_ONBOARD_DATA"

def test_job_idempotency_and_conflict(client):
    login_data = login_user(client, "operator@alpha.local", TEST_ALPHA_PASSWORD)
    csrf = login_data["csrf_token"]

    payload = {
        "satellite_id": "sat-a-001",
        "data_bytes": 200_000_000,
        "deadline_at": "2026-10-31T08:00:00Z",
        "priority": "routine",
        "allow_split": True
    }

    # First request
    resp1 = client.post(
        "/api/v1/jobs",
        json=payload,
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-idempotency-test"
        }
    )
    assert resp1.status_code == 201
    job1 = resp1.json()

    # Identical replay returns same result
    resp2 = client.post(
        "/api/v1/jobs",
        json=payload,
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-idempotency-test"
        }
    )
    assert resp2.status_code == 201
    assert resp2.json()["id"] == job1["id"]

    # Same key with different payload returns 409
    different_payload = dict(payload)
    different_payload["data_bytes"] = 300_000_000
    resp3 = client.post(
        "/api/v1/jobs",
        json=different_payload,
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-idempotency-test"
        }
    )
    assert resp3.status_code == 409
    assert resp3.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
