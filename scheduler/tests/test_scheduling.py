"""Comprehensive scheduling verification tests matching plan requirements."""

from __future__ import annotations

import copy
import pytest

from scheduler.api import solve_schedule
from scheduler.contracts import (
    ALGORITHM_FIFO,
    ALGORITHM_OPTIMIZED,
    REASON_ANTENNA_BUSY,
    REASON_BAND_MISMATCH,
    REASON_DEADLINE_UNREACHABLE,
    REASON_INSUFFICIENT_CAPACITY,
    REASON_PARTIAL_DELIVERY,
    REASON_PARTNER_NOT_APPROVED,
    REASON_STATION_OFFLINE,
    REASON_WEATHER_DEGRADED,
    STATUS_FEASIBLE,
    STATUS_INFEASIBLE,
)
from scheduler.exceptions import SchedulerInputError


def base_problem() -> dict:
    """Return a baseline minimal valid problem."""
    return {
        "contract_version": "orbitron.v1",
        "simulation_time": "2026-10-31T06:00:00Z",
        "schedule_version": 1,
        "planning_revision": 1,
        "horizon": {
            "from_at": "2026-10-31T06:00:00Z",
            "to_at": "2026-10-31T12:00:00Z",
        },
        "satellites": [
            {
                "id": "sat-1",
                "name": "Sat-1",
                "owner_org_id": "org-a",
                "supported_bands": ["X"],
                "max_downlink_rate_bps": 8000000,
                "max_parallel_contacts": 1,
                "onboard_bytes": 100000000,
                "operational_status": "available",
            }
        ],
        "stations": [
            {
                "id": "gs-1",
                "name": "GS-1",
                "owner_org_id": "org-a",
                "latitude_deg": 10.0,
                "longitude_deg": 20.0,
                "min_elevation_deg": 10.0,
                "operational_status": "online",
                "weather_capacity_factor": 1.0,
                "sharing_enabled": True,
                "approved_partner_org_ids": [],
                "antennas": [
                    {
                        "id": "ant-1",
                        "supported_bands": ["X"],
                        "max_rate_bps": 10000000,
                        "setup_seconds": 20,
                        "status": "available",
                    }
                ],
            }
        ],
        "opportunities": [
            {
                "id": "opp-1",
                "satellite_id": "sat-1",
                "station_id": "gs-1",
                "antenna_id": "ant-1",
                "band": "X",
                "start_at": "2026-10-31T07:00:00Z",
                "end_at": "2026-10-31T07:10:00Z",
                "predicted_rate_bps": 8000000,
            }
        ],
        "jobs": [
            {
                "id": "job-1",
                "satellite_id": "sat-1",
                "owner_org_id": "org-a",
                "requested_bytes": 40000000,
                "delivered_bytes": 0,
                "remaining_bytes": 40000000,
                "priority": "routine",
                "deadline_at": "2026-10-31T12:00:00Z",
                "allow_split": False,
                "status": "pending",
                "reasons": [],
                "created_at": "2026-10-31T06:00:00Z",
                "updated_at": "2026-10-31T06:00:00Z",
            }
        ],
        "existing_contacts": [],
        "approved_sharing_relationships": [],
        "policy": {
            "protect_active_contacts": True,
            "allow_active_preemption": False,
            "minimum_contact_seconds": 1,
            "random_seed": 42,
        },
    }


@pytest.mark.parametrize("algo", [ALGORITHM_FIFO, ALGORITHM_OPTIMIZED])
def test_one_job_one_opportunity(algo):
    """Test 1: One job and one suitable opportunity -> valid booking."""
    problem = base_problem()
    res = solve_schedule(problem, algorithm=algo)
    assert res["status"] == STATUS_FEASIBLE
    assert len(res["assignments"]) == 1
    asgn = res["assignments"][0]
    assert asgn["job_id"] == "job-1"
    assert asgn["allocated_bytes"] == 40000000
    assert asgn["setup_start_at"] == "2026-10-31T06:59:40Z"
    assert asgn["start_at"] == "2026-10-31T07:00:00Z"
    assert len(res["unassigned_jobs"]) == 0


@pytest.mark.parametrize("algo", [ALGORITHM_FIFO, ALGORITHM_OPTIMIZED])
def test_two_jobs_competing_for_one_antenna(algo):
    """Test 2: Two jobs competing for one antenna -> no overlapping reservations."""
    problem = base_problem()
    # Add a second competing job
    problem["jobs"].append(
        {
            "id": "job-2",
            "satellite_id": "sat-1",
            "owner_org_id": "org-a",
            "requested_bytes": 30000000,
            "delivered_bytes": 0,
            "remaining_bytes": 30000000,
            "priority": "emergency" if algo == ALGORITHM_OPTIMIZED else "routine",
            "deadline_at": "2026-10-31T12:00:00Z",
            "allow_split": False,
            "status": "pending",
            "reasons": [],
            "created_at": "2026-10-31T06:01:00Z",
            "updated_at": "2026-10-31T06:01:00Z",
        }
    )

    res = solve_schedule(problem, algorithm=algo)
    assert res["status"] == STATUS_FEASIBLE
    # Both jobs cannot fit with setup without overlapping if window is narrow or setup conflicts
    # Check that any assigned contacts on the antenna do not overlap
    asgns = res["assignments"]
    for i in range(len(asgns) - 1):
        assert asgns[i]["end_at"] <= asgns[i + 1]["setup_start_at"]


def test_setup_causes_conflict():
    """Test 3: Setup causes conflict -> conflict avoided or explained."""
    problem = base_problem()
    # Opportunity starts at 07:00:00, antenna setup is 300 seconds
    problem["stations"][0]["antennas"][0]["setup_seconds"] = 300
    # Add an existing protected contact ending at 06:58:00
    problem["existing_contacts"] = [
        {
            "id": "c-prev",
            "job_id": "job-other",
            "satellite_id": "sat-1",
            "station_id": "gs-1",
            "antenna_id": "ant-1",
            "opportunity_id": "opp-prev",
            "band": "X",
            "setup_start_at": "2026-10-31T06:40:00Z",
            "start_at": "2026-10-31T06:45:00Z",
            "end_at": "2026-10-31T06:58:00Z",
            "expected_rate_bps": 8000000,
            "allocated_bytes": 10000000,
            "transferred_bytes": 0,
            "status": "active",
        }
    ]
    # New contact setup cannot start until 06:58:00, so comm cannot start before 07:03:00!
    res = solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert res["status"] == STATUS_FEASIBLE
    if res["assignments"]:
        asgn = res["assignments"][0]
        assert asgn["setup_start_at"] >= "2026-10-31T06:58:00Z"


def test_satellite_concurrency_one_vs_two():
    """Test 4 & 5: Satellite concurrency 1 vs 2."""
    problem = base_problem()
    # 2 stations with separate antennas visible at the same time
    problem["stations"].append(
        {
            "id": "gs-2",
            "name": "GS-2",
            "owner_org_id": "org-a",
            "latitude_deg": 12.0,
            "longitude_deg": 22.0,
            "min_elevation_deg": 10.0,
            "operational_status": "online",
            "weather_capacity_factor": 1.0,
            "sharing_enabled": True,
            "approved_partner_org_ids": [],
            "antennas": [
                {
                    "id": "ant-2",
                    "supported_bands": ["X"],
                    "max_rate_bps": 10000000,
                    "setup_seconds": 10,
                    "status": "available",
                }
            ],
        }
    )
    problem["opportunities"].append(
        {
            "id": "opp-2",
            "satellite_id": "sat-1",
            "station_id": "gs-2",
            "antenna_id": "ant-2",
            "band": "X",
            "start_at": "2026-10-31T07:00:00Z",
            "end_at": "2026-10-31T07:10:00Z",
            "predicted_rate_bps": 8000000,
        }
    )
    problem["jobs"].append(
        {
            "id": "job-2",
            "satellite_id": "sat-1",
            "owner_org_id": "org-a",
            "requested_bytes": 20000000,
            "delivered_bytes": 0,
            "remaining_bytes": 20000000,
            "priority": "routine",
            "deadline_at": "2026-10-31T12:00:00Z",
            "allow_split": False,
            "status": "pending",
            "reasons": [],
            "created_at": "2026-10-31T06:01:00Z",
            "updated_at": "2026-10-31T06:01:00Z",
        }
    )

    # When max_parallel_contacts == 1: simultaneous downlink prevented!
    problem["satellites"][0]["max_parallel_contacts"] = 1
    res1 = solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert res1["status"] == STATUS_FEASIBLE
    # If both assigned, their communication intervals must NOT overlap
    if len(res1["assignments"]) == 2:
        a0, a1 = res1["assignments"][0], res1["assignments"][1]
        assert a0["end_at"] <= a1["start_at"] or a1["end_at"] <= a0["start_at"]

    # When max_parallel_contacts == 2: simultaneous downlinks permitted!
    problem["satellites"][0]["max_parallel_contacts"] = 2
    res2 = solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert res2["status"] == STATUS_FEASIBLE
    assert len(res2["assignments"]) == 2


def test_incompatible_band_excluded():
    """Test 6: Incompatible band -> assignment excluded with BAND_MISMATCH."""
    problem = base_problem()
    problem["opportunities"][0]["band"] = "Ka"  # Satellite only supports X
    res = solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert res["status"] == STATUS_FEASIBLE
    assert len(res["assignments"]) == 0
    assert len(res["unassigned_jobs"]) == 1
    assert res["unassigned_jobs"][0]["reasons"][0]["code"] == REASON_BAND_MISMATCH


def test_unapproved_partner_excluded():
    """Test 7: Unapproved partner -> assignment excluded with PARTNER_NOT_APPROVED."""
    problem = base_problem()
    problem["jobs"][0]["owner_org_id"] = "org-unapproved"
    res = solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert res["status"] == STATUS_FEASIBLE
    assert len(res["assignments"]) == 0
    assert len(res["unassigned_jobs"]) == 1
    assert res["unassigned_jobs"][0]["reasons"][0]["code"] == REASON_PARTNER_NOT_APPROVED


def test_offline_station_excluded():
    """Test 8: Offline station -> assignment excluded with STATION_OFFLINE."""
    problem = base_problem()
    problem["stations"][0]["operational_status"] = "offline"
    res = solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert res["status"] == STATUS_FEASIBLE
    assert len(res["assignments"]) == 0
    assert len(res["unassigned_jobs"]) == 1
    assert res["unassigned_jobs"][0]["reasons"][0]["code"] == REASON_STATION_OFFLINE


def test_zero_capacity_factor():
    """Test 9: Zero capacity factor -> no usable allocation."""
    problem = base_problem()
    problem["stations"][0]["weather_capacity_factor"] = 0.0
    res = solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert res["status"] == STATUS_FEASIBLE
    assert len(res["assignments"]) == 0
    assert len(res["unassigned_jobs"]) == 1
    assert res["unassigned_jobs"][0]["reasons"][0]["code"] in (REASON_WEATHER_DEGRADED, REASON_INSUFFICIENT_CAPACITY)


def test_rain_reduces_capacity_numerical_scenario():
    """Test 10 & Section 22: Rain reduces capacity factor to 0.4."""
    problem = base_problem()
    # 120,000,000 bytes, nominal rate 8,000,000 bps, window 4 minutes (240s)
    problem["jobs"][0]["remaining_bytes"] = 120000000
    problem["jobs"][0]["requested_bytes"] = 120000000
    problem["opportunities"][0]["start_at"] = "2026-10-31T07:00:00Z"
    problem["opportunities"][0]["end_at"] = "2026-10-31T07:04:00Z"  # 240 seconds
    problem["stations"][0]["weather_capacity_factor"] = 0.4

    # 1) If unsplit: 120MB does not fit 96MB -> unassigned!
    problem["jobs"][0]["allow_split"] = False
    res_unsplit = solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert len(res_unsplit["assignments"]) == 0
    assert len(res_unsplit["unassigned_jobs"]) == 1
    assert res_unsplit["unassigned_jobs"][0]["reasons"][0]["code"] == REASON_INSUFFICIENT_CAPACITY

    # 2) If split: 96MB fits (effective rate 3,200,000 * 240 / 8 = 96,000,000)
    problem["jobs"][0]["allow_split"] = True
    res_split = solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert len(res_split["assignments"]) == 1
    assert res_split["assignments"][0]["allocated_bytes"] == 96000000
    # Remaining 24MB is unassigned with PARTIAL_DELIVERY reason
    assert len(res_split["unassigned_jobs"]) == 1
    assert res_split["unassigned_jobs"][0]["reasons"][0]["code"] == REASON_PARTIAL_DELIVERY


def test_split_job_across_two_passes():
    """Test 12: Split job across two passes -> total bounded correctly."""
    problem = base_problem()
    problem["jobs"][0]["remaining_bytes"] = 50000000
    problem["jobs"][0]["allow_split"] = True

    # 2 opportunities each can carry 30MB
    problem["opportunities"] = [
        {
            "id": "opp-1",
            "satellite_id": "sat-1",
            "station_id": "gs-1",
            "antenna_id": "ant-1",
            "band": "X",
            "start_at": "2026-10-31T07:00:00Z",
            "end_at": "2026-10-31T07:00:30Z",  # 30s * 1MB/s = 30MB
            "predicted_rate_bps": 8000000,
        },
        {
            "id": "opp-2",
            "satellite_id": "sat-1",
            "station_id": "gs-1",
            "antenna_id": "ant-1",
            "band": "X",
            "start_at": "2026-10-31T08:00:00Z",
            "end_at": "2026-10-31T08:00:30Z",  # 30s * 1MB/s = 30MB
            "predicted_rate_bps": 8000000,
        },
    ]

    res = solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert res["status"] == STATUS_FEASIBLE
    assert len(res["assignments"]) == 2
    total_allocated = sum(a["allocated_bytes"] for a in res["assignments"])
    assert total_allocated == 50000000
    assert len(res["unassigned_jobs"]) == 0


def test_active_contact_protected():
    """Test 13 & 14: Active contact protected and setup already started."""
    problem = base_problem()
    # Simulation time is 06:00:00. Active contact on ant-1 from 05:59:40 to 07:05:00
    problem["existing_contacts"] = [
        {
            "id": "contact-active-1",
            "job_id": "job-prev",
            "satellite_id": "sat-1",
            "station_id": "gs-1",
            "antenna_id": "ant-1",
            "opportunity_id": "opp-1",
            "band": "X",
            "setup_start_at": "2026-10-31T05:59:40Z",
            "start_at": "2026-10-31T06:00:00Z",
            "end_at": "2026-10-31T07:05:00Z",
            "expected_rate_bps": 8000000,
            "allocated_bytes": 10000000,
            "transferred_bytes": 0,
            "status": "active",
        }
    ]
    # Opportunity 1 is occupied until 07:05:00, so new booking can only start after 07:05:00 + setup
    res = solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert res["status"] == STATUS_FEASIBLE
    if res["assignments"]:
        assert res["assignments"][0]["setup_start_at"] >= "2026-10-31T07:05:00Z"


def test_contradictory_protected_contacts():
    """Test 17: Contradictory protected contacts -> infeasible diagnostic."""
    problem = base_problem()
    problem["existing_contacts"] = [
        {
            "id": "c1",
            "job_id": "j1",
            "satellite_id": "sat-1",
            "station_id": "gs-1",
            "antenna_id": "ant-1",
            "band": "X",
            "setup_start_at": "2026-10-31T06:00:00Z",
            "start_at": "2026-10-31T06:00:20Z",
            "end_at": "2026-10-31T06:05:00Z",
            "allocated_bytes": 1000,
            "status": "active",
        },
        {
            "id": "c2",
            "job_id": "j2",
            "satellite_id": "sat-1",
            "station_id": "gs-1",
            "antenna_id": "ant-1",  # Same antenna overlapping!
            "band": "X",
            "setup_start_at": "2026-10-31T06:02:00Z",
            "start_at": "2026-10-31T06:02:20Z",
            "end_at": "2026-10-31T06:07:00Z",
            "allocated_bytes": 1000,
            "status": "active",
        },
    ]

    res = solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert res["status"] == STATUS_INFEASIBLE
    assert len(res["metrics"]["validation_conflicts"]) > 0


def test_empty_job_set():
    """Test 18: Empty job set -> valid empty result."""
    problem = base_problem()
    problem["jobs"] = []
    res = solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert res["status"] == STATUS_FEASIBLE
    assert len(res["assignments"]) == 0
    assert len(res["unassigned_jobs"]) == 0
    assert res["metrics"]["assigned_bytes"] == 0


def test_expired_deadline():
    """Test 19: Expired deadline -> explained unassigned work."""
    problem = base_problem()
    problem["jobs"][0]["deadline_at"] = "2026-10-31T06:30:00Z"  # Before opp-1 starts at 07:00:00
    res = solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert res["status"] == STATUS_FEASIBLE
    assert len(res["assignments"]) == 0
    assert len(res["unassigned_jobs"]) == 1
    assert res["unassigned_jobs"][0]["reasons"][0]["code"] == REASON_DEADLINE_UNREACHABLE


def test_input_immutability():
    """Test 23: Identical immutable inputs -> no mutation of problem."""
    problem = base_problem()
    problem_snapshot = copy.deepcopy(problem)
    solve_schedule(problem, algorithm=ALGORITHM_OPTIMIZED)
    assert problem == problem_snapshot


def test_reject_unknown_algorithm():
    """Verify unknown algorithm is rejected explicitly."""
    problem = base_problem()
    with pytest.raises(SchedulerInputError, match="Unsupported algorithm"):
        solve_schedule(problem, algorithm="genetic_search")
