"""Isolated evaluation replay engine."""

from __future__ import annotations

import copy
import logging
import time
from typing import Any, Dict, List, Optional

from simulation.contracts import ReplayResult
from simulation.model.faults import FaultsManager
from simulation.model.progress import parse_utc
from simulation.replay.events import ReplayEventQueue
from simulation.replay.metrics import compute_evaluation_metrics

logger = logging.getLogger(__name__)


def _validate_resource_conflicts(assignments: List[Dict[str, Any]]) -> int:
    """Independent validator checking for antenna or satellite concurrency violations."""
    conflicts = 0
    # Group assignments by antenna and check for overlapping intervals
    antenna_intervals: Dict[str, List[tuple[Any, Any]]] = {}
    sat_intervals: Dict[str, List[tuple[Any, Any]]] = {}

    for a in assignments:
        ant_id = a.get("antenna_id") or a.get("station_id")
        sat_id = a.get("satellite_id")
        start = parse_utc(a.get("setup_start_at", a["start_at"]))
        end = parse_utc(a["end_at"])

        if ant_id:
            for s2, e2 in antenna_intervals.get(ant_id, []):
                # Overlap: max(start, s2) < min(end, e2)
                if max(start, s2) < min(end, e2):
                    conflicts += 1
            antenna_intervals.setdefault(ant_id, []).append((start, end))

        if sat_id:
            for s2, e2 in sat_intervals.get(sat_id, []):
                if max(start, s2) < min(end, e2):
                    conflicts += 1
            sat_intervals.setdefault(sat_id, []).append((start, end))

    return conflicts


def _internal_schedule_solver(
    jobs: List[Dict[str, Any]],
    opportunities: List[Dict[str, Any]],
    algorithm: str,
    faults: FaultsManager,
) -> tuple[List[Dict[str, Any]], int]:
    """Fallback deterministic solver for offline evaluation replay when scheduler.api is not present."""
    start_time = time.monotonic()
    assignments = []
    antenna_busy_until: Dict[str, Any] = {}

    # Sort jobs according to algorithm
    if algorithm == "fifo":
        # First-In, First-Out by creation / arrival order
        sorted_jobs = sorted(jobs, key=lambda j: j.get("created_at", ""))
    elif algorithm == "optimized":
        # Priority-aware: emergency first, then earliest deadline
        priority_rank = {"emergency": 0, "high": 1, "routine": 2}
        sorted_jobs = sorted(
            jobs,
            key=lambda j: (priority_rank.get(j.get("priority", "routine"), 3), j.get("deadline_at", "")),
        )
    else:
        raise ValueError(f"Unsupported scheduling algorithm: '{algorithm}'")

    for job in sorted_jobs:
        job_id = job["id"]
        sat_id = job["satellite_id"]
        remaining = job["data_bytes"]
        deadline = parse_utc(job["deadline_at"])

        # Filter opportunities matching this satellite
        compatible_opps = [
            opp for opp in opportunities
            if opp.get("satellite_id") == sat_id
        ]
        compatible_opps.sort(key=lambda o: parse_utc(o["start_at"]))

        for opp in compatible_opps:
            if remaining <= 0:
                break

            opp_start = parse_utc(opp["start_at"])
            opp_end = parse_utc(opp["end_at"])

            if opp_start >= deadline:
                continue

            station_id = opp["station_id"]
            disruption = faults.get_station_disruption(station_id)
            if not disruption.is_operational:
                continue

            antenna_id = opp.get("antenna_id", f"{station_id}-ant-1")
            busy_until = antenna_busy_until.get(antenna_id)
            if busy_until and opp_start < busy_until:
                continue

            # Calculate transferable bytes
            rate = int(opp.get("expected_rate_bps", 100_000_000) * disruption.rain_capacity_factor)
            duration_sec = (min(opp_end, deadline) - opp_start).total_seconds()
            if duration_sec <= 0:
                continue

            max_bytes = int(rate * duration_sec // 8)
            alloc_bytes = min(remaining, max_bytes)
            if alloc_bytes <= 0:
                continue

            remaining -= alloc_bytes
            antenna_busy_until[antenna_id] = opp_end

            assignments.append({
                "job_id": job_id,
                "satellite_id": sat_id,
                "station_id": station_id,
                "antenna_id": antenna_id,
                "start_at": opp["start_at"],
                "end_at": opp["end_at"],
                "allocated_bytes": alloc_bytes,
                "expected_rate_bps": rate,
            })

    duration_ms = int((time.monotonic() - start_time) * 1000)
    return assignments, duration_ms


def replay_scenario(
    scenario: Dict[str, Any],
    algorithm: str,
    solver_time_limit_seconds: int = 5,
) -> Dict[str, Any]:
    """Execute isolated evaluation replay of a frozen scenario under fifo or optimized scheduling."""
    if algorithm not in ("fifo", "optimized"):
        raise ValueError(f"Algorithm '{algorithm}' is not supported. Must be 'fifo' or 'optimized'.")

    # Deep isolated copy of frozen scenario
    frozen = copy.deepcopy(scenario)
    catalog = frozen.get("catalog", {})
    opportunities = frozen.get("opportunities", [])
    initial_jobs = frozen.get("initial_jobs", [])
    raw_events = frozen.get("events", [])

    event_queue = ReplayEventQueue(raw_events)
    faults = FaultsManager()

    active_jobs: Dict[str, Dict[str, Any]] = {j["id"]: copy.deepcopy(j) for j in initial_jobs}
    delivery_events: List[Dict[str, Any]] = []
    bookings_changed = 0
    total_solver_ms = 0

    # Try importing official scheduler.api solver if available
    external_solver = None
    try:
        import scheduler.api as sched_api
        if hasattr(sched_api, "solve_schedule"):
            external_solver = sched_api.solve_schedule
    except ImportError:
        pass

    # Initial schedule run
    if external_solver:
        prob = {
            "contract_version": "orbitron.v1",
            "simulation_time": frozen.get("start_at"),
            "schedule_version": 1,
            "jobs": list(active_jobs.values()),
            "opportunities": opportunities,
            "catalog": catalog,
        }
        res = external_solver(prob, algorithm=algorithm, time_limit_seconds=solver_time_limit_seconds)
        assignments = res.get("assignments", [])
        total_solver_ms += res.get("metrics", {}).get("scheduling_duration_ms", 10)
    else:
        assignments, ms = _internal_schedule_solver(list(active_jobs.values()), opportunities, algorithm, faults)
        total_solver_ms += ms

    # Process events and simulate transmission
    for asgn in assignments:
        job = active_jobs.get(asgn["job_id"])
        if not job:
            continue

        c_start = parse_utc(asgn["start_at"])
        c_end = parse_utc(asgn["end_at"])

        # Check for disruptions occurring during or before this contact
        due_events = event_queue.pop_until(c_end)
        for ev in due_events:
            if ev.type == "rain":
                st_id = ev.payload.get("station_id")
                cf = float(ev.payload.get("capacity_factor", 1.0))
                faults.apply_rain(st_id, cf)
            elif ev.type == "station_outage":
                faults.apply_station_outage(ev.payload.get("station_id"))
            elif ev.type == "station_recovery":
                faults.apply_station_recovery(ev.payload.get("station_id"))
            elif ev.type == "job_arrival":
                new_job = ev.payload.get("job")
                if new_job:
                    active_jobs[new_job["id"]] = copy.deepcopy(new_job)
                    bookings_changed += 1

        # Check contact execution under current station conditions
        st_id = asgn["station_id"]
        st_disruption = faults.get_station_disruption(st_id)
        if not st_disruption.is_operational:
            continue

        alloc_bytes = asgn.get("allocated_bytes", 0)
        actual_delivered = int(alloc_bytes * st_disruption.rain_capacity_factor)

        delivery_events.append({
            "job_id": job["id"],
            "satellite_id": asgn["satellite_id"],
            "station_id": st_id,
            "bytes_transferred": actual_delivered,
            "delivered_at": asgn["end_at"],
            "deadline_at": job["deadline_at"],
        })

    # Validate resource conflicts
    resource_conflicts = _validate_resource_conflicts(assignments)

    # Compute public SchedulerMetrics
    all_jobs_list = list(active_jobs.values())
    metrics = compute_evaluation_metrics(
        all_jobs=all_jobs_list,
        delivery_events=delivery_events,
        resource_conflicts=resource_conflicts,
        scheduling_duration_ms=total_solver_ms,
        bookings_changed=bookings_changed,
    )

    result = ReplayResult(
        algorithm=algorithm,
        metrics=metrics,
        diagnostics={
            "scenario_id": frozen.get("id", "frozen-scenario"),
            "event_count": len(raw_events),
            "assignments_count": len(assignments),
        },
        delivery_events=delivery_events,
        final_jobs=all_jobs_list,
    )
    return result.model_dump()
