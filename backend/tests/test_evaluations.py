import pytest
from tests.conftest import login_user, TEST_ADMIN_PASSWORD
from app.workers.operations_worker import worker

def test_evaluation_execution(client):
    login_data = login_user(client, "admin@orbitron.local", TEST_ADMIN_PASSWORD)
    csrf = login_data["csrf_token"]

    resp = client.post(
        "/api/v1/evaluations",
        json={"scenario_id": "scenario-001"},
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-eval-test"
        }
    )
    assert resp.status_code == 202

    # Process evaluation via worker
    worker.process_next_operation()

    # Read snapshot
    snap = client.get("/api/v1/snapshot").json()
    assert len(snap["evaluations"]) >= 1
    ev = snap["evaluations"][0]
    assert ev["status"] == "completed"
    assert ev["fifo"] is not None
    assert ev["optimized"] is not None

    fifo = ev["fifo"]
    opt = ev["optimized"]

    metrics_fields = [
        "requested_bytes", "delivered_before_deadline_bytes", "total_jobs",
        "on_time_jobs", "urgent_jobs", "urgent_on_time_jobs",
        "resource_conflicts", "scheduling_duration_ms", "bookings_changed"
    ]
    for mf in metrics_fields:
        assert mf in fifo
        assert mf in opt
        assert isinstance(fifo[mf], int)
        assert isinstance(opt[mf], int)
