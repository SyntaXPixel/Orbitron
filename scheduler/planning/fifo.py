"""FIFO baseline scheduling implementation."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from scheduler.contracts import (
    ALGORITHM_FIFO,
    STATUS_FEASIBLE,
    calculate_effective_rate_bps,
    calculate_required_duration_seconds,
    calculate_transferable_bytes,
    format_iso_utc,
    from_integer_seconds,
    make_assignment,
    parse_iso_utc,
    to_integer_seconds,
)
from scheduler.planning.candidates import Candidate, build_candidates
from scheduler.planning.explanations import build_unassigned_jobs_list
from scheduler.planning.normalization import NormalizedProblem
from scheduler.planning.validation import validate_proposed_schedule


def check_antenna_conflict(
    setup_start: int,
    end: int,
    antenna_intervals: list[tuple[int, int]],
) -> bool:
    """Return True if [setup_start, end) overlaps any interval in antenna_intervals."""
    for s, e in antenna_intervals:
        if max(setup_start, s) < min(end, e):
            return True
    return False


def check_satellite_conflict(
    start: int,
    end: int,
    satellite_intervals: list[tuple[int, int]],
    max_parallel: int,
) -> bool:
    """Return True if adding [start, end) would exceed satellite max_parallel_contacts."""
    events: list[tuple[int, int]] = [(start, 1), (end, -1)]
    for s, e in satellite_intervals:
        # Only consider intervals that overlap [start, end)
        if max(start, s) < min(end, e):
            events.append((s, 1))
            events.append((e, -1))

    # Sort events; ends (-1) before starts (+1)
    events.sort(key=lambda x: (x[0], x[1]))
    current = 0
    for t, delta in events:
        current += delta
        if current > max_parallel:
            return True
    return False


def check_job_conflict(
    start: int,
    end: int,
    job_intervals: list[tuple[int, int]],
) -> bool:
    """Return True if [start, end) overlaps any interval for the same job."""
    for s, e in job_intervals:
        if max(start, s) < min(end, e):
            return True
    return False


def run_fifo_scheduler(
    problem: NormalizedProblem,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Execute the genuine FIFO scheduling baseline.

    Returns:
    (status, assignments, unassigned_jobs, metrics)
    """
    origin_dt = min(problem.simulation_time_dt, problem.horizon_from_dt)
    min_contact_sec = problem.policy.get("minimum_contact_seconds", 1)

    # Build candidates
    candidates, rejection_evidence = build_candidates(problem)

    # Sort jobs by genuine FIFO criteria (Section 16):
    # 1. Arrival sequence if present
    # 2. created_at
    # 3. Job ID
    sorted_job_ids = list(problem.eligible_job_ids)
    sorted_job_ids.sort(
        key=lambda jid: (
            problem.jobs_by_id[jid].get("arrival_sequence", 0),
            problem.jobs_by_id[jid].get("created_at", ""),
            jid,
        )
    )

    # Initialize resource usage with protected contacts
    antenna_usage: dict[str, list[tuple[int, int]]] = {}
    satellite_usage: dict[str, list[tuple[int, int]]] = {}
    job_usage: dict[str, list[tuple[int, int]]] = {}

    for pc in problem.protected_contacts:
        try:
            pc_setup = to_integer_seconds(parse_iso_utc(pc["setup_start_at"]), origin_dt)
            pc_start = to_integer_seconds(parse_iso_utc(pc["start_at"]), origin_dt)
            pc_end = to_integer_seconds(parse_iso_utc(pc["end_at"]), origin_dt)
        except Exception:
            continue

        ant_id = pc.get("antenna_id", "")
        if ant_id not in antenna_usage:
            antenna_usage[ant_id] = []
        antenna_usage[ant_id].append((pc_setup, pc_end))

        sat_id = pc.get("satellite_id", "")
        if sat_id not in satellite_usage:
            satellite_usage[sat_id] = []
        satellite_usage[sat_id].append((pc_start, pc_end))

        jid = pc.get("job_id", "")
        if jid not in job_usage:
            job_usage[jid] = []
        job_usage[jid].append((pc_start, pc_end))

    assignments: list[dict[str, Any]] = []

    for job_id in sorted_job_ids:
        job = problem.jobs_by_id[job_id]
        allow_split = job.get("allow_split", False)
        newly_plannable = problem.job_newly_plannable_bytes.get(job_id, 0)
        remaining_needed = newly_plannable

        # Get candidates for this job
        job_cands = [c for c in candidates if c.job_id == job_id]
        job_cands.sort(key=lambda c: (c.earliest_comm_start_sec, c.opportunity_id))

        if not allow_split:
            # Unsplit job: must cover entire newly_plannable bytes in ONE contact
            for cand in job_cands:
                req_duration = calculate_required_duration_seconds(
                    newly_plannable, cand.effective_rate_bps
                )
                req_duration = max(req_duration, min_contact_sec)

                latest_start = cand.latest_comm_end_sec - req_duration
                if latest_start < cand.earliest_comm_start_sec:
                    continue

                ant_id = cand.antenna_id
                sat_id = cand.satellite_id
                max_parallel = int(
                    problem.satellites_by_id[sat_id].get("max_parallel_contacts", 1)
                )

                # Search for earliest feasible start
                found_start: int | None = None
                for t_start in range(cand.earliest_comm_start_sec, latest_start + 1):
                    t_setup = t_start - cand.setup_seconds
                    t_end = t_start + req_duration

                    if check_antenna_conflict(t_setup, t_end, antenna_usage.get(ant_id, [])):
                        continue
                    if check_satellite_conflict(
                        t_start, t_end, satellite_usage.get(sat_id, []), max_parallel
                    ):
                        continue
                    if check_job_conflict(t_start, t_end, job_usage.get(job_id, [])):
                        continue

                    found_start = t_start
                    break

                if found_start is not None:
                    t_setup = found_start - cand.setup_seconds
                    t_end = found_start + req_duration

                    setup_start_dt = from_integer_seconds(t_setup, origin_dt)
                    start_dt = from_integer_seconds(found_start, origin_dt)
                    end_dt = from_integer_seconds(t_end, origin_dt)

                    asgn = make_assignment(
                        job_id=job_id,
                        satellite_id=sat_id,
                        station_id=cand.station_id,
                        antenna_id=ant_id,
                        opportunity_id=cand.opportunity_id,
                        band=cand.band,
                        setup_start_at=format_iso_utc(setup_start_dt),
                        start_at=format_iso_utc(start_dt),
                        end_at=format_iso_utc(end_dt),
                        expected_rate_bps=cand.effective_rate_bps,
                        allocated_bytes=newly_plannable,
                    )
                    assignments.append(asgn)

                    antenna_usage.setdefault(ant_id, []).append((t_setup, t_end))
                    satellite_usage.setdefault(sat_id, []).append((found_start, t_end))
                    job_usage.setdefault(job_id, []).append((found_start, t_end))
                    remaining_needed = 0
                    break
        else:
            # Split job: can allocate across multiple sequential contacts
            for cand in job_cands:
                if remaining_needed <= 0:
                    break

                ant_id = cand.antenna_id
                sat_id = cand.satellite_id
                max_parallel = int(
                    problem.satellites_by_id[sat_id].get("max_parallel_contacts", 1)
                )

                # Find earliest feasible gap in this candidate
                # Try from earliest start up to latest start
                best_start: int | None = None
                best_duration: int = 0
                t_cur = cand.earliest_comm_start_sec

                while t_cur <= cand.latest_comm_end_sec - min_contact_sec:
                    t_setup = t_cur - cand.setup_seconds
                    t_trial_end = t_cur + min_contact_sec

                    if (
                        check_antenna_conflict(t_setup, t_trial_end, antenna_usage.get(ant_id, []))
                        or check_satellite_conflict(
                            t_cur, t_trial_end, satellite_usage.get(sat_id, []), max_parallel
                        )
                        or check_job_conflict(t_cur, t_trial_end, job_usage.get(job_id, []))
                    ):
                        t_cur += 1
                        continue

                    # Found a start! Determine maximum duration available at this start
                    dur = min_contact_sec
                    while t_cur + dur < cand.latest_comm_end_sec:
                        next_end = t_cur + dur + 1
                        if (
                            check_antenna_conflict(t_setup, next_end, antenna_usage.get(ant_id, []))
                            or check_satellite_conflict(
                                t_cur, next_end, satellite_usage.get(sat_id, []), max_parallel
                            )
                            or check_job_conflict(t_cur, next_end, job_usage.get(job_id, []))
                        ):
                            break
                        dur += 1

                    best_start = t_cur
                    best_duration = dur
                    break

                if best_start is not None and best_duration >= min_contact_sec:
                    max_gap_bytes = calculate_transferable_bytes(
                        cand.effective_rate_bps, best_duration
                    )
                    if max_gap_bytes < 1:
                        continue

                    bytes_to_alloc = min(remaining_needed, max_gap_bytes)
                    used_duration = calculate_required_duration_seconds(
                        bytes_to_alloc, cand.effective_rate_bps
                    )
                    used_duration = max(used_duration, min_contact_sec)

                    t_setup = best_start - cand.setup_seconds
                    t_end = best_start + used_duration

                    setup_start_dt = from_integer_seconds(t_setup, origin_dt)
                    start_dt = from_integer_seconds(best_start, origin_dt)
                    end_dt = from_integer_seconds(t_end, origin_dt)

                    asgn = make_assignment(
                        job_id=job_id,
                        satellite_id=sat_id,
                        station_id=cand.station_id,
                        antenna_id=ant_id,
                        opportunity_id=cand.opportunity_id,
                        band=cand.band,
                        setup_start_at=format_iso_utc(setup_start_dt),
                        start_at=format_iso_utc(start_dt),
                        end_at=format_iso_utc(end_dt),
                        expected_rate_bps=cand.effective_rate_bps,
                        allocated_bytes=bytes_to_alloc,
                    )
                    assignments.append(asgn)

                    antenna_usage.setdefault(ant_id, []).append((t_setup, t_end))
                    satellite_usage.setdefault(sat_id, []).append((best_start, t_end))
                    job_usage.setdefault(job_id, []).append((best_start, t_end))
                    remaining_needed -= bytes_to_alloc

    # Build unassigned jobs list with explanation reasons
    unassigned_jobs = build_unassigned_jobs_list(
        problem=problem,
        candidates=candidates,
        assignments=assignments,
        job_rejection_evidence=rejection_evidence,
    )

    # Independent validation
    is_valid, validation_conflicts = validate_proposed_schedule(
        problem, assignments, unassigned_jobs
    )

    # Calculate metrics
    assigned_bytes = sum(a.get("allocated_bytes", 0) for a in assignments)
    fully_planned = sum(
        1
        for jid in problem.eligible_job_ids
        if sum(a["allocated_bytes"] for a in assignments if a["job_id"] == jid)
        >= problem.job_newly_plannable_bytes[jid]
    )
    partially_planned = sum(
        1
        for jid in problem.eligible_job_ids
        if 0
        < sum(a["allocated_bytes"] for a in assignments if a["job_id"] == jid)
        < problem.job_newly_plannable_bytes[jid]
    )

    # Bookings changed: compare new mutable assignments against mutable existing contacts
    bookings_changed = len(problem.mutable_contacts)
    for mc in problem.mutable_contacts:
        for asgn in assignments:
            if (
                asgn["job_id"] == mc.get("job_id")
                and asgn["satellite_id"] == mc.get("satellite_id")
                and asgn["station_id"] == mc.get("station_id")
                and asgn["antenna_id"] == mc.get("antenna_id")
                and asgn["band"] == mc.get("band")
                and asgn["start_at"] == mc.get("start_at")
                and asgn["end_at"] == mc.get("end_at")
                and asgn["allocated_bytes"] == mc.get("allocated_bytes")
            ):
                bookings_changed -= 1
                break

    metrics = {
        "algorithm_requested": ALGORITHM_FIFO,
        "algorithm_used": ALGORITHM_FIFO,
        "solver_status": "FEASIBLE" if is_valid else "INVALID",
        "elapsed_ms": 0,
        "optimal": False,
        "fallback_used": False,
        "timed_out": False,
        "candidate_count": len(candidates),
        "assigned_bytes": assigned_bytes,
        "fully_planned_jobs": fully_planned,
        "partially_planned_jobs": partially_planned,
        "bookings_changed": max(0, bookings_changed),
        "validation_conflicts": validation_conflicts,
        "diagnostic_reasons": [],
    }

    status = STATUS_FEASIBLE if is_valid else "unavailable"
    return status, assignments, unassigned_jobs, metrics
