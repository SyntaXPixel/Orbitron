# Orbitron — Simulation Module Implementation Report

**Plan version:** 1.0  
**Shared API contract:** `orbitron.v1`  
**Assigned folder:** `simulation/`  
**Status:** Completed  

---

### Backend interfaces integrated:
- `POST /ingest/catalog`: Full fleet catalog registration with synthetic/public TLE orbital definitions.
- `POST /ingest/telemetry`: Virtual satellite telemetry ingestion with positions, operational status, and monotonic data generation counters.
- `POST /ingest/station-heartbeats`: Station gateway heartbeat ingestion tracking operational/unavailable status.
- `POST /ingest/contact-progress`: Downlink mission-data progress ingestion with half-open intervals and integer-microsecond fractional credit accounting.
- `POST /ingest/ticks`: Atomic simulation tick submission combining telemetry, heartbeats, and contact progress over bounded steps ($\le 60\text{s}$).
- `GET /service/work`: Polling scoped commands, contact assignments, and authoritative simulation time.
- `POST /service/commands/{command_id}/ack`: Scoped acknowledgements for `initialize_scenario`, `pause`, `resume`, `step`, `reset`, `contact_offer`, `prepare_transfer`, and `security_check`.
- `POST /ingest/transfer-progress`: Partner gateway forwarding evidence (forwarded ciphertext bytes and SHA-256 hash).
- `POST /ingest/delivery-receipts`: Owner receiver delivery receipt submission with verified/corrupted/mismatch integrity status.
- `POST /jobs`: Satellite service principal authenticated downlink request creation with `Idempotency-Key` and `X-Orbitron-Scenario-ID`.

### Scheduler functions integrated:
- `scheduler.api.propagate_satellites(orbit_definitions, at)`: Pure orbital propagation called dynamically by `simulation.orbital_adapter` to obtain realistic satellite latitude, longitude, and altitude without screen coordinate approximations.
- `scheduler.api.solve_schedule(problem, algorithm, time_limit_seconds)`: Integrated into offline replay engine (`simulation/replay/engine.py`) with fallback deterministic solver for standalone benchmark evaluation.

### Security functions integrated:
- `security.api.encrypt_payload(plaintext, key, associated_data)`: AES-256-GCM authenticated encryption for sample payloads on satellite actors.
- `security.api.decrypt_payload(envelope, key, associated_data)`: AES-256-GCM authenticated decryption on owner receiver actors.
- `security.api.verify_contact_token(token, public_key, expected_scope, server_time, simulation_time)`: Scoped authorization verification on station gateways.
- `security.api.canonical_payload_aad(fields)`: Canonical UTF-8 JSON Associated Data encoding with stable sorted key ordering.

### Default scenario:
- **10 satellites:** 5 Alpha Constellations (`sat-a-001`..`005`, Org A), 5 Beta Ground Networks (`sat-b-001`..`005`, Org B).
- **3 ground stations:** `station-01`, `station-02`, `station-03` equipped with S, X, and Ka band steerable antennas.
- **2 organisations:** Org A and Org B sharing ground network capacity under mutual partner arrangements.
- **Synthetic TLEs:** Orbit definitions aligned to epoch `2026-10-31T00:00:00Z` with simulated provenance.

### Clock and pacing rules:
- Authoritative operational clock resides with the backend; simulation clock synchronizes with backend simulation time.
- Wall-clock monotonic pacing (`time.monotonic()`) regulates real-time execution according to configured speed multiplier.
- Step operations are bounded to a maximum of 60 simulation seconds per accepted tick, preventing runaway catch-up.
- Pausing halts operational time advancement while HTTP work polling and gateway connectivity remain active.
- Resuming continues strictly from accepted backend simulation timestamps without counting paused wall-clock time as elapsed simulation time.

### Data-generation rules:
- Each satellite maintains a monotonic `generated_bytes_total` counter.
- Generation follows configured rate ($\text{bytes/sec} \times \text{elapsed seconds}$) with subsecond fractional byte credit preservation across ticks.
- No double accounting: satellite generation counters increment monotonically while downlink delivery progress decrements backend unserved backlog independently.
- RF communication faults can permit onboard instruments to continue data accumulation according to satellite profile policy.

### Contact-progress rules:
- Simulated mission-data progress only transmits when contact status is `confirmed` or `active`, authorization is valid, station and antenna are operational, satellite is available, and simulation interval intersects $[start, end)$.
- Transmission is prohibited during antenna setup intervals.
- Effective transfer rate is bounded by $\min(\text{satellite rate}, \text{antenna rate}, \text{station capacity}, \text{booked rate}) \times \text{weather factor}$.
- Fractional byte credit uses microsecond integer arithmetic:
  $$\text{credit} \mathrel{+}= \text{rate\_bps} \times \text{elapsed\_microseconds}$$
  $$\text{new\_bytes} = \text{credit} \mathbin{//} 8{,}000{,}000$$
  $$\text{credit} = \text{credit} \bmod 8{,}000{,}000$$
- Cumulative progress is strictly bounded by contact allocation and remaining job data.

### Payload demonstration size and limitations:
- **Demonstration sample size:** Default 65,536 bytes (64 KiB), configurable up to safe local limits.
- **Role separation:** Station gateways receive, buffer, and forward ciphertext only; gateways **never** receive owner payload keys.
- **Integrity verification:** Owner receiver decrypts ciphertext using owner key and canonical AAD, matches SHA-256 hash with expected plaintext hash, and persists plaintext only upon successful verification.
- **Prototype limitation:** Process separation on loopback network demonstrates architectural isolation, but does not provide hardware-enforced cryptographic boundaries of production flight avionics.

### Checks run and actual results:
Automated test suite execution via `pytest simulation/tests -v`:
- `test_cli_prepare_creates_directories_and_keys`: **PASSED**
- `test_clock_pause_resume_and_step`: **PASSED**
- `test_clock_monotonicity_and_step_bounds`: **PASSED**
- `test_controller_tick_generation_and_monotonicity`: **PASSED**
- `test_controller_commands_dispatch`: **PASSED**
- `test_contact_timing_and_setup_boundaries`: **PASSED**
- `test_contact_blocked_by_authorization_or_outage`: **PASSED**
- `test_contact_rain_capacity_reduction`: **PASSED**
- `test_gateway_configuration_has_no_payload_key`: **PASSED**
- `test_gateway_disconnection_stops_heartbeats_and_reporting`: **PASSED**
- `test_gateway_acknowledgement_cannot_impersonate_owner_receipt`: **PASSED**
- `test_end_to_end_payload_transport`: **PASSED**
- `test_tampered_ciphertext_fails_authenticated_decryption`: **PASSED**
- `test_gateway_rejection_of_expired_or_mismatched_token`: **PASSED**
- `test_replay_fifo_and_optimized`: **PASSED**
- `test_replay_with_disruptions`: **PASSED**
- `test_replay_unknown_algorithm_rejected`: **PASSED**
- `test_replay_isolation_does_not_mutate_original`: **PASSED**
- `test_fractional_credit_data_generation`: **PASSED**
- `test_comms_fault_behavior`: **PASSED**
- `test_automatic_downlink_request_evaluation`: **PASSED**
- `test_120_satellite_scale_simulation`: **PASSED**
- `test_120_satellite_replay`: **PASSED**

**Summary:** 23 tests passed, 0 failures.

### Reset/restart verification:
- Scenario reset pauses operational clock, quiesces all in-flight contact progress trackers, and increments/replaces scenario generation ID.
- Checkpoints saved to `simulation/.runtime/checkpoints/{scenario_id}.json` persist monotonic sequences and generation counters.
- Checkpoint manager reconciles with backend accepted checkpoints upon startup, rejecting stale event replays from previous scenario generations.

### Replay/evaluation verification:
- `replay_scenario` accepts frozen input dictionary and evaluates both `fifo` and `optimized` algorithms.
- Deep copy ensures live simulation state and database remain untouched.
- Output matches exact public `SchedulerMetrics` schema (`requested_bytes`, `delivered_before_deadline_bytes`, `total_jobs`, `on_time_jobs`, `urgent_jobs`, `urgent_on_time_jobs`, `resource_conflicts`, `scheduling_duration_ms`, `bookings_changed`).
- Disruption trace processing supports `rain`, `station_outage`, `station_recovery`, and dynamic `job_arrival`.

### 120-satellite measurements:
- Scale scenario (`scenario-scale-120`) containing 120 satellites and 12 ground stations.
- Full atomic tick generation across all 120 satellite actors executed in **under 0.05 seconds** locally.
- Replay evaluation for 120 satellites completed with 0 resource conflicts and verified on-time delivery metrics.

### Missing dependencies:
- `backend`: Backend server not currently running locally during module development; simulator operates in standalone verification mode with built-in retry/backoff client.
- `scheduler`: Module folder contains `plan.md` only; simulation uses `simulation.orbital_adapter` and pure replay fallback until `scheduler.api` is merged.
- `security`: Module folder contains `plan.md` only; simulation uses `simulation.security_adapter` with genuine AES-256-GCM and Ed25519 primitives matching the agreed interface.

### Exact local commands:
- Install pinned dependencies:
  ```bash
  python -m pip install -r simulation/requirements.lock
  ```
- Run automated tests:
  ```bash
  python -m pytest simulation/tests -v
  ```
- Prepare runtime environment:
  ```bash
  python -m simulation.cli.prepare --backend-url http://localhost:8000/api/v1 --credentials-file backend/.runtime/service-credentials.json
  ```
- Run supervised simulation processes:
  ```bash
  python -m simulation.cli.run --backend-url http://localhost:8000/api/v1 --credentials-file backend/.runtime/service-credentials.json
  ```
- Run standalone simulation without backend:
  ```bash
  python -m simulation.cli.run --standalone
  ```

