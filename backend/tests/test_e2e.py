import pytest
from tests.conftest import (
    login_user, TEST_ADMIN_PASSWORD, TEST_ALPHA_PASSWORD,
    TEST_GATEWAY_TOKEN, TEST_OWNER_TOKEN, TEST_CONTROLLER_TOKEN
)
from app.adapters.scheduler import set_scheduler_override
from app.workers.operations_worker import worker

def test_full_operational_e2e_flow(client):
    # 1. Login as operator
    login_data = login_user(client, "operator@alpha.local", TEST_ALPHA_PASSWORD)
    csrf = login_data["csrf_token"]

    # 2. Read satellite records via snapshot
    snap_resp = client.get("/api/v1/snapshot")
    assert snap_resp.status_code == 200
    snap = snap_resp.json()
    satellites = snap["satellites"]
    assert len(satellites) >= 1
    target_sat = satellites[0]
    sat_id = target_sat["id"]

    # 3. Create Job
    job_resp = client.post(
        "/api/v1/jobs",
        json={
            "satellite_id": sat_id,
            "data_bytes": 400_000_000,
            "deadline_at": "2026-10-31T08:30:00Z",
            "priority": "high",
            "allow_split": True
        },
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "e2e-job-1"
        }
    )
    assert job_resp.status_code == 201
    job = job_resp.json()
    job_id = job["id"]

    # 4. Generate Bookings using Scheduler
    class E2EScheduler:
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
                        "satellite_id": sat_id,
                        "station_id": "gs-a-001",
                        "antenna_id": "ant-a-001",
                        "opportunity_id": "opp-001",
                        "band": "X",
                        "setup_start_at": "2026-10-31T06:15:00Z",
                        "start_at": "2026-10-31T06:16:00Z",
                        "end_at": "2026-10-31T06:26:00Z",
                        "expected_rate_bps": 150_000_000,
                        "allocated_bytes": 400_000_000,
                        "reasons": []
                    }
                ],
                "unassigned_jobs": []
            }
        @staticmethod
        def propagate_satellites(orbit_definitions, at):
            return []

    set_scheduler_override(E2EScheduler)

    sched_run = client.post(
        "/api/v1/schedule/runs",
        json={"algorithm": "optimized", "expected_schedule_version": snap["meta"]["schedule_version"]},
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "e2e-sched-1"
        }
    )
    assert sched_run.status_code == 202
    worker.process_next_operation()

    # Verify contact created
    snap2 = client.get("/api/v1/snapshot").json()
    assert len(snap2["contacts"]) == 1
    contact = snap2["contacts"][0]
    contact_id = contact["id"]
    assert contact["status"] == "tentative"

    # 5. Station Gateway confirms contact
    # Find service work for gateway
    work_resp = client.get("/api/v1/service/work", headers={"Authorization": f"Bearer {TEST_GATEWAY_TOKEN}"})
    assert work_resp.status_code == 200
    work = work_resp.json()
    assert len(work["pending_commands"]) >= 1
    confirm_cmd = next(c for c in work["pending_commands"] if c["command_type"] == "confirm_contact")

    ack_resp = client.post(
        f"/api/v1/service/commands/{confirm_cmd['id']}/ack",
        json={
            "event_id": "e2e-ack-1",
            "scenario_id": "scenario-001",
            "status": "completed",
            "result": {"confirmed": True},
            "reasons": []
        },
        headers={"Authorization": f"Bearer {TEST_GATEWAY_TOKEN}"}
    )
    assert ack_resp.status_code == 200

    # 6. Authorize contact and accept simulated progress
    progress_resp = client.post(
        "/api/v1/ingest/contact-progress",
        json={
            "event_id": "e2e-prog-1",
            "scenario_id": "scenario-001",
            "sequence": 1,
            "contact_id": contact_id,
            "interval_start_at": "2026-10-31T06:16:00Z",
            "interval_end_at": "2026-10-31T06:20:00Z",
            "cumulative_transferred_bytes": 200_000_000,
            "final": False
        },
        headers={"Authorization": f"Bearer {TEST_GATEWAY_TOKEN}"}
    )
    assert progress_resp.status_code == 200

    # Verify job remaining bytes decreased in snapshot
    snap3 = client.get("/api/v1/snapshot").json()
    updated_job = next(j for j in snap3["jobs"] if j["id"] == job_id)
    assert updated_job["delivered_bytes"] == 200_000_000
    assert updated_job["remaining_bytes"] == 200_000_000

    # 7. Apply disruption (Rain) as admin
    admin_login = login_user(client, "admin@orbitron.local", TEST_ADMIN_PASSWORD)
    admin_csrf = admin_login["csrf_token"]

    event_resp = client.post(
        "/api/v1/events",
        json={
            "type": "rain",
            "station_id": "gs-a-001",
            "capacity_factor": 0.5,
            "expected_schedule_version": snap3["meta"]["schedule_version"]
        },
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": admin_csrf,
            "Idempotency-Key": "e2e-event-1"
        }
    )
    assert event_resp.status_code == 202

    # Process disruption event
    worker.process_next_operation()
    # Process enqueued recovery replan
    worker.process_next_operation()

    # 8. Execute protected sample transfer
    transfer_resp = client.post(
        "/api/v1/transfers",
        json={"contact_id": contact_id},
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": admin_csrf,
            "Idempotency-Key": "e2e-transfer-1"
        }
    )
    assert transfer_resp.status_code == 202
    trans_op = transfer_resp.json()
    transfer_id = trans_op["resource_id"]

    # Gateway reports forwarding
    client.post(
        "/api/v1/ingest/transfer-progress",
        json={
            "event_id": "e2e-tp-1",
            "scenario_id": "scenario-001",
            "transfer_id": transfer_id,
            "forwarded_bytes": 52,
            "ciphertext_sha256": "sample_cipher_sha"
        },
        headers={"Authorization": f"Bearer {TEST_GATEWAY_TOKEN}"}
    )

    # 9. Verify owner receipt
    receipt_resp = client.post(
        "/api/v1/ingest/delivery-receipts",
        json={
            "event_id": "e2e-dr-1",
            "scenario_id": "scenario-001",
            "transfer_id": transfer_id,
            "owner_plaintext_sha256": "valid_hash",
            "integrity_status": "verified",
            "owner_decryption_status": "succeeded"
        },
        headers={"Authorization": f"Bearer {TEST_OWNER_TOKEN}"}
    )
    assert receipt_resp.status_code == 200

    worker.process_next_operation()

    # 10. Run comparison evaluation
    eval_resp = client.post(
        "/api/v1/evaluations",
        json={"scenario_id": "scenario-001"},
        headers={
            "Origin": "http://localhost:5173",
            "X-CSRF-Token": admin_csrf,
            "Idempotency-Key": "e2e-eval-1"
        }
    )
    assert eval_resp.status_code == 202
    worker.process_next_operation()

    # Final snapshot inspection
    final_snap = client.get("/api/v1/snapshot").json()
    assert len(final_snap["evaluations"]) >= 1
    assert final_snap["evaluations"][0]["status"] == "completed"
    assert final_snap["transfers"][0]["status"] == "delivered"
    set_scheduler_override(None)
