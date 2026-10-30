import pytest
from tests.conftest import login_user, TEST_ADMIN_PASSWORD

def test_health_contract(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "orbitron-backend"
    assert data["contract_version"] == "orbitron.v1"
    assert data["status"] in ["ready", "degraded"]

def test_snapshot_contract_and_structure(client):
    login_user(client, "admin@orbitron.local", TEST_ADMIN_PASSWORD)
    resp = client.get("/api/v1/snapshot")
    assert resp.status_code == 200
    snap = resp.json()

    # Verify Meta
    meta = snap["meta"]
    assert meta["contract_version"] == "orbitron.v1"
    assert meta["mode"] == "simulation"
    assert isinstance(meta["state_revision"], int)
    assert isinstance(meta["schedule_version"], int)
    assert meta["server_time"].endswith("Z")
    assert meta["simulation_time"].endswith("Z")
    assert meta["visible_start_at"].endswith("Z")
    assert meta["visible_end_at"].endswith("Z")
    assert "scheduler" in meta["services"]
    assert "security" in meta["services"]

    # Verify required snapshot collections
    required_collections = [
        "organizations", "satellites", "stations", "jobs", "opportunities",
        "contacts", "schedule_changes", "events", "transfers", "security_checks",
        "evaluations", "operations", "audit"
    ]
    for col in required_collections:
        assert col in snap, f"Missing required collection: {col}"
        assert isinstance(snap[col], list), f"Collection {col} should be an array"

    # User, Simulator, Scenario
    assert "user" in snap
    assert snap["user"]["email"] == "admin@orbitron.local"
    assert "simulator" in snap
    assert snap["simulator"]["run_state"] in ["running", "paused", "stopped"]
    assert "scenario" in snap
    if snap["scenario"]:
        assert snap["scenario"]["seed"] == 42
        assert snap["scenario"]["start_at"].endswith("Z")

def test_error_envelope_structure(client):
    # Missing auth on protected endpoint
    resp = client.get("/api/v1/operations/non-existent-op")
    assert resp.status_code == 401
    data = resp.json()
    assert "error" in data
    err = data["error"]
    assert "code" in err
    assert "message" in err
    assert "details" in err
    assert "request_id" in err
    assert isinstance(err["details"], list)

def test_validation_error_envelope(client):
    login_data = login_user(client, "admin@orbitron.local", TEST_ADMIN_PASSWORD)
    csrf = login_data["csrf_token"]
    # Send invalid job body (negative data_bytes)
    resp = client.post(
        "/api/v1/jobs",
        json={
            "satellite_id": "sat-a-001",
            "data_bytes": -50,
            "deadline_at": "2026-10-31T08:00:00Z",
            "priority": "invalid_priority",
            "allow_split": True
        },
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "test-key-invalid-val"
        }
    )
    assert resp.status_code == 422
    data = resp.json()
    assert "error" in data
    err = data["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert len(err["details"]) > 0
    assert "field" in err["details"][0]
    assert "message" in err["details"][0]
