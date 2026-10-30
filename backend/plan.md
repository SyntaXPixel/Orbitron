# Orbitron — Backend Implementation Plan

**Upload location:** `backend/plan.md`  
**Module:** Backend  
**Plan version:** 1.0  
**Shared API contract:** `orbitron.v1`  
**Target:** A locally running backend connected to the frontend, scheduler, simulator and security modules.

---

## 1. Instructions to the implementing agent

You are implementing Orbitron’s backend.

The backend is the authoritative application service. It validates requests, stores operational records, coordinates scheduling and security, and exposes consistent information to the frontend.

### Read before implementation

Read:

1. Repository-level instructions, including any `AGENTS.md`.
2. `frontend/plan.md`.
3. This document.
4. Other available module plans, especially their integration sections.

The public TypeScript interfaces in `frontend/plan.md` define the required JSON response shapes.

Implement matching Pydantic response models. Do not rename fields, change units, alter enum values or replace responses with a different envelope.

### Responsibilities

Implement:

- FastAPI application.
- Database models and migrations.
- Authentication and sessions.
- Organisation and resource permissions.
- Frontend-facing APIs.
- Simulator and gateway ingestion APIs.
- Scheduling coordination.
- Persisted asynchronous operations.
- Snapshot assembly.
- Audit records.
- Evaluation coordination.
- Local setup and verification.

### Boundaries

Work inside `backend/`.

Do not implement the React frontend, optimization algorithms, satellite movement engine or payload cryptography in this folder.

Use adapters for the separately owned modules.

If a required module is missing, expose its unavailability honestly. Never manufacture a successful result.

Keep `backend/plan.md` unchanged unless the project owner requests a revision.

---

## 2. Product behaviour

Orbitron coordinates downlink requests across a shared ground-station network.

The application must support this sequence:

1. Satellite and station records are registered.
2. A user submits a downlink job.
3. Orbital prediction produces feasible contact opportunities.
4. The scheduler selects compatible assignments.
5. The backend validates and saves the proposed schedule.
6. A station gateway confirms its assigned contact.
7. Security checks authorize execution.
8. The simulator reports actual simulated progress.
9. The backend updates contact and job records.
10. Disruptions can trigger recovery scheduling.
11. The frontend reads the resulting saved state.

### Simulation is an external participant

The simulator must behave as a producer of operational records.

It cannot directly edit the database.

It submits registration, telemetry, progress and acknowledgements through authenticated interfaces.

The backend treats those submissions as application inputs:

- Validate identity.
- Validate resource scope.
- Validate timestamps and counters.
- Deduplicate events.
- Enforce contact constraints.
- Persist accepted observations.
- Reject invalid updates.

Every simulated satellite retains `source: "simulated"`.

Real public orbital data may support a simulated satellite’s movement. It does not make its payload or telemetry real mission data.

---

## 3. Runtime and technology choices

Use:

- Python 3.11 or newer, with a tested compatible dependency set.
- FastAPI.
- Pydantic v2.
- SQLAlchemy 2.
- Alembic.
- SQLite for the initial local prototype.
- Uvicorn.
- Pytest and HTTPX.
- An established Argon2 password-hashing library.

Use one dependency declaration for the backend and commit the appropriate dependency lock or reproducible pinned dependency file.

Do not introduce Redis, Celery, Kubernetes or additional databases for the initial prototype.

### Local addresses

```text
Frontend: http://localhost:5173
Backend:  http://localhost:8000
API:      http://localhost:8000/api/v1
```

### Execution model

For the first local implementation:

- Run one Uvicorn application worker.
- Use a persisted operation queue.
- Process queued operations through a bounded worker.
- Use short database transactions.
- Run expensive scheduling outside database write transactions.
- Keep CPU-heavy work out of the HTTP event loop.

Do not use multiple Uvicorn workers with a process-local coordination lock and claim that scheduling writes are protected across processes.

---

## 4. Folder structure

Use a structure similar to:

```text
backend/
├── plan.md
├── README.md
├── IMPLEMENTATION_REPORT.md
├── pyproject.toml
├── requirements.lock
├── alembic.ini
├── .env.example
├── .gitignore
├── app/
│   ├── main.py
│   ├── config.py
│   ├── lifespan.py
│   ├── db/
│   │   ├── session.py
│   │   ├── models.py
│   │   └── migrations/
│   ├── schemas/
│   │   ├── public.py
│   │   ├── requests.py
│   │   ├── ingestion.py
│   │   └── errors.py
│   ├── routes/
│   │   ├── health.py
│   │   ├── auth.py
│   │   ├── snapshot.py
│   │   ├── jobs.py
│   │   ├── scheduling.py
│   │   ├── events.py
│   │   ├── simulation.py
│   │   ├── transfers.py
│   │   ├── security_checks.py
│   │   ├── evaluations.py
│   │   └── ingestion.py
│   ├── services/
│   ├── adapters/
│   │   ├── scheduler.py
│   │   ├── security.py
│   │   └── simulator.py
│   ├── workers/
│   └── cli/
├── fixtures/
└── tests/
```

`requirements.lock` is the requested pinned installation file for this prototype. Its contents must reflect the dependency declaration.

Store runtime data under an ignored directory such as:

```text
backend/.runtime/
```

Do not commit:

- The working database.
- Session tokens.
- Service credentials.
- Local passwords.
- Payload files.
- Private keys.
- Local environment files.

---

## 5. Public contract compatibility

Implement every public model from Section 6 of `frontend/plan.md`:

- `Reason`
- `Organization`
- `User`
- `Session`
- `Position`
- `Satellite`
- `Antenna`
- `Station`
- `Job`
- `Opportunity`
- `Contact`
- `ScheduleChange`
- `DisruptionEvent`
- `Transfer`
- `SecurityCheck`
- `SchedulerMetrics`
- `Evaluation`
- `Operation`
- `AuditEntry`
- `SimulatorState`
- `Scenario`
- `Snapshot`
- `ApiError`

Copy their field names and meanings exactly.

Database tables may contain additional internal fields. Public response models must deliberately select safe fields.

Never serialize ORM objects indiscriminately.

### Required snapshot collections

Every snapshot includes these arrays, even when empty:

```text
organizations
satellites
stations
jobs
opportunities
contacts
schedule_changes
events
transfers
security_checks
evaluations
operations
audit
```

It also includes:

```text
meta
user
simulator
scenario
```

### Required metadata

```json
{
  "contract_version": "orbitron.v1",
  "mode": "simulation",
  "state_revision": 1,
  "schedule_version": 0,
  "server_time": "2026-10-31T06:00:00Z",
  "simulation_time": "2026-10-31T06:00:00Z",
  "visible_start_at": "2026-10-31T05:45:00Z",
  "visible_end_at": "2026-10-31T12:00:00Z",
  "services": {
    "scheduler": "unavailable",
    "security": "unavailable"
  }
}
```

These timestamps illustrate the format. They must not become fixed runtime defaults.

---

## 6. Clocks, identifiers and units

### 6.1 Two clocks

Maintain two separate concepts.

**Server time**

Used for:

- Session expiry.
- Service credential expiry.
- API operation submission/completion.
- Gateway and simulator connectivity.
- HTTP rate limiting.

**Simulation time**

Used for:

- Satellite positions.
- Visibility windows.
- Job arrival and deadlines.
- Contact execution.
- Simulated transfer intervals.
- Operational disruption events.

Pause stops simulation time. It must not prevent real-time session expiry or connectivity detection.

Use timezone-aware values internally.

Serialize public timestamps as UTC strings ending in `Z`.

### 6.2 Identifiers

Use stable string IDs.

Generate new database resource IDs on the backend unless registration explicitly supplies an externally assigned resource ID.

Never use a display name as a primary key.

Maintain internal:

- `scenario_id`
- Resource version.
- Event sequence.
- Arrival sequence for FIFO tie-breaking.

### 6.3 Units

Use:

- Bytes for data volume.
- Bits per second for rate.
- Seconds for duration.
- Degrees for coordinates.
- Kilometres for altitude.

Keep counters as integers.

Reject NaN, infinity, negative counters and values outside agreed safe limits.

For the initial public job API:

```text
1 <= data_bytes <= 1,000,000,000,000
```

Ensure public integers stay within JavaScript’s safe integer range.

### 6.4 Revisions

Maintain:

- `state_revision`: advances when frontend-visible operational state changes.
- `schedule_version`: advances when a new booking plan is committed.
- Internal `planning_revision`: advances when planning inputs materially change.

Telemetry updates must not automatically create a new schedule version.

Audit-only activity should not trigger endless scheduling retries.

---

## 7. Persistence model

Use migrations. Do not silently recreate the database on startup.

Suggested tables:

| Table | Purpose |
|---|---|
| `organizations` | Participating organisations |
| `users` | Users, roles and password hashes |
| `sessions` | Server-side sessions and CSRF material |
| `service_principals` | Simulator, satellite, station and receiver identities |
| `service_credentials` | Hashed credentials, scope, expiry and revocation |
| `satellites` | Capabilities and current satellite state |
| `satellite_orbits` | Orbital definitions and provenance |
| `satellite_observations` | Accepted telemetry history |
| `stations` | Location, operational state and connectivity |
| `antennas` | Capabilities, resource state and setup time |
| `station_partner_permissions` | Approved sharing relationships |
| `jobs` | Delivery requests and data counters |
| `opportunities` | Predicted communication opportunities |
| `contacts` | Proposed and executable bookings |
| `contact_authorizations` | Scoped execution permissions |
| `contact_progress` | Accepted progress observations |
| `schedule_changes` | Before/after booking relationships and reasons |
| `disruption_events` | Rain, outages and recovery events |
| `transfers` | Secure demonstration metadata |
| `security_checks` | Controlled verification results |
| `operations` | Persisted asynchronous work |
| `service_commands` | Commands waiting for external participants |
| `evaluations` | FIFO/proposed comparison records |
| `audit_entries` | Access and operational history |
| `idempotency_records` | Duplicate-request protection |
| `ingestion_events` | Service-event deduplication |
| `scenario_runs` | Seed, clock and scenario generation |
| `application_state` | Revisions and current run references |

### Database rules

- Enable SQLite foreign-key enforcement on every connection.
- Configure an appropriate busy timeout.
- Use WAL mode for the local file database.
- Use one SQLAlchemy session per request or worker transaction.
- Never share a session between worker threads.
- Enforce uniqueness for resource identities and ingestion keys.
- Store relations relationally rather than embedding the entire application in one JSON column.
- Structured reason lists and immutable evaluation inputs may use JSON where appropriate.

Do not rely only on SQLite to enforce every numeric constraint. Validate with application schemas and service logic.

---

## 8. Authentication and permissions

### 8.1 Browser sessions

Use backend-managed sessions.

On successful login:

1. Verify the password using the password-hashing library.
2. Generate a fresh cryptographically random session token.
3. Generate a separate CSRF token.
4. Store a hash of the session token.
5. Associate the session with the user.
6. Return the frontend `Session` object.
7. Set the session cookie.

Suggested local cookie:

```text
Name: orbitron_session
HttpOnly: true
SameSite: Lax
Path: /api/v1
Secure: false for local HTTP only
```

Do not use a `__Host-` cookie name with this local configuration.

Use a configurable session lifetime, initially two real-time hours.

Session records must be revocable.

### 8.2 CSRF and origins

Authenticated browser mutations require:

```text
X-CSRF-Token
```

Validate it against the active session using a constant-time comparison.

Validate the request origin for browser mutations.

Login does not require an existing CSRF token, but must validate allowed origin and require the expected JSON content type.

Do not treat `SameSite` alone as the complete CSRF defence.

### 8.3 CORS

Allow:

```text
http://localhost:5173
```

Enable credentials.

Allow required methods and headers, including:

```text
Content-Type
X-CSRF-Token
Idempotency-Key
```

Do not combine credentialed browser requests with a wildcard allowed origin.

### 8.4 Roles and ownership

Public roles remain:

```text
operator
network_admin
```

Operators can act only on permitted resources.

For example:

- An operator can submit a job for an owned satellite.
- An operator cannot claim another organisation by supplying a different ID.
- A station partner relationship does not grant unrelated access.
- A station receiving a payload does not receive satellite-command permission.
- An administrator’s metadata visibility does not include payload decryption keys.

Enforce permissions in backend services, not only in route decorators or frontend controls.

### 8.5 Service identities

Service principals are separate from browser sessions.

Supported service categories:

```text
simulator_controller
satellite
station_gateway
owner_receiver
```

Service APIs use scoped bearer credentials.

Store hashes of high-entropy bearer credentials.

A credential’s scope identifies permitted organisations, satellites or stations.

Never accept a request’s claimed organisation as sufficient authorization.

For the local virtual fleet, a controller may have explicit delegated access to a configured simulation namespace. This must remain an intentional development permission.

Do not expose service credentials through `/snapshot`.

---

## 9. Errors, audit and idempotency

### 9.1 Error envelope

All public errors use:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request could not be accepted.",
    "details": [
      {
        "field": "data_bytes",
        "message": "Must be a positive integer."
      }
    ],
    "request_id": "request-identifier"
  }
}
```

Normalize framework validation errors into this shape.

Use appropriate statuses:

| Status | Meaning |
|---|---|
| `400` | Invalid request semantics |
| `401` | Missing or invalid authentication |
| `403` | Authenticated but not permitted |
| `404` | Resource absent or not visible |
| `409` | Stale schedule, conflicting state or idempotency mismatch |
| `422` | Field validation failure |
| `429` | Rate limit |
| `503` | Required operational module unavailable |

Do not send stack traces or secrets to the browser.

### 9.2 Idempotency

Require `Idempotency-Key` for business mutations.

Authentication endpoints may receive the header, but must not cache or replay login credentials or session-cookie responses.

For business requests, key records by:

```text
principal + route + idempotency_key
```

Store:

- Canonical request hash.
- Scenario generation where applicable.
- Response status.
- Resulting resource or operation ID.

Behaviour:

- Same key and same payload: return the original result.
- Same key and different payload: return `409`.
- Concurrent identical submissions: create one result.
- A key from a previous reset scenario: reject with a clear scenario-changed conflict.

### 9.3 Audit

Record:

- Actor.
- Action.
- Resource.
- Outcome.
- Human-readable explanation.
- Timestamp.
- Clock basis.

Use server time for authentication and access decisions.

Use simulation time for operational events when that is the relevant timestamp.

Do not log plaintext passwords, tokens, payloads or decryption keys.

---

## 10. Frontend-facing endpoints

All public paths use `/api/v1`.

### 10.1 Health

```text
GET /health
200
```

Response:

```json
{
  "service": "orbitron-backend",
  "contract_version": "orbitron.v1",
  "status": "ready"
}
```

Allowed status:

```text
ready
degraded
```

Health must remain reachable without authentication.

Missing scheduler or security integration produces degraded readiness, not fabricated availability.

### 10.2 Authentication

```text
POST /auth/login
GET  /auth/session
POST /auth/logout
```

Login body:

```json
{
  "email": "operator@example.test",
  "password": "user-entered-value"
}
```

Login and session lookup return the exact `Session` model from the frontend plan.

Logout returns `204`.

### 10.3 Snapshot

```text
GET /snapshot
200 Snapshot
```

Optional paired query parameters:

```text
from
to
```

Validate:

- Both are supplied or both omitted.
- Both are UTC timestamps.
- End is later than start.
- Requested horizon is bounded to a documented maximum of 24 hours.

Default range:

```text
simulation_time - 15 minutes
through
simulation_time + 6 hours
```

### 10.4 Jobs

```text
POST /jobs
201 Job
```

Body:

```json
{
  "satellite_id": "sat-a-001",
  "data_bytes": 1000000000,
  "deadline_at": "2026-10-31T08:30:00Z",
  "priority": "high",
  "allow_split": true
}
```

Allowed priorities:

```text
routine
high
emergency
```

### 10.5 Scheduler

```text
POST /schedule/runs
202 Operation
```

Body:

```json
{
  "algorithm": "optimized",
  "expected_schedule_version": 7
}
```

### 10.6 Disruptions

```text
POST /events
202 Operation
```

Body fields:

```text
type
station_id
capacity_factor
expected_schedule_version
```

Types:

```text
rain
station_outage
station_recovery
```

`capacity_factor` is required and between zero and one for rain. It is `null` for the other types.

### 10.7 Simulator controls

```text
POST /simulation/actions
202 Operation
```

Support exactly:

```json
{"action":"pause"}
```

```json
{"action":"resume"}
```

```json
{"action":"step","step_seconds":60}
```

```json
{"action":"reset","seed":42}
```

### 10.8 Transfer

```text
POST /transfers
202 Operation
```

Body:

```json
{
  "contact_id": "contact-001"
}
```

### 10.9 Security checks

```text
POST /security/checks
202 Operation
```

Body:

```json
{
  "test_case": "tampered_payload",
  "contact_id": "contact-001"
}
```

Other allowed cases:

```text
expired_authorization
wrong_station
```

### 10.10 Evaluation

```text
POST /evaluations
202 Operation
```

Body:

```json
{
  "scenario_id": "scenario-001"
}
```

### 10.11 Operation lookup

```text
GET /operations/{operation_id}
200 Operation
```

Apply ownership and visibility checks.

---

## 11. Snapshot assembly

Build a snapshot from a consistent database read transaction.

Do not combine unrelated queries from changing revisions and present them as one coherent state.

### Visibility

For an operator, include:

- Owned jobs and satellites.
- Permitted station catalogue information.
- Partner contacts and related metadata the operator is allowed to inspect.
- Relevant transfers, operations, changes and audit entries.

For a network administrator, include the operational dataset permitted by the local demonstration policy.

Never include:

- Password hashes.
- Session tokens.
- CSRF data belonging to other sessions.
- Service credentials.
- Payload decryption keys.
- Raw secret-bearing service-command payloads.

### Referential completeness

When a visible record references another operational record, include the permitted referenced metadata needed to resolve it.

For example, a schedule change may reference an old contact outside the current timeline range. Include that contact as supporting metadata; the frontend will clip its rendering to the viewport.

Do not expose another organisation’s unrelated records merely to fill a reference.

### Bounded dataset

Support the agreed local dataset:

- 120 satellites.
- 12 stations.
- 1,000 jobs.
- Contacts and opportunities for the requested horizon.
- Recent operational activity with required reference closure.

Use deterministic ordering.

Do not calculate headline totals from an undisclosed truncated collection.

### Freshness

Calculate satellite telemetry freshness using simulation time.

Calculate external service connectivity using server time and received heartbeats.

A paused simulator can remain connected.

A simulator that stops sending heartbeats becomes stale, then disconnected.

---

## 12. Job lifecycle and data accounting

### Creation

On job creation:

1. Authenticate the user.
2. Check satellite ownership and access.
3. Validate the satellite is registered.
4. Validate deadline against simulation time.
5. Validate data volume.
6. Check unreserved onboard data.
7. Create the job.
8. Reserve its requested bytes.
9. Persist an audit entry.
10. Advance appropriate revisions.

Prevent two jobs from reserving the same onboard data.

### Initial state

```text
requested_bytes = submitted data_bytes
delivered_bytes = 0
remaining_bytes = requested_bytes
status = pending
```

Job `created_at` and `updated_at` use simulation time.

Use an internal monotonic arrival sequence to resolve FIFO ties.

### Priority handling

Routine and high-priority jobs remain pending until scheduling is requested or an already defined scheduling policy runs.

An emergency job may enqueue an automatic recovery scheduling operation after its creation transaction commits.

Return the newly created job immediately as `201 Job`.

Do not label it scheduled before assignments exist.

### Transitions

Typical transitions:

```text
pending → scheduled → active → completed
pending → blocked
scheduled → pending
active → pending
blocked → scheduled
```

A failed or partial contact can leave the job pending with remaining data.

The `cancelled` status exists in the public model, but a cancellation endpoint is outside this initial API. Do not invent a new frontend action without a contract update.

### Invariants

Always enforce:

```text
requested_bytes = delivered_bytes + remaining_bytes
remaining_bytes >= 0
delivered_bytes <= requested_bytes
```

Count accepted transfer progress once.

Never update job counters from both a telemetry decrement and the same contact-progress event.

---

## 13. Scheduling integration

The scheduler is a separate Python module.

The backend owns its adapter and validation. The scheduler owner implements the algorithms.

### Required scheduler interface

Reserve these functions in `scheduler/api.py`:

```python
def predict_opportunities(
    catalog: dict,
    horizon: dict,
) -> list[dict]:
    ...

def solve_schedule(
    problem: dict,
    algorithm: str,
    time_limit_seconds: int = 5,
) -> dict:
    ...

def propagate_satellites(
    orbit_definitions: list[dict],
    at: str,
) -> list[dict]:
    ...
```

These functions must be pure with respect to backend persistence:

- No database writes.
- No HTTP mutation calls.
- No editing backend records.
- No payload-key handling.

The later scheduler plan must adopt these signatures.

### Orbital ownership

The scheduler module owns reusable orbital prediction functions.

The simulator may use the same pure propagation library to keep movement and predicted opportunities consistent.

This does not give the simulator direct database access.

### Prediction input

`catalog` includes:

```text
satellites
stations
orbit_definitions
```

`horizon` includes:

```text
from_at
to_at
```

Orbital definitions include:

```text
satellite_id
format = tle
line1
line2
epoch_at
orbit_source
```

Both public and synthetically generated TLE records must be identified accurately.

Prediction returns the public `Opportunity` fields.

### Scheduling problem

Provide an immutable problem containing:

```text
contract_version
simulation_time
schedule_version
planning_revision
horizon
jobs
satellites
stations
opportunities
existing_contacts
approved_sharing_relationships
policy
```

`policy` initially specifies:

```text
protect_active_contacts = true
allow_active_preemption = false
```

### Scheduling result

Return:

```text
status
assignments
unassigned_jobs
metrics
```

Supported result statuses:

```text
feasible
infeasible
unavailable
```

Each assignment includes:

```text
job_id
satellite_id
station_id
antenna_id
opportunity_id
band
setup_start_at
start_at
end_at
expected_rate_bps
allocated_bytes
reasons
```

Each unassigned job includes:

```text
job_id
reasons
```

The backend generates contact IDs and final schedule versions.

### Backend validation

Before committing, independently validate:

- All IDs exist and match.
- Satellite and station bands are compatible.
- The opportunity belongs to the selected satellite, station and antenna.
- Communication stays inside the opportunity.
- Setup intervals are respected.
- Antenna bookings do not overlap.
- Satellite concurrency limits are respected.
- Station and antenna are usable.
- Sharing is approved.
- Data allocation does not exceed remaining unreserved work.
- Duration and rate can support allocated bytes.
- Deadlines are respected.
- Active contacts remain protected.
- Current simulation time has not invalidated proposed starts.

### Commit process

1. Capture an immutable planning problem.
2. Run prediction/optimization outside the write transaction.
3. Reopen a short write transaction.
4. Recheck relevant revisions and constraints.
5. Reject or boundedly recompute if inputs changed.
6. Commit bookings and schedule changes atomically.
7. Increment `schedule_version`.
8. Update job statuses and reasons.
9. Complete the scheduling operation.

Do not reject every schedule merely because unrelated telemetry changed `state_revision`. Revalidate the planning inputs that matter.

### Missing scheduler

If the adapter is unavailable:

- Return `503` when detected before acceptance.
- Mark an already accepted operation failed if unavailability is discovered later.
- Include `SCHEDULER_UNAVAILABLE`.
- Do not substitute hardcoded assignments.

---

## 14. Contact lifecycle and station confirmation

A saved booking is not automatically executable.

Use the public statuses:

```text
tentative
confirmed
active
completed
failed
cancelled
```

### Execution requirements

Before a contact executes:

- The booking exists.
- The station gateway confirms it.
- The station and antenna remain usable.
- The contact has an allowed authorization.
- Simulation time is inside the executable interval.
- Resource conflicts remain absent.

### Station acknowledgement

Create a scoped service command for the responsible station.

The gateway must acknowledge the correct contact and schedule version.

Reject confirmations from the wrong station or for stale assignments.

A disconnected station must not receive a fabricated confirmation.

### Partial delivery

If a contact ends before all allocated bytes transfer:

- Record the accepted transferred bytes.
- Preserve the remaining job data.
- Record a partial-delivery reason.
- Release unusable future allocations as needed.
- Enqueue recovery when appropriate.

Do not mark the whole job complete because one contact ended.

---

## 15. Simulator and service APIs

These are additional service-facing endpoints under `/api/v1`.

They do not replace or rename frontend endpoints.

### Common ingestion envelope

Service events include:

```text
event_id
scenario_id
sequence
observed_at
```

The authenticated identity determines permitted resources.

Deduplicate by scenario, principal and event ID.

Reject:

- Previous-scenario events after reset.
- Reused IDs with different payloads.
- Unpermitted resources.
- Invalid timestamps.
- Counter regressions.
- Malformed coordinates.

### 15.1 Catalogue registration

```text
POST /ingest/catalog
```

Controller-only body:

```text
event_id
scenario_id
organizations
satellites
stations
orbit_definitions
```

Use public satellite/station fields for their corresponding records.

Orbital definitions use the format in Section 13.

This endpoint is for initial registration and controlled capability updates. It must not let an ordinary gateway change ownership or approve itself as a partner.

Initial scenario setup may call the same registration service through the backend CLI.

### 15.2 Telemetry

```text
POST /ingest/telemetry
```

Body:

```text
event_id
scenario_id
sequence
satellite_id
observed_at
position
operational_status
generated_bytes_total
```

`generated_bytes_total` is a monotonically increasing generation counter within the scenario.

The backend derives new onboard data from its increase.

Delivered data is deducted through accepted contact-progress accounting, avoiding double counting.

### 15.3 Station heartbeat

```text
POST /ingest/station-heartbeats
```

Body:

```text
event_id
scenario_id
sequence
station_id
observed_at
operational_status
```

Record connectivity using the server receipt time.

Station capability changes use the controlled catalogue path.

### 15.4 Contact progress

```text
POST /ingest/contact-progress
```

Body:

```text
event_id
scenario_id
sequence
contact_id
interval_start_at
interval_end_at
cumulative_transferred_bytes
final
```

Validate:

- Reporting identity owns or is delegated the station.
- Contact was confirmed and authorized for the reported interval.
- Interval falls within the contact.
- Counter is monotonic.
- Increment is physically consistent with the configured simulated rate and interval.
- Increment does not exceed allocated or remaining data.
- Previously accepted progress is not applied again.

Use the cumulative counter to calculate the newly accepted delta.

Document a bounded late-report policy. Late reports must not authorize new transmission outside the contact window.

### 15.5 Atomic simulation ticks

```text
POST /ingest/ticks
```

Controller-only body:

```text
event_id
scenario_id
previous_simulation_time
simulation_time
telemetry[]
station_heartbeats[]
contact_progress[]
```

Purpose: allow the local virtual fleet to advance a bounded simulation interval consistently.

Requirements:

- Reuse the same validation and accounting services as individual ingestion endpoints.
- Validate the controller’s delegated resource scope.
- Require `previous_simulation_time` to match current state.
- Permit a positive step no larger than 60 simulation seconds.
- Process progress against the old/new interval and applicable contact state.
- Commit accepted records and clock advancement atomically.
- Never permit arbitrary job-status or schedule overwrites.

Pausing blocks ordinary advancing ticks.

A requested manual step permits one explicitly authorized advancement.

### 15.6 Service work retrieval

```text
GET /service/work
```

Return only the authenticated service’s:

- Pending commands.
- Relevant contact assignments.
- Required non-secret configuration.

Do not return other stations’ work or owner payload keys.

### 15.7 Command acknowledgement

```text
POST /service/commands/{command_id}/ack
```

Body:

```text
event_id
scenario_id
status
result
reasons
```

Allowed acknowledgement statuses:

```text
completed
failed
```

Validate the command owner and result schema.

An acknowledgement only proves the specified command was handled. It must not automatically prove payload delivery or integrity.

### 15.8 Transfer evidence

Provide:

```text
POST /ingest/transfer-progress
POST /ingest/delivery-receipts
```

Transfer-progress fields:

```text
event_id
scenario_id
transfer_id
forwarded_bytes
ciphertext_sha256
```

Owner receipt fields:

```text
event_id
scenario_id
transfer_id
owner_plaintext_sha256
integrity_status
owner_decryption_status
```

A partner gateway can report forwarding.

Only an authorized owner receiver can report owner decryption evidence.

The later simulation/security plans must adopt these service interfaces.

---

## 16. Disruption and recovery behaviour

### Rain

On rain:

1. Validate administrator permission.
2. Validate station and capacity factor.
3. Check expected schedule version.
4. Persist the event.
5. Apply the configured capacity factor.
6. Revalidate affected bookings.
7. Enqueue recovery scheduling.
8. Persist explanations.

Rain changes expected capacity. It does not automatically make every contact impossible.

### Outage

On outage:

- Mark the station unavailable.
- Prevent new executable contacts.
- Invalidate affected future contacts.
- Handle active contacts under the configured policy.
- Preserve already accepted delivery.
- Seek alternatives where feasible.

### Recovery

On station recovery:

- Restore the configured normal station state.
- Reconsider available capacity.
- Avoid moving unrelated bookings unnecessarily.

### Failure distinction

A disruption can be applied even if subsequent optimization fails.

Represent this honestly:

- Event: applied.
- Recovery operation: failed.
- Reasons: actual scheduling failure.
- Invalid contacts: not executable.

Do not roll an actual outage back merely because the scheduler is unavailable.

### Impossible requests

An optimizer completing successfully can still leave jobs blocked.

That is a valid operational result, not automatically an operation failure.

Return concrete blocking reasons.

---

## 17. Security integration

Reserve an adapter boundary to the security module.

The backend retains ownership of:

- HTTP authentication plumbing.
- Sessions.
- Service-principal records.
- Permission enforcement at routes/services.
- Persisted authorization metadata.

The security module provides:

- Contact policy evaluation.
- Scoped authorization generation/verification.
- Revocation rules.
- Controlled security checks.
- Secure-transfer protocol integration.

### Required policy interface

Reserve in `security/api.py`:

```python
def capabilities() -> dict:
    ...

def evaluate_contact(context: dict) -> dict:
    ...
```

The evaluation context includes:

```text
principal
satellite
station
antenna
job
contact
sharing_relationship
simulation_time
server_time
```

Return:

```text
allowed
reasons
scope
expires_at
```

Scope must bind:

```text
satellite_id
station_id
antenna_id
contact_id
allowed_action
contact_start_at
contact_end_at
```

The initial action is receive-and-forward.

Satellite commanding is outside this prototype.

### Two expiry checks

A contact permission can involve:

- A real-time credential expiry.
- A simulation-time executable contact interval.

Check both according to their clock basis.

Do not compare a simulated future contact timestamp with wall-clock credential time as if they were the same clock.

### Missing security module

If required authorization capabilities are unavailable:

- Report security unavailable.
- Keep protected execution disabled.
- Do not grant every request to make the demonstration appear functional.

Basic browser login must still function through the backend’s session implementation.

---

## 18. Secure-transfer coordination

`POST /transfers` requests an actual software demonstration.

Before acceptance, validate:

- User access.
- Contact existence.
- Partner station relationship.
- Contact readiness.
- Authorization.
- Receiver availability where known.

Persist a `Transfer` record and an asynchronous operation.

Coordinate the external gateway and owner receiver through scoped commands.

### Payload ownership

The backend coordinates metadata.

Satellite-side simulation and the owner receiver control payload encryption/decryption material.

Do not store payload decryption keys in ordinary backend tables or snapshots.

### Evidence

Populate:

- Forwarding progress.
- Ciphertext hash.
- Expected plaintext hash, if supplied by the owner-side workflow.
- Owner’s recovered plaintext hash.
- Integrity status.
- Owner decryption status.

Set `delivered` only after the owner-side receipt confirms the required verification.

A gateway’s forwarding acknowledgement alone is insufficient.

### Sample-file limitation

A small sample file can demonstrate encryption and forwarding.

Its bytes must be reported as that sample’s actual transfer size.

Do not claim that decrypting a small sample proves an entire gigabyte-scale simulated job was physically transferred.

Secure demonstration counters and abstract job-progress counters must not double-count the same delivery.

### Security checks

The controlled checks must actually exercise:

- Expired permission rejection.
- Wrong-station rejection.
- Modified ciphertext integrity failure.

Persist expected and observed results.

A check has `passed: true` only when the observed result matches the expected security behaviour.

---

## 19. Persisted asynchronous operations

Public asynchronous operations use:

```text
queued
running
succeeded
failed
```

Supported kinds remain:

```text
schedule
disruption
simulation
transfer
security_check
evaluation
```

### Acceptance transaction

For a valid asynchronous request:

1. Validate permission and initial conditions.
2. Apply idempotency handling.
3. Insert the operation.
4. Insert required resource/command records.
5. Commit.
6. Return `202 Operation`.

Do not return `202` for work that exists only in process memory.

### Worker behaviour

- Claim work atomically.
- Use bounded concurrency.
- Use fresh database sessions.
- Save progress and final state.
- Record actual errors.
- Avoid holding write locks while solving or waiting for services.

### Restart behaviour

On startup:

- Resume safely retryable queued work.
- Reconcile interrupted running work.
- Recheck external acknowledgements before issuing duplicates.
- Mark unrecoverable work failed with an interruption reason.
- Never assume an interrupted transfer succeeded.

### Timeouts

Distinguish:

- Scheduler computation timeout.
- Missing gateway acknowledgement.
- Disconnected simulator.
- Owner receiver unavailable.
- Client/browser timeout.

A browser request ending does not cancel already accepted work unless an explicit cancellation mechanism exists.

---

## 20. Evaluation coordination

Evaluation compares:

```text
fifo
optimized
```

Both must use:

- The same initial state.
- The same jobs.
- The same capabilities.
- The same opportunities.
- The same disruption trace.
- The same horizon.

Freeze the workload and event trace before running either algorithm.

Store:

```text
scenario_id
workload_id
event_trace_id
algorithm configuration
results
```

Run evaluations against isolated copies.

Do not modify the live schedule, live data counters or active contacts.

### Metrics

Return the exact frontend `SchedulerMetrics` fields:

```text
requested_bytes
delivered_before_deadline_bytes
total_jobs
on_time_jobs
urgent_jobs
urgent_on_time_jobs
resource_conflicts
scheduling_duration_ms
bookings_changed
```

Definitions:

- Count job completion only when all requested bytes arrive before its deadline.
- Count delivered-before-deadline bytes according to the replayed delivery timeline.
- Count conflicts through independent validation.
- Measure actual scheduling runtime.
- Count changed bookings according to a documented consistent rule.

Do not invent improvement percentages.

If one run fails, preserve its failure and leave its result unavailable rather than filling it with zeros.

---

## 21. Scenario bootstrap and reset

Provide a repeatable local bootstrap command.

It creates:

- Schema through migrations.
- Two demonstration organisations.
- Administrator and operator accounts.
- Service identities.
- A deterministic scenario definition.
- Initial satellite/station catalogue.
- Valid orbital definitions.

Use environment-provided or interactively generated local passwords.

Do not commit a working administrator password.

Service credentials must be generated and stored only in ignored local runtime configuration.

### Orbital data

Use validated packaged orbital data or clearly identified synthetic orbital definitions.

The scheduler’s prediction functions calculate opportunities.

Do not seed preselected successful booking outcomes.

The normal offline demo must not require a live public orbital-data download.

### Reset

Reset:

- Is administrator-only.
- Is acknowledged by the simulator/controller.
- Creates a new scenario generation.
- Preserves users and appropriate credential configuration.
- Fences off old in-flight service events.
- Resolves or fails old in-flight operations explicitly.
- Restores the configured seed and initial operational state.

Keep historical data internally where useful, but do not mix old-scenario records into the current snapshot.

A reset must not silently leave an old gateway transmitting under stale assignments.

---

## 22. Implementation order

### Round 1: backend foundation

Implement in this order:

1. Project configuration.
2. Database models and migrations.
3. Configuration loading.
4. Error envelope.
5. Session authentication and CSRF.
6. Organisation/resource access checks.
7. Health endpoint.
8. Snapshot response models.
9. Catalogue/bootstrap services.
10. Job creation and reservation accounting.
11. Scheduler adapter.
12. Persisted operations.
13. Scheduling commit validation.
14. Contact and schedule-change persistence.
15. Integration with the frontend and scheduler.

During this round, a contact may remain tentative while gateway and contact-security integrations are not yet available.

That must be visible in the actual saved state.

### Round 1 gate

Verify:

- Fresh database initialization.
- Real login.
- Correct snapshot structure.
- Real persisted job creation.
- Actual scheduler-generated assignments.
- Conflict validation.
- Persistence across backend restart.
- Frontend compatibility.

### Round 2: operational integrations

Complete:

1. Scoped service credentials.
2. Telemetry and heartbeat ingestion.
3. Atomic simulation ticks.
4. Station contact acknowledgement.
5. Contact progress accounting.
6. Disruption recovery.
7. Security policy integration.
8. Secure-transfer metadata and receipts.
9. Controlled security checks.
10. Evaluation.
11. Reset fencing.
12. Restart and failure handling.
13. End-to-end verification.

The same friend/agent who owns backend in Round 1 may implement security in Round 2. Keep ownership boundaries clear while fixing integration issues in previously owned files.

---

## 23. Verification requirements

Use temporary test databases.

Do not run destructive tests against the working demonstration database.

### Contract tests

Verify:

- Every public response matches the frontend contract.
- Required snapshot arrays are always present.
- Timestamp strings end in `Z`.
- Error envelopes match the agreed shape.
- Nullable values are represented correctly.
- All documented public endpoints exist.
- Unsupported enum values are rejected.

### Authentication and permissions

Verify:

- Incorrect password rejected.
- Session cookie established correctly.
- Session expiry uses server time.
- Logout revokes the session.
- Missing/incorrect CSRF rejected.
- Disallowed origin rejected.
- Operator cannot submit for another organisation’s satellite.
- Gateway cannot report another station’s progress.
- Gateway cannot submit owner decryption evidence.
- Revoked service credential rejected.

### Accounting and concurrency

Verify:

- Duplicate job submission creates one job.
- Different payload with reused key returns conflict.
- Concurrent requests cannot reserve the same onboard bytes twice.
- Duplicate progress does not increase delivery twice.
- Regressing counters are rejected.
- Progress outside a valid contact interval is rejected.
- Remaining bytes never become negative.
- Stale schedule commits fail safely.
- Invalid scheduler output is not saved.
- Setup-time and satellite-concurrency conflicts are detected.

### Disruptions and integration

Verify:

- Rain affects capacity.
- Outage blocks affected execution.
- Emergency creation triggers an actual recovery operation.
- Active contacts follow the configured protection policy.
- Simulator pause differs from disconnection.
- Clock advancement and reports remain consistent.
- Old events after reset are rejected.
- Missing modules produce unavailable responses.
- Restart does not fabricate completion.
- FIFO evaluation does not alter the live schedule.

### Actual end-to-end demonstration

Run:

```text
login
→ read satellite records
→ create job
→ generate bookings
→ confirm contact
→ authorize contact
→ accept simulated progress
→ apply disruption
→ recover schedule
→ execute protected sample transfer
→ verify owner receipt
→ run comparison
```

Record the actual result of every step.

---

## 24. Local commands and configuration

Provide commands equivalent to:

```text
python -m pip install -r requirements.lock
python -m alembic upgrade head
python -m app.cli.bootstrap
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

These commands are run from `backend/` after activating a compatible virtual environment.

Document how the repository root becomes importable for sibling modules. Use a deliberate package/import configuration rather than machine-specific absolute paths.

The frontend connects through `http://localhost:8000`.

### Environment example

Include non-secret placeholders for:

```dotenv
ORBITRON_ENV=local
ORBITRON_DATABASE_URL=sqlite:///.runtime/orbitron.db
ORBITRON_FRONTEND_ORIGIN=http://localhost:5173
ORBITRON_SESSION_TTL_SECONDS=7200
ORBITRON_COOKIE_SECURE=false
ORBITRON_SCHEDULER_TIME_LIMIT_SECONDS=5
```

Document any additional required settings.

Resolve the relative database path against the backend directory, independent of the caller’s current working directory.

Provide:

- Test command.
- Migration command.
- Bootstrap command.
- Startup command.
- OpenAPI export command.

Export the implemented public API for cross-module verification.

---

## 25. Deliverables and handover

Provide:

1. Complete backend source.
2. Reproducible dependencies.
3. Database migrations.
4. `.env.example`.
5. Bootstrap tooling.
6. Automated tests.
7. README.
8. `IMPLEMENTATION_REPORT.md`.

The report must state:

```text
Implemented endpoints:
Public contract version:
Database schema and migrations:
Scheduler interface status:
Simulator interface status:
Security interface status:
Checks run and actual results:
End-to-end scenarios verified:
Known limitations:
Missing dependencies:
Exact startup instructions:
```

### Completion checklist

- [ ] Frontend contract preserved.
- [ ] Frontend endpoints implemented.
- [ ] Persistent database used.
- [ ] Sessions and CSRF enforced.
- [ ] Organisation ownership enforced.
- [ ] Scoped service identities enforced.
- [ ] Satellite records treated as real application records with simulated provenance.
- [ ] Simulation time separated from server time.
- [ ] Scheduler output independently validated.
- [ ] Station acknowledgement required for execution.
- [ ] Delivery counters deduplicated and bounded.
- [ ] Disruptions cause actual state changes.
- [ ] Secure-transfer success requires owner evidence.
- [ ] Evaluation uses identical frozen inputs.
- [ ] Async operations survive or reconcile after restart.
- [ ] Reset rejects old-scenario events.
- [ ] No payload keys or credentials exposed.
- [ ] Local setup works from a fresh checkout.
- [ ] Actual integration results documented.

---

## 26. Out of scope

Do not add:

- Public deployment.
- Real satellite commanding.
- Real ISRO/NASA integrations.
- Production certification claims.
- Unnecessary distributed infrastructure.
- A second scheduling algorithm hidden inside backend routes.
- Hardcoded successful recovery outcomes.
- Automatic trust for every registered partner.
- Plaintext payload storage in the operational database.

---

## 27. Implementation references

Use official documentation to verify framework behaviour:

- [FastAPI application lifespan](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/)
- [SQLAlchemy SQLite integration](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)
- [SQLite foreign-key enforcement](https://www.sqlite.org/foreignkeys.html)
- [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [OWASP CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)

The Orbitron public interface remains the contract defined by this plan and `frontend/plan.md`.
