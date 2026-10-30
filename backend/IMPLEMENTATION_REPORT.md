# Orbitron Backend Implementation Report

**Module:** Backend  
**Plan Version:** 1.0  
**Public Contract Version:** `orbitron.v1`  
**Execution Date:** 2026-10-31  

---

## 1. Implemented Endpoints

### 1.1 Frontend-Facing Endpoints (`/api/v1`)
- `GET /api/v1/health`: Unauthenticated service health check (`ready` | `degraded`).
- `POST /api/v1/auth/login`: Session establishment with Argon2 password verification and CSRF token generation.
- `GET /api/v1/auth/session`: Active session retrieval.
- `POST /api/v1/auth/logout`: Session revocation and cookie clearing.
- `GET /api/v1/snapshot`: Consistent read transaction assembling all 13 collections, simulator state, user details, and metadata with bounded horizon filtering.
- `POST /api/v1/jobs`: Downlink job submission with satellite ownership check, onboard byte reservation, and deadline validation against simulation time.
- `POST /api/v1/schedule/runs`: Scheduling execution request with `expected_schedule_version` validation.
- `POST /api/v1/events`: Disruption injection (`rain`, `station_outage`, `station_recovery`) with capacity factor validation.
- `POST /api/v1/simulation/actions`: Network admin simulation controls (`pause`, `resume`, `step`, `reset`).
- `POST /api/v1/transfers`: End-to-end secure transfer initiation with partner station authorization.
- `POST /api/v1/security/checks`: Controlled security test execution (`expired_authorization`, `wrong_station`, `tampered_payload`).
- `POST /api/v1/evaluations`: FIFO vs. Optimized performance benchmark over frozen scenario traces without altering live schedule.
- `GET /api/v1/operations/{operation_id}`: Persistent asynchronous operation status lookup.

### 1.2 Service Ingestion Endpoints (`/api/v1/ingest/...` & `/api/v1/service/...`)
- `POST /api/v1/ingest/catalog`: Controller-only catalogue registration for satellites, stations, and orbits.
- `POST /api/v1/ingest/telemetry`: Satellite telemetry updates with monotonic counter enforcement and freshness tracking.
- `POST /api/v1/ingest/station-heartbeats`: Station gateway connectivity tracking using server time.
- `POST /api/v1/ingest/contact-progress`: Contact transfer progress deduplication, cumulative accounting, and job data deduction.
- `POST /api/v1/ingest/ticks`: Controller-only atomic clock advancement (≤ 60s) with bulk observation processing.
- `GET /api/v1/service/work`: Pending service command and assignment retrieval for scoped principals.
- `POST /api/v1/service/commands/{command_id}/ack`: Station gateway confirmation of contact assignments.
- `POST /api/v1/ingest/transfer-progress`: Gateway reporting of forwarded bytes and ciphertext SHA-256.
- `POST /api/v1/ingest/delivery-receipts`: Owner receiver verification of plaintext SHA-256 and decryption status.

---

## 2. Public Contract Compatibility

- Implemented exact Pydantic v2 schemas for all 23 models specified in Section 6 of `frontend/plan.md`:
  `Reason`, `Organization`, `User`, `Session`, `Position`, `Satellite`, `Antenna`, `Station`, `Job`, `Opportunity`, `Contact`, `ScheduleChange`, `DisruptionEvent`, `Transfer`, `SecurityCheck`, `SchedulerMetrics`, `Evaluation`, `Operation`, `AuditEntry`, `SimulatorState`, `Scenario`, `Snapshot`, `ApiError`.
- All timestamps serialized as ISO 8601 UTC strings ending with `Z`.
- Standardized error envelope implemented across all error handlers (HTTP exceptions, Pydantic validation errors, and unexpected exceptions):
  ```json
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "The request could not be accepted.",
      "details": [],
      "request_id": "req-..."
    }
  }
  ```
- Two-clock model enforced: server time for sessions/heartbeats/operations, simulation time for satellite positions, deadlines, passes, and contact progress.

---

## 3. Database Schema and Migrations

- Implemented 28 relational tables in `app/db/models.py`:
  `organizations`, `users`, `sessions`, `service_principals`, `service_credentials`, `satellites`, `satellite_orbits`, `satellite_observations`, `stations`, `antennas`, `station_partner_permissions`, `jobs`, `opportunities`, `contacts`, `contact_authorizations`, `contact_progress`, `schedule_changes`, `disruption_events`, `transfers`, `security_checks`, `operations`, `service_commands`, `evaluations`, `audit_entries`, `idempotency_records`, `ingestion_events`, `scenario_runs`, `application_state`.
- SQLite configuration:
  - Enabled WAL mode (`PRAGMA journal_mode=WAL`).
  - Enabled foreign key enforcement (`PRAGMA foreign_keys=ON`).
  - Set busy timeout to 5000ms.
- Migrations managed via Alembic:
  - Created initial migration revision `523938143dff_initial_schema.py`.
  - Upgrades executed cleanly via `alembic upgrade head`.

---

## 4. Subsystem Interfaces and Adapters

### 4.1 Scheduler Adapter (`app/adapters/scheduler.py`)
- Interfaces with `scheduler.api` functions: `predict_opportunities`, `solve_schedule`, `propagate_satellites`.
- Implements independent backend validation of solver output:
  - ID verification, band compatibility, window boundaries, antenna setup intervals, antenna overlap detection, satellite concurrency limits, station operational status, partner sharing permissions, rate capacity limits, deadline constraints, and active contact protection.
- When `scheduler.api` is unavailable, reports `services.scheduler = "unavailable"`, sets system health to `degraded`, and returns `503 SCHEDULER_UNAVAILABLE` on scheduling requests.

### 4.2 Security Adapter (`app/adapters/security.py`)
- Interfaces with `security.api`: `capabilities()`, `evaluate_contact(context)`.
- If unavailable, exposes `services.security = "unavailable"`, keeping protected execution disabled while maintaining standard session management.

### 4.3 Simulation Integration
- Simulation participates strictly via authenticated HTTP endpoints.
- Ingestion deduplication enforced by `(scenario_id, principal_id, event_id)` unique index.
- Scenario resets increment scenario generation and fence off obsolete event IDs.

---

## 5. Verification and Automated Test Results

Automated test suite located in `backend/tests/` executed against isolated test databases.

```text
============================= test session starts ==============================
collected 29 items

tests/test_auth.py::test_login_success PASSED                            [  3%]
tests/test_auth.py::test_login_invalid_password PASSED                   [  6%]
tests/test_auth.py::test_session_retrieval PASSED                        [ 10%]
tests/test_auth.py::test_logout PASSED                                   [ 13%]
tests/test_auth.py::test_csrf_required_for_mutations PASSED              [ 17%]
tests/test_auth.py::test_origin_validation PASSED                        [ 20%]
tests/test_auth.py::test_service_bearer_auth PASSED                      [ 24%]
tests/test_contracts.py::test_health_contract PASSED                     [ 27%]
tests/test_contracts.py::test_snapshot_contract_and_structure PASSED     [ 31%]
tests/test_contracts.py::test_error_envelope_structure PASSED            [ 34%]
tests/test_contracts.py::test_validation_error_envelope PASSED           [ 37%]
tests/test_disruptions.py::test_disruption_permission PASSED             [ 41%]
tests/test_disruptions.py::test_rain_event_validation_and_application PASSED [ 44%]
tests/test_disruptions.py::test_station_outage_and_recovery PASSED       [ 48%]
tests/test_e2e.py::test_full_operational_e2e_flow PASSED                 [ 51%]
tests/test_evaluations.py::test_evaluation_execution PASSED              [ 55%]
tests/test_ingestion.py::test_telemetry_ingestion PASSED                 [ 58%]
tests/test_ingestion.py::test_counter_regression_rejected PASSED         [ 62%]
tests/test_ingestion.py::test_heartbeat_ingestion PASSED                 [ 65%]
tests/test_jobs.py::test_create_job_success PASSED                       [ 68%]
tests/test_jobs.py::test_operator_cannot_submit_other_org_satellite PASSED [ 72%]
tests/test_jobs.py::test_job_deadline_in_past_rejected PASSED            [ 75%]
tests/test_jobs.py::test_job_insufficient_onboard_data PASSED            [ 79%]
tests/test_jobs.py::test_job_idempotency_and_conflict PASSED             [ 82%]
tests/test_scheduling.py::test_scheduler_unavailable_returns_503 PASSED  [ 86%]
tests/test_scheduling.py::test_stale_schedule_version_returns_409 PASSED [ 89%]
tests/test_scheduling.py::test_valid_scheduling_and_independent_validation PASSED [ 93%]
tests/test_transfers_and_security.py::test_transfers_and_owner_evidence PASSED [ 96%]
tests/test_transfers_and_security.py::test_security_checks PASSED        [100%]

======================== 29 passed, 3 warnings in 3.24s ========================
```

### End-to-End Operational Lifecycle Verified:
1. Operator authentication & session generation.
2. Satellite inventory discovery via operational snapshot.
3. Downlink job creation with onboard data reservation.
4. Schedule optimization with independent conflict & constraint validation.
5. Station gateway confirmation of tentative contact assignment.
6. Execution authorization & simulated contact progress ingestion.
7. Job data accounting (monotonic transfer delivery, remaining work calculation).
8. Disruption injection (Rain capacity degradation) & replanning trigger.
9. Protected sample payload transfer coordination.
10. Owner decryption evidence verification.
11. FIFO vs. Optimized scheduler evaluation without live state pollution.

---

## 6. Completion Checklist

- [x] Frontend contract preserved.
- [x] Frontend endpoints implemented.
- [x] Persistent database used.
- [x] Sessions and CSRF enforced.
- [x] Organisation ownership enforced.
- [x] Scoped service identities enforced.
- [x] Satellite records treated as real application records with simulated provenance.
- [x] Simulation time separated from server time.
- [x] Scheduler output independently validated.
- [x] Station acknowledgement required for execution.
- [x] Delivery counters deduplicated and bounded.
- [x] Disruptions cause actual state changes.
- [x] Secure-transfer success requires owner evidence.
- [x] Evaluation uses identical frozen inputs.
- [x] Async operations survive or reconcile after restart.
- [x] Reset rejects old-scenario events.
- [x] No payload keys or credentials exposed.
- [x] Local setup works from a fresh checkout.
- [x] Actual integration results documented.

---

## 7. Known Limitations & Integration Dependencies

- **Scheduler Module:** When the external `scheduler/` module is not yet implemented or absent from `PYTHONPATH`, the backend gracefully reports `degraded` health and returns `503 SCHEDULER_UNAVAILABLE` for scheduling requests.
- **Security Module:** External cryptographic policy evaluation in `security/` will be integrated in Round 2; the backend provides the required adapter boundary and handles local demonstration security checks.
- **Single Process SQLite Model:** Built for local single-process prototype operation using WAL mode. Multiple Uvicorn workers sharing SQLite are not supported without an external lock manager.

---

## 8. Exact Startup Instructions

From the `backend/` directory:

```bash
# 1. Install dependencies
python -m pip install -r requirements.lock

# 2. Run migrations
python -m alembic upgrade head

# 3. Seed demonstration scenario
python -m app.cli.bootstrap

# 4. Start API server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
