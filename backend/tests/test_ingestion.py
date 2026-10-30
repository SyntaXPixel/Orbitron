import pytest
from tests.conftest import TEST_CONTROLLER_TOKEN, TEST_GATEWAY_TOKEN

def test_telemetry_ingestion(client):
    payload = {
        "event_id": "telem-ev-1",
        "scenario_id": "scenario-001",
        "sequence": 1,
        "satellite_id": "sat-a-001",
        "observed_at": "2026-10-31T06:05:00Z",
        "position": {
            "latitude_deg": 79.0,
            "longitude_deg": 16.0,
            "altitude_km": 525.0,
            "observed_at": "2026-10-31T06:05:00Z"
        },
        "operational_status": "communicating",
        "generated_bytes_total": 500_000
    }
    resp = client.post(
        "/api/v1/ingest/telemetry",
        json=payload,
        headers={"Authorization": f"Bearer {TEST_CONTROLLER_TOKEN}"}
    )
    assert resp.status_code == 200

    # Verify idempotency
    resp_dup = client.post(
        "/api/v1/ingest/telemetry",
        json=payload,
        headers={"Authorization": f"Bearer {TEST_CONTROLLER_TOKEN}"}
    )
    assert resp_dup.status_code == 200

    # Verify conflict on payload mismatch
    bad_payload = dict(payload)
    bad_payload["generated_bytes_total"] = 999_999
    resp_conflict = client.post(
        "/api/v1/ingest/telemetry",
        json=bad_payload,
        headers={"Authorization": f"Bearer {TEST_CONTROLLER_TOKEN}"}
    )
    assert resp_conflict.status_code == 409

def test_counter_regression_rejected(client):
    # First set counter to 500,000
    client.post(
        "/api/v1/ingest/telemetry",
        json={
            "event_id": "telem-setup-1",
            "scenario_id": "scenario-001",
            "sequence": 1,
            "satellite_id": "sat-a-001",
            "observed_at": "2026-10-31T06:05:00Z",
            "operational_status": "available",
            "generated_bytes_total": 500_000
        },
        headers={"Authorization": f"Bearer {TEST_CONTROLLER_TOKEN}"}
    )

    # Try sending lower generated_bytes_total
    payload = {
        "event_id": "telem-regress-1",
        "scenario_id": "scenario-001",
        "sequence": 2,
        "satellite_id": "sat-a-001",
        "observed_at": "2026-10-31T06:06:00Z",
        "operational_status": "available",
        "generated_bytes_total": 100  # Less than previous 500,000
    }
    resp = client.post(
        "/api/v1/ingest/telemetry",
        json=payload,
        headers={"Authorization": f"Bearer {TEST_CONTROLLER_TOKEN}"}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "COUNTER_REGRESSION"

def test_heartbeat_ingestion(client):
    payload = {
        "event_id": "hb-ev-1",
        "scenario_id": "scenario-001",
        "sequence": 1,
        "station_id": "gs-a-001",
        "observed_at": "2026-10-31T06:05:00Z",
        "operational_status": "online"
    }
    resp = client.post(
        "/api/v1/ingest/station-heartbeats",
        json=payload,
        headers={"Authorization": f"Bearer {TEST_GATEWAY_TOKEN}"}
    )
    assert resp.status_code == 200
