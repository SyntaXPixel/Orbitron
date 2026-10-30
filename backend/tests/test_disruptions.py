import pytest
from tests.conftest import login_user, TEST_ADMIN_PASSWORD, TEST_ALPHA_PASSWORD
from app.workers.operations_worker import worker

def test_disruption_permission(client):
    login_data = login_user(client, "operator@alpha.local", TEST_ALPHA_PASSWORD)
    csrf = login_data["csrf_token"]

    resp = client.post(
        "/api/v1/events",
        json={
            "type": "station_outage",
            "station_id": "gs-a-001",
            "capacity_factor": None,
            "expected_schedule_version": 0
        },
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-event-forbidden"
        }
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

def test_rain_event_validation_and_application(client):
    login_data = login_user(client, "admin@orbitron.local", TEST_ADMIN_PASSWORD)
    csrf = login_data["csrf_token"]

    # Invalid capacity factor for rain (> 1.0)
    resp_bad = client.post(
        "/api/v1/events",
        json={
            "type": "rain",
            "station_id": "gs-a-001",
            "capacity_factor": 1.5,
            "expected_schedule_version": 0
        },
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-event-bad-rain"
        }
    )
    assert resp_bad.status_code == 422

    # Valid rain event
    resp = client.post(
        "/api/v1/events",
        json={
            "type": "rain",
            "station_id": "gs-a-001",
            "capacity_factor": 0.4,
            "expected_schedule_version": 0
        },
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-event-rain-valid"
        }
    )
    assert resp.status_code == 202

    worker.process_next_operation()

    # Verify station weather capacity updated in snapshot
    snap_resp = client.get("/api/v1/snapshot")
    assert snap_resp.status_code == 200
    snap = snap_resp.json()
    st = next(s for s in snap["stations"] if s["id"] == "gs-a-001")
    assert st["weather_capacity_factor"] == 0.4
    assert len(snap["events"]) == 1
    assert snap["events"][0]["type"] == "rain"
    assert snap["events"][0]["status"] == "applied"

def test_station_outage_and_recovery(client):
    login_data = login_user(client, "admin@orbitron.local", TEST_ADMIN_PASSWORD)
    csrf = login_data["csrf_token"]

    # Outage
    resp_out = client.post(
        "/api/v1/events",
        json={
            "type": "station_outage",
            "station_id": "gs-a-001",
            "capacity_factor": None,
            "expected_schedule_version": 0
        },
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-event-outage"
        }
    )
    assert resp_out.status_code == 202
    while worker.process_next_operation():
        pass

    snap1 = client.get("/api/v1/snapshot").json()
    st1 = next(s for s in snap1["stations"] if s["id"] == "gs-a-001")
    assert st1["operational_status"] == "offline"

    # Recovery
    resp_rec = client.post(
        "/api/v1/events",
        json={
            "type": "station_recovery",
            "station_id": "gs-a-001",
            "capacity_factor": None,
            "expected_schedule_version": snap1["meta"]["schedule_version"]
        },
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-event-recovery"
        }
    )
    assert resp_rec.status_code == 202
    while worker.process_next_operation():
        pass

    snap2 = client.get("/api/v1/snapshot").json()
    st2 = next(s for s in snap2["stations"] if s["id"] == "gs-a-001")
    assert st2["operational_status"] == "online"
