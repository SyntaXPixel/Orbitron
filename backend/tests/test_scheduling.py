import pytest
from tests.conftest import login_user, TEST_ADMIN_PASSWORD, TEST_ALPHA_PASSWORD
from app.adapters.scheduler import set_scheduler_override
from app.workers.operations_worker import worker

def test_scheduler_unavailable_returns_503(client):
    set_scheduler_override(None)  # No scheduler available
    login_data = login_user(client, "admin@orbitron.local", TEST_ADMIN_PASSWORD)
    csrf = login_data["csrf_token"]

    resp = client.post(
        "/api/v1/schedule/runs",
        json={"algorithm": "optimized", "expected_schedule_version": 0},
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-sched-unavailable"
        }
    )
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "SCHEDULER_UNAVAILABLE"

def test_stale_schedule_version_returns_409(client):
    class FakeScheduler:
        @staticmethod
        def predict_opportunities(catalog, horizon):
            return []
        @staticmethod
        def solve_schedule(problem, algorithm, time_limit_seconds=5):
            return {"status": "feasible", "assignments": [], "unassigned_jobs": []}
        @staticmethod
        def propagate_satellites(orbit_definitions, at):
            return []

    set_scheduler_override(FakeScheduler)
    login_data = login_user(client, "admin@orbitron.local", TEST_ADMIN_PASSWORD)
    csrf = login_data["csrf_token"]

    resp = client.post(
        "/api/v1/schedule/runs",
        json={"algorithm": "optimized", "expected_schedule_version": 999},  # Wrong version
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-sched-stale"
        }
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "STALE_SCHEDULE"
    set_scheduler_override(None)

def test_valid_scheduling_and_independent_validation(client):
    # 1. First create a job
    login_data = login_user(client, "operator@alpha.local", TEST_ALPHA_PASSWORD)
    csrf = login_data["csrf_token"]

    job_resp = client.post(
        "/api/v1/jobs",
        json={
            "satellite_id": "sat-a-001",
            "data_bytes": 500_000_000,
            "deadline_at": "2026-10-31T08:00:00Z",
            "priority": "routine",
            "allow_split": True
        },
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-sched-job-1"
        }
    )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    # 2. Setup Mock Scheduler that returns a valid assignment
    class ValidScheduler:
        @staticmethod
        def predict_opportunities(catalog, horizon):
            return []
        @staticmethod
        def solve_schedule(problem, algorithm, time_limit_seconds=5):
            return {
                "status": "feasible",
                "assignments": [
                    {
                        "job_id": job_id,
                        "satellite_id": "sat-a-001",
                        "station_id": "gs-a-001",
                        "antenna_id": "ant-a-001",
                        "opportunity_id": "opp-001",
                        "band": "X",
                        "setup_start_at": "2026-10-31T06:15:00Z",
                        "start_at": "2026-10-31T06:16:00Z",
                        "end_at": "2026-10-31T06:26:00Z",
                        "expected_rate_bps": 150_000_000,
                        "allocated_bytes": 500_000_000,
                        "reasons": []
                    }
                ],
                "unassigned_jobs": []
            }
        @staticmethod
        def propagate_satellites(orbit_definitions, at):
            return []

    set_scheduler_override(ValidScheduler)

    # 3. Request schedule run
    sched_resp = client.post(
        "/api/v1/schedule/runs",
        json={"algorithm": "optimized", "expected_schedule_version": 0},
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "key-sched-run-1"
        }
    )
    assert sched_resp.status_code == 202
    op = sched_resp.json()
    assert op["status"] == "queued"

    # Process operation via worker
    worker.process_next_operation()

    # 4. Check snapshot for committed contact and updated schedule version
    snap_resp = client.get("/api/v1/snapshot")
    assert snap_resp.status_code == 200
    snap = snap_resp.json()
    assert snap["meta"]["schedule_version"] == 1
    assert len(snap["contacts"]) == 1
    c = snap["contacts"][0]
    assert c["job_id"] == job_id
    assert c["status"] == "tentative"
    assert c["allocated_bytes"] == 500_000_000

    # Job is now scheduled
    scheduled_job = next(j for j in snap["jobs"] if j["id"] == job_id)
    assert scheduled_job["status"] == "scheduled"
    set_scheduler_override(None)
