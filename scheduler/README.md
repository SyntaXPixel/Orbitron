# Orbitron — Scheduler and Orbital Prediction Module

This module implements satellite orbital propagation, ground-station contact visibility prediction, and conflict-free communication scheduling for Orbitron under the `orbitron.v1` shared contract.

## Capabilities

1. **Orbital Propagation (`propagate_satellites`)**:
   - Pure, deterministic SGP4 orbital propagation using Skyfield.
   - Calculates geographic subpoints (latitude, longitude, altitude in km) at explicit UTC timestamps.
   - Fully offline with bundled timescales (no internet connection required).

2. **Contact Opportunity Prediction (`predict_opportunities`)**:
   - Predicts geometric visibility intervals `[start_at, end_at)` between satellites and station antennas.
   - Handles horizon boundaries, conservative integer-second rounding, and antenna setup times.
   - Nominal transfer rates computed from satellite and antenna capabilities.

3. **Constrained Scheduling (`solve_schedule`)**:
   - **Optimized CP-SAT Algorithm**: Global integer constraint satisfaction using Google OR-Tools CP-SAT with sequential priority-ordered objectives.
   - **FIFO Baseline**: Genuine FIFO scheduling based on arrival/creation order under identical physical constraints.
   - **Priority Heuristic Fallback**: Fast feasible construction when time limits or solver constraints require degraded operation.

4. **Independent Validation (`validate_proposed_schedule`)**:
   - Independent validator verifying all resource exclusivity, satellite concurrency, partner authorizations, deadlines, and rate bounds before proposals are accepted.

5. **Explanations and Reason Generation**:
   - Provides granular diagnostics and standardized reason codes (`NO_VISIBLE_PASS`, `BAND_MISMATCH`, `STATION_OFFLINE`, `ANTENNA_BUSY`, `DEADLINE_UNREACHABLE`, `INSUFFICIENT_CAPACITY`, `PARTNER_NOT_APPROVED`, `PARTIAL_DELIVERY`, `WEATHER_DEGRADED`).

---

## Directory Layout

```text
scheduler/
├── plan.md                       # Implementation plan (preserved)
├── README.md                     # Module documentation
├── IMPLEMENTATION_REPORT.md      # Formal delivery report
├── requirements.in               # High-level dependencies
├── requirements.lock             # Pinned dependency lockfile
├── __init__.py                   # Package exports
├── api.py                        # Public API (predict_opportunities, solve_schedule, propagate_satellites)
├── contracts.py                  # Contract constants, schemas, time and unit conversions
├── exceptions.py                 # Custom scheduler exception hierarchy
├── orbital/                      # Orbital prediction & propagation subsystem
│   ├── __init__.py
│   ├── cache.py                  # Thread-safe in-memory timescale and satellite cache
│   ├── tle.py                    # TLE format validation, checksums, and epoch verification
│   ├── propagation.py            # Satellite propagation calculations
│   └── opportunities.py          # Opportunity visibility prediction
├── planning/                     # Constrained scheduling subsystem
│   ├── __init__.py
│   ├── normalization.py          # Problem validation and protected contact indexing
│   ├── compatibility.py          # Filtering and explanation evidence
│   ├── candidates.py             # Candidate generation and interval bounds
│   ├── fifo.py                   # Genuine FIFO baseline scheduler
│   ├── fallback.py               # Priority-based feasible fallback scheduler
│   ├── optimized.py              # CP-SAT constraint optimization model
│   ├── validation.py             # Standalone independent constraint validator
│   └── explanations.py           # Reason and explanation generation
├── cli/                          # Demonstration and diagnostic CLI tools
│   ├── __init__.py
│   ├── solve.py                  # Problem solver CLI
│   ├── predict.py                # Opportunity prediction CLI
│   └── validate_catalog.py       # Catalog validation and propagation CLI
├── fixtures/                     # Test data fixtures
│   ├── catalog.json              # Sample satellite, station, and orbital definitions
│   ├── horizon.json              # Sample prediction horizon
│   └── problem.json              # Full sample planning problem
└── tests/                        # Pytest verification suite
    ├── __init__.py
    ├── test_orbital.py           # Orbital mechanics and TLE parsing tests
    ├── test_scheduling.py        # Complete scheduling acceptance criteria tests
    ├── test_small_instance.py    # Exhaustive enumeration verification
    ├── test_scale_120_satellites.py # 120-satellite benchmark
    └── test_cli.py               # Command line tool tests
```

---

## Installation & Requirements

From the repository root:

```bash
python -m pip install -r scheduler/requirements.lock
```

Primary libraries:
- `skyfield>=1.55`
- `sgp4>=2.27`
- `ortools>=9.15.6755`
- `pytest>=9.2.0`

---

## CLI Usage

All CLI tools can be run directly from the repository root:

### 1. Validate Catalogue Fixture
```bash
python -m scheduler.cli.validate_catalog --catalog scheduler/fixtures/catalog.json --at 2026-10-31T06:00:00Z
```

### 2. Predict Contact Opportunities
```bash
python -m scheduler.cli.predict --catalog scheduler/fixtures/catalog.json --horizon scheduler/fixtures/horizon.json --output opportunities.json
```

### 3. Solve Scheduling Problem
```bash
# Optimized CP-SAT
python -m scheduler.cli.solve --input scheduler/fixtures/problem.json --algorithm optimized --output result.json

# FIFO Baseline
python -m scheduler.cli.solve --input scheduler/fixtures/problem.json --algorithm fifo --output result_fifo.json
```

---

## Running Verification Checks

Run the automated test suite from the repository root:

```bash
python -m pytest scheduler/tests -v
```

Run the 120-satellite benchmark with performance timings:

```bash
python -m pytest scheduler/tests/test_scale_120_satellites.py -s
```

---

## Public Python Interface

```python
from scheduler.api import predict_opportunities, solve_schedule, propagate_satellites

# 1. Propagation
positions = propagate_satellites(
    orbit_definitions=catalog["orbit_definitions"],
    at="2026-10-31T06:00:00Z",
)

# 2. Opportunity Prediction
opportunities = predict_opportunities(
    catalog=catalog,
    horizon={"from_at": "2026-10-31T06:00:00Z", "to_at": "2026-10-31T18:00:00Z"},
)

# 3. Schedule Optimization
result = solve_schedule(
    problem=problem_dict,
    algorithm="optimized",  # or "fifo"
    time_limit_seconds=5,
)
```
