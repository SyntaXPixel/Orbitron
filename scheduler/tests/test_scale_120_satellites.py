"""Scale performance measurement for a repeatable 120-satellite constellation scenario."""

from __future__ import annotations

import time
import pytest

from scheduler.api import predict_opportunities, propagate_satellites, solve_schedule
from scheduler.contracts import STATUS_FEASIBLE
from scheduler.orbital.tle import compute_tle_checksum


def generate_120_satellite_catalog() -> tuple[dict, dict]:
    """Generate a repeatable synthetic 120-satellite constellation and 4 global stations."""
    satellites = []
    orbit_definitions = []

    # 12 planes with 10 satellites each at 550 km altitude (inclination 53 degrees, MM ~ 15.0)
    sat_idx = 1
    for plane in range(12):
        raan = plane * 30.0
        for sat_in_plane in range(10):
            ma = sat_in_plane * 36.0
            sat_id = f"sat-const-{sat_idx:03d}"
            sat_num = 50000 + sat_idx

            l1_prefix = f"1 {sat_num:05d}U 26001A   26304.00000000  .00001000  00000+0  10000-3 0  999"
            c1 = compute_tle_checksum(l1_prefix)
            line1 = l1_prefix + str(c1)

            l2_prefix = f"2 {sat_num:05d}  53.0000 {raan:8.4f} 0001000   0.0000 {ma:8.4f} 15.10000000    1"
            c2 = compute_tle_checksum(l2_prefix)
            line2 = l2_prefix + str(c2)

            satellites.append(
                {
                    "id": sat_id,
                    "name": f"Constellation-{sat_idx}",
                    "owner_org_id": "org-constellation",
                    "supported_bands": ["X", "Ka"],
                    "max_downlink_rate_bps": 20000000,
                    "max_parallel_contacts": 1,
                    "onboard_bytes": 500000000,
                    "operational_status": "available",
                }
            )

            orbit_definitions.append(
                {
                    "satellite_id": sat_id,
                    "format": "tle",
                    "line1": line1,
                    "line2": line2,
                    "epoch_at": "2026-10-31T00:00:00Z",
                    "orbit_source": "synthetic",
                }
            )
            sat_idx += 1

    stations = [
        {
            "id": "gs-north",
            "name": "Northern Station",
            "owner_org_id": "org-constellation",
            "latitude_deg": 65.0,
            "longitude_deg": -18.0,
            "min_elevation_deg": 10.0,
            "operational_status": "online",
            "weather_capacity_factor": 1.0,
            "sharing_enabled": True,
            "approved_partner_org_ids": [],
            "antennas": [
                {
                    "id": "ant-n1",
                    "supported_bands": ["X", "Ka"],
                    "max_rate_bps": 25000000,
                    "setup_seconds": 15,
                    "status": "available",
                }
            ],
        },
        {
            "id": "gs-south",
            "name": "Southern Station",
            "owner_org_id": "org-constellation",
            "latitude_deg": -33.0,
            "longitude_deg": -70.0,
            "min_elevation_deg": 10.0,
            "operational_status": "online",
            "weather_capacity_factor": 1.0,
            "sharing_enabled": True,
            "approved_partner_org_ids": [],
            "antennas": [
                {
                    "id": "ant-s1",
                    "supported_bands": ["X", "Ka"],
                    "max_rate_bps": 25000000,
                    "setup_seconds": 15,
                    "status": "available",
                }
            ],
        },
    ]

    catalog = {
        "satellites": satellites,
        "stations": stations,
        "orbit_definitions": orbit_definitions,
    }

    horizon = {
        "from_at": "2026-10-31T06:00:00Z",
        "to_at": "2026-10-31T08:00:00Z",
    }

    return catalog, horizon


def test_120_satellite_scale_performance():
    """Execute and measure 120-satellite scenario performance."""
    catalog, horizon = generate_120_satellite_catalog()
    assert len(catalog["satellites"]) == 120
    assert len(catalog["orbit_definitions"]) == 120

    # 1. Measure pure propagation time for 120 satellites
    t_prop_start = time.perf_counter()
    positions = propagate_satellites(catalog["orbit_definitions"], "2026-10-31T06:00:00Z")
    t_prop_elapsed = time.perf_counter() - t_prop_start
    assert len(positions) == 120

    # 2. Measure opportunity prediction time over 2-hour horizon
    t_pred_start = time.perf_counter()
    opportunities = predict_opportunities(catalog, horizon)
    t_pred_elapsed = time.perf_counter() - t_pred_start
    assert len(opportunities) > 0

    # 3. Create 30 diverse jobs
    jobs = []
    for i in range(1, 31):
        sat_id = f"sat-const-{i:03d}"
        jobs.append(
            {
                "id": f"job-const-{i:03d}",
                "satellite_id": sat_id,
                "owner_org_id": "org-constellation",
                "requested_bytes": 25000000,
                "delivered_bytes": 0,
                "remaining_bytes": 25000000,
                "priority": "emergency" if i <= 3 else ("high" if i <= 10 else "routine"),
                "deadline_at": "2026-10-31T08:00:00Z",
                "allow_split": i % 2 == 0,
                "status": "pending",
                "reasons": [],
                "created_at": "2026-10-31T06:00:00Z",
                "updated_at": "2026-10-31T06:00:00Z",
            }
        )

    problem = {
        "contract_version": "orbitron.v1",
        "simulation_time": "2026-10-31T06:00:00Z",
        "schedule_version": 1,
        "planning_revision": 1,
        "horizon": horizon,
        "satellites": catalog["satellites"],
        "stations": catalog["stations"],
        "opportunities": opportunities,
        "jobs": jobs,
        "existing_contacts": [],
        "approved_sharing_relationships": [],
        "policy": {
            "protect_active_contacts": True,
            "allow_active_preemption": False,
            "minimum_contact_seconds": 1,
            "random_seed": 42,
        },
    }

    # 4. Measure scheduling time (optimized)
    t_sched_start = time.perf_counter()
    res = solve_schedule(problem, algorithm="optimized", time_limit_seconds=5)
    t_sched_elapsed = time.perf_counter() - t_sched_start

    assert res["status"] == STATUS_FEASIBLE
    assert len(res["metrics"]["validation_conflicts"]) == 0

    print(f"\n--- 120-Satellite Constellation Benchmark Results ---")
    print(f"Propagation time (120 sats): {t_prop_elapsed:.3f} s")
    print(f"Prediction time (120 sats x 2 stations x 2h): {t_pred_elapsed:.3f} s ({len(opportunities)} opportunities)")
    print(f"Scheduling time (30 jobs, {res['metrics']['candidate_count']} candidates): {t_sched_elapsed:.3f} s")
    print(f"Solver status: {res['metrics']['solver_status']}")
    print(f"Assigned bytes: {res['metrics']['assigned_bytes']} bytes")
    print(f"Fully planned jobs: {res['metrics']['fully_planned_jobs']}")
    print(f"Partially planned jobs: {res['metrics']['partially_planned_jobs']}")
    print(f"Conflicts: {res['metrics']['validation_conflicts']}")
