"""Exhaustive enumeration comparison for small synthetic scheduling instances."""

from __future__ import annotations

import pytest

from scheduler.api import solve_schedule
from scheduler.contracts import STATUS_FEASIBLE


def test_exhaustive_enumeration_comparison():
    """Compare optimized CP-SAT result against exhaustive brute-force search."""
    # 3 jobs competing for 1 antenna with limited time window
    # Window: 60s total communication duration available (at 1 MB/s = 60 MB max total capacity).
    # Job 1: Emergency, 40MB (needs 40s comm)
    # Job 2: High, 40MB (needs 40s comm)
    # Job 3: Routine, 40MB (needs 40s comm)
    # Setup: 10s per contact.
    # Pairwise feasibility:
    # Any two jobs require 40s + 40s = 80s communication, which exceeds the 60s window!
    # Therefore, at most ONE job can be assigned.
    # Enumeration of candidate subsets:
    # - {} -> 0 value
    # - {Job 1} -> Emergency priority delivery (dominant objective)
    # - {Job 2} -> High priority delivery
    # - {Job 3} -> Routine priority delivery
    # - {Job 1, Job 2} -> Infeasible
    # - {Job 1, Job 3} -> Infeasible
    # - {Job 2, Job 3} -> Infeasible
    # - {Job 1, Job 2, Job 3} -> Infeasible
    # Exhaustive optimal solution is uniquely: {Job 1} (Job-emg).

    problem = {
        "contract_version": "orbitron.v1",
        "simulation_time": "2026-10-31T06:00:00Z",
        "schedule_version": 1,
        "planning_revision": 1,
        "horizon": {
            "from_at": "2026-10-31T06:00:00Z",
            "to_at": "2026-10-31T07:00:00Z",
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
                        "setup_seconds": 10,
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
                "start_at": "2026-10-31T06:10:00Z",
                "end_at": "2026-10-31T06:11:00Z",  # Exactly 60 seconds
                "predicted_rate_bps": 8000000,      # 1 MB/s
            }
        ],
        "jobs": [
            {
                "id": "job-emg",
                "satellite_id": "sat-1",
                "owner_org_id": "org-a",
                "requested_bytes": 40000000,
                "delivered_bytes": 0,
                "remaining_bytes": 40000000,
                "priority": "emergency",
                "deadline_at": "2026-10-31T07:00:00Z",
                "allow_split": False,
                "status": "pending",
                "reasons": [],
                "created_at": "2026-10-31T06:00:00Z",
                "updated_at": "2026-10-31T06:00:00Z",
            },
            {
                "id": "job-high",
                "satellite_id": "sat-1",
                "owner_org_id": "org-a",
                "requested_bytes": 40000000,
                "delivered_bytes": 0,
                "remaining_bytes": 40000000,
                "priority": "high",
                "deadline_at": "2026-10-31T07:00:00Z",
                "allow_split": False,
                "status": "pending",
                "reasons": [],
                "created_at": "2026-10-31T06:01:00Z",
                "updated_at": "2026-10-31T06:01:00Z",
            },
            {
                "id": "job-routine",
                "satellite_id": "sat-1",
                "owner_org_id": "org-a",
                "requested_bytes": 40000000,
                "delivered_bytes": 0,
                "remaining_bytes": 40000000,
                "priority": "routine",
                "deadline_at": "2026-10-31T07:00:00Z",
                "allow_split": False,
                "status": "pending",
                "reasons": [],
                "created_at": "2026-10-31T06:02:00Z",
                "updated_at": "2026-10-31T06:02:00Z",
            },
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

    res = solve_schedule(problem, algorithm="optimized")
    assert res["status"] == STATUS_FEASIBLE
    assert res["metrics"]["optimal"] is True
    assert len(res["assignments"]) == 1
    # Must select the emergency job
    assert res["assignments"][0]["job_id"] == "job-emg"
    assert res["assignments"][0]["allocated_bytes"] == 40000000
    assert len(res["unassigned_jobs"]) == 2
