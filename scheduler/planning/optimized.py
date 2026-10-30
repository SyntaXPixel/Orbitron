"""Optimized scheduling using Google OR-Tools CP-SAT with fallback and validation."""

from __future__ import annotations

import time
from typing import Any

from ortools.sat.python import cp_model

from scheduler.contracts import (
    ALGORITHM_OPTIMIZED,
    PRIORITY_EMERGENCY,
    PRIORITY_HIGH,
    PRIORITY_ROUTINE,
    STATUS_FEASIBLE,
    STATUS_INFEASIBLE,
    STATUS_UNAVAILABLE,
    format_iso_utc,
    from_integer_seconds,
    make_assignment,
    parse_iso_utc,
    to_integer_seconds,
)
from scheduler.planning.candidates import Candidate, build_candidates
from scheduler.planning.explanations import build_unassigned_jobs_list
from scheduler.planning.fallback import run_priority_fallback_scheduler
from scheduler.planning.normalization import NormalizedProblem
from scheduler.planning.validation import validate_proposed_schedule


def run_optimized_scheduler(
    problem: NormalizedProblem,
    time_limit_seconds: int = 5,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Execute the CP-SAT optimized scheduler with priority-based hierarchical objectives.

    Returns:
    (status, assignments, unassigned_jobs, metrics)
    """
    start_monotonic = time.monotonic()
    origin_dt = min(problem.simulation_time_dt, problem.horizon_from_dt)
    min_contact_sec = problem.policy.get("minimum_contact_seconds", 1)

    # 1. Contradictory protected contacts check
    if problem.contradictory_protected_reasons:
        metrics = {
            "algorithm_requested": ALGORITHM_OPTIMIZED,
            "algorithm_used": ALGORITHM_OPTIMIZED,
            "solver_status": "INFEASIBLE",
            "elapsed_ms": int((time.monotonic() - start_monotonic) * 1000),
            "optimal": False,
            "fallback_used": False,
            "timed_out": False,
            "candidate_count": 0,
            "assigned_bytes": 0,
            "fully_planned_jobs": 0,
            "partially_planned_jobs": 0,
            "bookings_changed": 0,
            "validation_conflicts": problem.contradictory_protected_reasons,
            "diagnostic_reasons": problem.contradictory_protected_reasons,
        }
        return STATUS_INFEASIBLE, [], [], metrics

    # 2. Build candidates
    candidates, rejection_evidence = build_candidates(problem)

    # If no eligible jobs or no candidates, return early feasible empty result
    if not problem.eligible_job_ids or not candidates:
        unassigned_jobs = build_unassigned_jobs_list(
            problem=problem,
            candidates=candidates,
            assignments=[],
            job_rejection_evidence=rejection_evidence,
        )
        elapsed_ms = int((time.monotonic() - start_monotonic) * 1000)
        metrics = {
            "algorithm_requested": ALGORITHM_OPTIMIZED,
            "algorithm_used": ALGORITHM_OPTIMIZED,
            "solver_status": "OPTIMAL",
            "elapsed_ms": elapsed_ms,
            "optimal": True,
            "fallback_used": False,
            "timed_out": False,
            "candidate_count": len(candidates),
            "assigned_bytes": 0,
            "fully_planned_jobs": 0,
            "partially_planned_jobs": 0,
            "bookings_changed": len(problem.mutable_contacts),
            "validation_conflicts": [],
            "diagnostic_reasons": [],
        }
        return STATUS_FEASIBLE, [], unassigned_jobs, metrics

    # 3. Generate initial feasible hint using priority fallback
    hint_status, hint_assignments, _, _ = run_priority_fallback_scheduler(
        problem, candidates, rejection_evidence
    )
    hint_map: dict[tuple[str, str], dict[str, Any]] = {}
    if hint_status == STATUS_FEASIBLE:
        for asgn in hint_assignments:
            hint_map[(asgn["job_id"], asgn["opportunity_id"])] = asgn

    # 4. Build CP-SAT Model
    model = cp_model.CpModel()

    # Pre-calculate fixed intervals for protected contacts
    protected_ant_intervals: dict[str, list[Any]] = {}
    protected_sat_intervals: dict[str, list[Any]] = {}
    protected_job_intervals: dict[str, list[Any]] = {}

    for idx, pc in enumerate(problem.protected_contacts):
        try:
            pc_setup = to_integer_seconds(parse_iso_utc(pc["setup_start_at"]), origin_dt)
            pc_start = to_integer_seconds(parse_iso_utc(pc["start_at"]), origin_dt)
            pc_end = to_integer_seconds(parse_iso_utc(pc["end_at"]), origin_dt)
        except Exception:
            continue

        ant_id = pc.get("antenna_id", "")
        if pc_end > pc_setup:
            ant_iv = model.NewIntervalVar(pc_setup, pc_end - pc_setup, pc_end, f"fix_ant_{idx}")
            protected_ant_intervals.setdefault(ant_id, []).append(ant_iv)

        sat_id = pc.get("satellite_id", "")
        if pc_end > pc_start:
            sat_iv = model.NewIntervalVar(pc_start, pc_end - pc_start, pc_end, f"fix_sat_{idx}")
            protected_sat_intervals.setdefault(sat_id, []).append(sat_iv)

        jid = pc.get("job_id", "")
        if pc_end > pc_start:
            job_iv = model.NewIntervalVar(pc_start, pc_end - pc_start, pc_end, f"fix_job_{idx}")
            protected_job_intervals.setdefault(jid, []).append(job_iv)

    # Candidate decision variables
    cand_selected: list[Any] = []
    cand_comm_start: list[Any] = []
    cand_comm_dur: list[Any] = []
    cand_comm_end: list[Any] = []
    cand_comm_interval: list[Any] = []
    cand_ant_interval: list[Any] = []
    cand_alloc_bytes: list[Any] = []

    # Map existing mutable contacts for preservation bonus
    existing_mutable_keys = {
        (
            mc.get("job_id"),
            mc.get("satellite_id"),
            mc.get("station_id"),
            mc.get("antenna_id"),
            mc.get("band"),
        )
        for mc in problem.mutable_contacts
    }

    for i, cand in enumerate(candidates):
        sel_var = model.NewBoolVar(f"cand_sel_{i}")
        cand_selected.append(sel_var)

        c_start = model.NewIntVar(
            cand.earliest_comm_start_sec, cand.latest_comm_end_sec, f"comm_start_{i}"
        )
        c_dur = model.NewIntVar(0, cand.max_comm_duration_sec, f"comm_dur_{i}")
        c_end = model.NewIntVar(
            cand.earliest_comm_start_sec, cand.latest_comm_end_sec, f"comm_end_{i}"
        )
        model.Add(c_end == c_start + c_dur)

        c_iv = model.NewOptionalIntervalVar(c_start, c_dur, c_end, sel_var, f"comm_iv_{i}")
        cand_comm_start.append(c_start)
        cand_comm_dur.append(c_dur)
        cand_comm_end.append(c_end)
        cand_comm_interval.append(c_iv)

        # Antenna interval including setup
        s_setup = model.NewIntVar(
            cand.earliest_setup_start_sec, cand.latest_comm_end_sec, f"setup_start_{i}"
        )
        model.Add(s_setup == c_start - cand.setup_seconds)
        a_dur = model.NewIntVar(0, cand.max_comm_duration_sec + cand.setup_seconds, f"ant_dur_{i}")
        model.Add(a_dur == c_dur + cand.setup_seconds).OnlyEnforceIf(sel_var)
        model.Add(a_dur == 0).OnlyEnforceIf(sel_var.Not())

        a_iv = model.NewOptionalIntervalVar(s_setup, a_dur, c_end, sel_var, f"ant_iv_{i}")
        cand_ant_interval.append(a_iv)

        # Allocated bytes
        max_bytes_possible = min(cand.job_newly_plannable_bytes, cand.max_transferable_bytes)
        bytes_var = model.NewIntVar(0, max_bytes_possible, f"bytes_{i}")
        cand_alloc_bytes.append(bytes_var)

        model.Add(bytes_var >= 1).OnlyEnforceIf(sel_var)
        model.Add(bytes_var == 0).OnlyEnforceIf(sel_var.Not())
        model.Add(c_dur >= min_contact_sec).OnlyEnforceIf(sel_var)
        model.Add(c_dur == 0).OnlyEnforceIf(sel_var.Not())

        # Capacity rate constraint: 8 * alloc_bytes <= effective_rate * c_dur
        model.Add(8 * bytes_var <= cand.effective_rate_bps * c_dur)

        # Unsplit job constraint
        if not cand.allow_split:
            model.Add(bytes_var == cand.job_newly_plannable_bytes).OnlyEnforceIf(sel_var)

        # Solution hint from heuristic fallback
        hint_key = (cand.job_id, cand.opportunity_id)
        if hint_key in hint_map:
            hint_asgn = hint_map[hint_key]
            model.AddHint(sel_var, 1)
            h_start_sec = to_integer_seconds(parse_iso_utc(hint_asgn["start_at"]), origin_dt)
            h_end_sec = to_integer_seconds(parse_iso_utc(hint_asgn["end_at"]), origin_dt)
            model.AddHint(c_start, h_start_sec)
            model.AddHint(c_dur, h_end_sec - h_start_sec)
            model.AddHint(c_end, h_end_sec)
            model.AddHint(bytes_var, hint_asgn["allocated_bytes"])
        else:
            model.AddHint(sel_var, 0)
            model.AddHint(bytes_var, 0)
            model.AddHint(c_dur, 0)

    # Constraint 1: Antenna exclusivity (No overlap per antenna)
    cands_by_antenna: dict[str, list[Any]] = {}
    for i, cand in enumerate(candidates):
        cands_by_antenna.setdefault(cand.antenna_id, []).append(cand_ant_interval[i])

    all_ant_keys = set(cands_by_antenna.keys()) | set(protected_ant_intervals.keys())
    for ant_id in all_ant_keys:
        all_ivs = cands_by_antenna.get(ant_id, []) + protected_ant_intervals.get(ant_id, [])
        if len(all_ivs) > 1:
            model.AddNoOverlap(all_ivs)

    # Constraint 2: Satellite concurrency (Cumulative per satellite)
    cands_by_sat: dict[str, list[Any]] = {}
    for i, cand in enumerate(candidates):
        cands_by_sat.setdefault(cand.satellite_id, []).append(cand_comm_interval[i])

    all_sat_keys = set(cands_by_sat.keys()) | set(protected_sat_intervals.keys())
    for sat_id in all_sat_keys:
        satellite = problem.satellites_by_id.get(sat_id)
        max_parallel = int(satellite.get("max_parallel_contacts", 1)) if satellite else 1
        all_ivs = cands_by_sat.get(sat_id, []) + protected_sat_intervals.get(sat_id, [])
        if len(all_ivs) > 1:
            demands = [1 for _ in all_ivs]
            model.AddCumulative(all_ivs, demands, max_parallel)

    # Constraint 3: Job level constraints
    cands_by_job: dict[str, list[int]] = {}
    for i, cand in enumerate(candidates):
        cands_by_job.setdefault(cand.job_id, []).append(i)

    # Track fully planned job booleans for objective bonus
    job_completed_bools: list[Any] = []

    for job_id, indices in cands_by_job.items():
        job = problem.jobs_by_id[job_id]
        allow_split = job.get("allow_split", False)
        newly_plannable = problem.job_newly_plannable_bytes.get(job_id, 0)

        # Job communication intervals must not overlap
        job_comm_ivs = [cand_comm_interval[i] for i in indices] + protected_job_intervals.get(job_id, [])
        if len(job_comm_ivs) > 1:
            model.AddNoOverlap(job_comm_ivs)

        # Total allocated bytes cannot exceed newly plannable remainder
        total_job_bytes = sum(cand_alloc_bytes[i] for i in indices)
        model.Add(total_job_bytes <= newly_plannable)

        # Unsplit job: at most 1 contact
        if not allow_split:
            model.Add(sum(cand_selected[i] for i in indices) <= 1)

        # Completion indicator
        is_completed = model.NewBoolVar(f"job_completed_{job_id}")
        model.Add(total_job_bytes == newly_plannable).OnlyEnforceIf(is_completed)
        model.Add(total_job_bytes < newly_plannable).OnlyEnforceIf(is_completed.Not())
        job_completed_bools.append(is_completed)

    # Objective formulation (Section 18)
    # Scaled integer hierarchical weights:
    # Emergency bytes: 10,000 / MB (or direct scaled)
    # High priority bytes: 100 / MB
    # Routine priority bytes: 1 / MB
    # Fully planned job bonus: 50,000
    # Booking preservation bonus: 1,000
    # Contact count penalty: -10
    obj_terms: list[Any] = []
    for i, cand in enumerate(candidates):
        prio = cand.job_priority
        if prio == PRIORITY_EMERGENCY:
            weight = 10000
        elif prio == PRIORITY_HIGH:
            weight = 100
        else:
            weight = 1

        # Use bytes directly or scaled to KB to prevent any int overflow
        # With max 100 GB (10^11 bytes), weight 10,000 gives 10^15 < 2^62
        obj_terms.append(cand_alloc_bytes[i] * weight)

        # Booking preservation bonus
        match_key = (cand.job_id, cand.satellite_id, cand.station_id, cand.antenna_id, cand.band)
        if match_key in existing_mutable_keys:
            obj_terms.append(cand_selected[i] * 1000)

        # Contact count penalty (fewer unnecessary contacts)
        obj_terms.append(cand_selected[i] * -100)

        # Earlier useful completion (Section 18 requirement 6)
        obj_terms.append(-cand_comm_end[i])

    for comp_var in job_completed_bools:
        obj_terms.append(comp_var * 50000)

    model.Maximize(sum(obj_terms))

    # Solver configuration
    solver = cp_model.CpSolver()
    remaining_time = max(0.5, float(time_limit_seconds) - (time.monotonic() - start_monotonic))
    solver.parameters.max_time_in_seconds = remaining_time
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = problem.policy.get("random_seed", 42)

    status_code = solver.Solve(model)
    elapsed_ms = int((time.monotonic() - start_monotonic) * 1000)

    # 5. Process solver outcome
    if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        is_optimal = status_code == cp_model.OPTIMAL
        assignments: list[dict[str, Any]] = []

        for i, cand in enumerate(candidates):
            if solver.Value(cand_selected[i]):
                s_val = solver.Value(cand_comm_start[i])
                dur_val = solver.Value(cand_comm_dur[i])
                bytes_val = solver.Value(cand_alloc_bytes[i])
                e_val = s_val + dur_val
                setup_val = s_val - cand.setup_seconds

                setup_start_dt = from_integer_seconds(setup_val, origin_dt)
                start_dt = from_integer_seconds(s_val, origin_dt)
                end_dt = from_integer_seconds(e_val, origin_dt)

                asgn = make_assignment(
                    job_id=cand.job_id,
                    satellite_id=cand.satellite_id,
                    station_id=cand.station_id,
                    antenna_id=cand.antenna_id,
                    opportunity_id=cand.opportunity_id,
                    band=cand.band,
                    setup_start_at=format_iso_utc(setup_start_dt),
                    start_at=format_iso_utc(start_dt),
                    end_at=format_iso_utc(end_dt),
                    expected_rate_bps=cand.effective_rate_bps,
                    allocated_bytes=bytes_val,
                )
                assignments.append(asgn)

        # Sort assignments stably
        assignments.sort(
            key=lambda a: (
                a["start_at"],
                a["job_id"],
                a["opportunity_id"],
            )
        )

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

        if is_valid:
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
                "algorithm_requested": ALGORITHM_OPTIMIZED,
                "algorithm_used": ALGORITHM_OPTIMIZED,
                "solver_status": solver.StatusName(status_code),
                "elapsed_ms": elapsed_ms,
                "optimal": is_optimal,
                "fallback_used": False,
                "timed_out": not is_optimal and (elapsed_ms >= (time_limit_seconds * 1000 - 200)),
                "candidate_count": len(candidates),
                "assigned_bytes": assigned_bytes,
                "fully_planned_jobs": fully_planned,
                "partially_planned_jobs": partially_planned,
                "bookings_changed": max(0, bookings_changed),
                "validation_conflicts": [],
                "diagnostic_reasons": [],
            }
            return STATUS_FEASIBLE, assignments, unassigned_jobs, metrics

    elif status_code == cp_model.INFEASIBLE:
        metrics = {
            "algorithm_requested": ALGORITHM_OPTIMIZED,
            "algorithm_used": ALGORITHM_OPTIMIZED,
            "solver_status": "INFEASIBLE",
            "elapsed_ms": elapsed_ms,
            "optimal": False,
            "fallback_used": False,
            "timed_out": False,
            "candidate_count": len(candidates),
            "assigned_bytes": 0,
            "fully_planned_jobs": 0,
            "partially_planned_jobs": 0,
            "bookings_changed": 0,
            "validation_conflicts": ["Optimization model is mathematically infeasible"],
            "diagnostic_reasons": ["Optimization model is mathematically infeasible"],
        }
        return STATUS_INFEASIBLE, [], [], metrics

    # 6. Fallback if timeout without incumbent or invalid proposal
    fallback_status, fb_assignments, fb_unassigned, fb_metrics = run_priority_fallback_scheduler(
        problem, candidates, rejection_evidence
    )
    fb_metrics["timed_out"] = True
    fb_metrics["elapsed_ms"] = int((time.monotonic() - start_monotonic) * 1000)
    return fallback_status, fb_assignments, fb_unassigned, fb_metrics
