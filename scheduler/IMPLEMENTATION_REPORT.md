# Orbitron Scheduler Module — Implementation Report

**Module:** Scheduler and orbital prediction  
**Shared API Contract:** `orbitron.v1`  
**Location:** `scheduler/`  
**Branch:** `agent/scheduler`  

---

## 1. Implemented interfaces

In exact accordance with `scheduler/plan.md` Section 5 and `backend/plan.md` Section 13, the following three public pure functions are implemented in `scheduler/api.py`:

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

All functions:
- Receive explicit inputs and return JSON-serializable dictionaries/lists.
- Guarantee input immutability via defensive copying.
- Perform zero database queries or HTTP mutations.
- Rely on explicit operational UTC timestamps without wall-clock dependence.
- Run completely offline without internet or external ephemeris downloads.

---

## 2. Supported orbital inputs

- Formats: Two-Line Element sets (`format: "tle"`).
- Orbit sources: `"public_tle"` and `"synthetic"`.
- Rigorous TLE validation:
  - Fixed-width 69-character lines with standard `1 ` and `2 ` prefixes.
  - Modulo-10 checksum validation on both lines.
  - Consistency of 5-digit satellite catalog numbers across Line 1 and Line 2.
  - Precise fractional day-of-year epoch extraction.
  - Discrepancy check between parsed TLE epoch and declared `epoch_at` with documented tolerance (default 86,400s).

---

## 3. Orbital-data validity policy

- Maximum propagation age policy: configurable through `max_age_days` (default 30.0 days).
- If simulation timestamp exceeds the validity window relative to TLE epoch, the module raises `OrbitalDataError` rather than fabricating synthetic positions or adjusting timestamps.
- Altitude validation: subpoint elevation must exceed 80 km to reject decayed or non-physical orbits. Coordinates must be finite with latitude in `[-90, 90]` and normalized longitude in `[-180, 180]`.

---

## 4. Scheduling assumptions

- Units: Data in bytes, transmission rates in bits per second (bps), durations in integer seconds.
- Effective transfer rate:
  $$\text{effective\_rate\_bps} = \lfloor \text{nominal\_opportunity\_rate\_bps} \times \text{weather\_capacity\_factor} \rfloor$$
  where nominal rate is $\min(\text{satellite.max\_downlink\_rate\_bps}, \text{antenna.max\_rate\_bps})$. Weather factor is applied exactly once during scheduling.
- Half-open time intervals: $[start, end)$.
- Conservative rounding:
  - Start times rounded up (ceil).
  - End times rounded down (floor).
  - Transferable bytes rounded down (floor).
  - Required durations rounded up (ceil).
- Antenna exclusivity: Antenna occupied during $[setup\_start\_at, end\_at)$ where $setup\_start\_at = start\_at - setup\_seconds$. Setup must start $\ge simulation\_time$.
- Satellite concurrency: Number of active communication intervals on a satellite at any instant $\le max\_parallel\_contacts$.
- Station sharing: Requires $sharing\_enabled = \text{True}$, owner organization in $approved\_partner\_org\_ids$, and an approved relationship in $approved\_sharing\_relationships$.

---

## 5. Objective ordering

The CP-SAT model enforces a strict hierarchical priority structure:
1. Emergency data allocated before deadlines.
2. High-priority data allocated before deadlines.
3. Routine data allocated before deadlines.
4. Job completion bonus (encouraging fully scheduled jobs).
5. Preservation of valid existing mutable bookings (reducing unnecessary schedule churn).
6. Fewer unnecessary contacts and earlier useful completion (negative penalty on completion time and contact count).

---

## 6. Split-job policy

- `allow_split: false`: The job's newly plannable remainder must be carried in at most ONE contact. If no single opportunity can carry the complete remainder before the deadline, it remains unassigned with reason `INSUFFICIENT_CAPACITY`. No intentional partial allocation is performed.
- `allow_split: true`: Work may be divided across multiple sequential, non-overlapping contacts up to $newly\_plannable\_bytes$. If only part of the remainder fits in the horizon, the planned portion is assigned and the unallocated remainder is reported in `unassigned_jobs` with code `PARTIAL_DELIVERY`.
- Job remaining bytes are not decremented in planning; allocation is distinct from backend delivery confirmation.

---

## 7. Protected-contact policy

- Protected contacts:
  - Contacts with status in `{"active", "in_progress", "communicating", "setup"}`.
  - Contacts where $setup\_start\_at \le simulation\_time < end\_at$.
  - Explicitly locked contact IDs specified in `policy.locked_contact_ids`.
- Protected contacts are preserved and cannot be moved or preempted.
- Remaining reservation accounting:
  $$reserved\_bytes = \max(0, allocated\_bytes - transferred\_bytes)$$
  $$newly\_plannable\_bytes = remaining\_bytes - \sum reserved\_bytes$$
- If supplied protected contacts are mutually contradictory or exceed job remaining bytes, the scheduler returns `status: "infeasible"` with diagnostic reasons.

---

## 8. Timeout and fallback behaviour

- Solvers operate under an explicit monotonic time budget (`time_limit_seconds`).
- If CP-SAT times out with a feasible incumbent, the incumbent is returned with `optimal: false` and `timed_out: true`.
- If CP-SAT times out without an incumbent, the priority heuristic fallback scheduler executes, applying all hard physical constraints, and returns `algorithm_used: "priority_fallback"` with `fallback_used: true`.
- All outputs are independently verified by `validate_proposed_schedule`.

---

## 9. Checks run and actual results

Full test suite of 37 tests in `scheduler/tests/` passed:

```text
============================= test session starts =============================
collected 37 items

scheduler/tests/test_cli.py::test_cli_validate_catalog PASSED            [  2%]
scheduler/tests/test_cli.py::test_cli_predict PASSED                     [  5%]
scheduler/tests/test_cli.py::test_cli_solve PASSED                       [  8%]
scheduler/tests/test_orbital.py::test_tle_checksum PASSED                [ 10%]
scheduler/tests/test_orbital.py::test_valid_tle_format PASSED            [ 13%]
scheduler/tests/test_orbital.py::test_invalid_tle_format[...] PASSED     [ 32%]
scheduler/tests/test_orbital.py::test_epoch_agreement_and_data_age PASSED [ 35%]
scheduler/tests/test_orbital.py::test_propagation_accuracy_and_stability PASSED [ 37%]
scheduler/tests/test_orbital.py::test_propagation_input_immutability PASSED [ 40%]
scheduler/tests/test_orbital.py::test_propagation_invalid_timestamp PASSED [ 43%]
scheduler/tests/test_orbital.py::test_predict_opportunities_nominal_rate_and_clipping PASSED [ 45%]
scheduler/tests/test_scale_120_satellites.py::test_120_satellite_scale_performance PASSED [ 48%]
scheduler/tests/test_scheduling.py::test_one_job_one_opportunity[fifo] PASSED [ 51%]
scheduler/tests/test_scheduling.py::test_one_job_one_opportunity[optimized] PASSED [ 54%]
scheduler/tests/test_scheduling.py::test_two_jobs_competing_for_one_antenna[fifo] PASSED [ 56%]
scheduler/tests/test_scheduling.py::test_two_jobs_competing_for_one_antenna[optimized] PASSED [ 59%]
scheduler/tests/test_scheduling.py::test_setup_causes_conflict PASSED    [ 62%]
scheduler/tests/test_scheduling.py::test_satellite_concurrency_one_vs_two PASSED [ 64%]
scheduler/tests/test_scheduling.py::test_incompatible_band_excluded PASSED [ 67%]
scheduler/tests/test_scheduling.py::test_unapproved_partner_excluded PASSED [ 70%]
scheduler/tests/test_scheduling.py::test_offline_station_excluded PASSED [ 72%]
scheduler/tests/test_scheduling.py::test_zero_capacity_factor PASSED     [ 75%]
scheduler/tests/test_scheduling.py::test_rain_reduces_capacity_numerical_scenario PASSED [ 78%]
scheduler/tests/test_scheduling.py::test_split_job_across_two_passes PASSED [ 81%]
scheduler/tests/test_scheduling.py::test_active_contact_protected PASSED [ 83%]
scheduler/tests/test_scheduling.py::test_contradictory_protected_contacts PASSED [ 86%]
scheduler/tests/test_scheduling.py::test_empty_job_set PASSED            [ 89%]
scheduler/tests/test_scheduling.py::test_expired_deadline PASSED         [ 91%]
scheduler/tests/test_scheduling.py::test_input_immutability PASSED       [ 94%]
scheduler/tests/test_scheduling.py::test_reject_unknown_algorithm PASSED [ 97%]
scheduler/tests/test_small_instance.py::test_exhaustive_enumeration_comparison PASSED [100%]

======================= 37 passed in 4.38s =======================
```

---

## 10. Backend and simulator integration verified

- **Backend Integration**:
  - `predict_opportunities(catalog, horizon)` returns opportunities matching public TypeScript `Opportunity` interface.
  - `solve_schedule(problem, algorithm, time_limit_seconds)` accepts immutable problem and returns `status`, `assignments`, `unassigned_jobs`, `metrics` matching backend adapter expectations.
  - Generates zero database IDs (backend creates contact IDs).
- **Simulator Integration**:
  - Pure `propagate_satellites(orbit_definitions, at)` calculates subpoints for simulated satellites without database dependence or state mutations.

---

## 11. 120-satellite benchmark measurements

Measured on Windows 11 with Python 3.13.14, Skyfield 1.55, OR-Tools 9.15:
- **Orbital Propagation (120 satellites)**: 0.028 seconds (28 ms).
- **Opportunity Prediction (120 satellites x 2 stations x 2-hour horizon)**: 0.355 seconds (146 opportunities).
- **CP-SAT Constrained Scheduling (30 jobs, 54 candidates)**: 0.164 seconds.
- **Solver Status**: OPTIMAL.
- **Assigned Data**: 600,000,000 bytes.
- **Validation Conflicts**: 0.

---

## 12. Known limitations

- Weather factor is modeled as a station-wide scalar capacity factor ($0.0 \dots 1.0$), not atmospheric RF absorption curves.
- Orbital calculation uses SGP4/TLE; high-precision numerical orbit determination (e.g. gravitational harmonics, solar radiation pressure) is out of scope.

---

## 13. Exact local commands

```bash
# 1. Install dependencies
python -m pip install -r scheduler/requirements.lock

# 2. Run all tests
python -m pytest scheduler/tests -v

# 3. Run 120-satellite benchmark
python -m pytest scheduler/tests/test_scale_120_satellites.py -s

# 4. Run CLI tools
python -m scheduler.cli.validate_catalog --catalog scheduler/fixtures/catalog.json --at 2026-10-31T06:00:00Z
python -m scheduler.cli.predict --catalog scheduler/fixtures/catalog.json --horizon scheduler/fixtures/horizon.json
python -m scheduler.cli.solve --input scheduler/fixtures/problem.json --algorithm optimized
```

---

## 14. Completion checklist

- [x] Required function signatures preserved.
- [x] Public field names and units preserved.
- [x] Operational time always supplied explicitly.
- [x] Runtime positions calculated from orbital data.
- [x] Runtime opportunities calculated from geometry.
- [x] Weather applied exactly once.
- [x] Antenna setup included.
- [x] Satellite concurrency enforced.
- [x] Partner approval enforced.
- [x] Active contacts protected.
- [x] Protected allocations not double-counted.
- [x] Split-job allocations bounded correctly.
- [x] FIFO uses the same physical constraints.
- [x] Optimizer output independently validated.
- [x] Timeout distinguished from infeasibility.
- [x] Fallback reported honestly.
- [x] Planned bytes distinguished from delivered bytes.
- [x] Backend and simulator interfaces verified.
- [x] Other modules and plan files unchanged.
