"""Candidate booking construction from eligible jobs and compatible opportunities."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from scheduler.contracts import (
    calculate_effective_rate_bps,
    calculate_required_duration_seconds,
    calculate_transferable_bytes,
    parse_iso_utc,
    to_integer_seconds,
)
from scheduler.planning.compatibility import check_job_opportunity_compatibility
from scheduler.planning.normalization import NormalizedProblem


class Candidate:
    """A feasible candidate assignment for optimization and greedy solvers."""

    def __init__(
        self,
        candidate_id: str,
        job_id: str,
        satellite_id: str,
        station_id: str,
        antenna_id: str,
        opportunity_id: str,
        band: str,
        setup_seconds: int,
        earliest_setup_start_sec: int,
        earliest_comm_start_sec: int,
        latest_comm_end_sec: int,
        max_comm_duration_sec: int,
        effective_rate_bps: int,
        max_transferable_bytes: int,
        job_newly_plannable_bytes: int,
        allow_split: bool,
        job_priority: str,
        job_created_at: str,
        job_deadline_dt: datetime,
        opp_start_dt: datetime,
        opp_end_dt: datetime,
        origin_dt: datetime,
    ) -> None:
        self.candidate_id = candidate_id
        self.job_id = job_id
        self.satellite_id = satellite_id
        self.station_id = station_id
        self.antenna_id = antenna_id
        self.opportunity_id = opportunity_id
        self.band = band
        self.setup_seconds = setup_seconds
        self.earliest_setup_start_sec = earliest_setup_start_sec
        self.earliest_comm_start_sec = earliest_comm_start_sec
        self.latest_comm_end_sec = latest_comm_end_sec
        self.max_comm_duration_sec = max_comm_duration_sec
        self.effective_rate_bps = effective_rate_bps
        self.max_transferable_bytes = max_transferable_bytes
        self.job_newly_plannable_bytes = job_newly_plannable_bytes
        self.allow_split = allow_split
        self.job_priority = job_priority
        self.job_created_at = job_created_at
        self.job_deadline_dt = job_deadline_dt
        self.opp_start_dt = opp_start_dt
        self.opp_end_dt = opp_end_dt
        self.origin_dt = origin_dt


def build_candidates(
    problem: NormalizedProblem,
) -> tuple[list[Candidate], dict[str, list[dict[str, Any]]]]:
    """Build eligible candidates and track per-job compatibility evidence.

    Returns:
    (candidates_list, rejection_reasons_by_job_id)
    """
    origin_dt = min(problem.simulation_time_dt, problem.horizon_from_dt)
    candidates: list[Candidate] = []
    job_rejection_reasons: dict[str, list[dict[str, Any]]] = {}

    min_contact_sec = problem.policy.get("minimum_contact_seconds", 1)

    for job_id in problem.eligible_job_ids:
        job = problem.jobs_by_id[job_id]
        job_rejection_reasons[job_id] = []
        newly_plannable = problem.job_newly_plannable_bytes.get(job_id, 0)
        allow_split = job.get("allow_split", False)
        priority = job.get("priority", "routine")
        created_at = job.get("created_at", "")

        try:
            deadline_dt = parse_iso_utc(job.get("deadline_at", ""))
        except Exception:
            deadline_dt = problem.horizon_to_dt

        # Check each opportunity in the problem
        for opp_id, opp in problem.opportunities_by_id.items():
            compatible, reason, effective_rate = check_job_opportunity_compatibility(job, opp, problem)
            if not compatible:
                if reason:
                    job_rejection_reasons[job_id].append(reason)
                continue

            station_id = opp["station_id"]
            antenna_id = opp["antenna_id"]
            antenna = problem.antennas_by_station_and_ant_id[(station_id, antenna_id)]
            setup_sec = int(antenna.get("setup_seconds", 0))

            opp_start_dt = parse_iso_utc(opp["start_at"])
            opp_end_dt = parse_iso_utc(opp["end_at"])

            # Setup must begin at or after simulation time
            earliest_allowed_setup_start = max(opp_start_dt - timedelta(seconds=setup_sec), problem.simulation_time_dt)
            earliest_allowed_comm_start = max(opp_start_dt, earliest_allowed_setup_start + timedelta(seconds=setup_sec))
            latest_allowed_comm_end = min(opp_end_dt, deadline_dt)

            max_duration = int((latest_allowed_comm_end - earliest_allowed_comm_start).total_seconds())
            if max_duration < min_contact_sec:
                continue

            max_transferable = calculate_transferable_bytes(effective_rate, max_duration)
            if max_transferable < 1:
                continue

            # Unsplit job constraint check
            if not allow_split and max_transferable < newly_plannable:
                # Opportunity cannot carry the whole remainder
                continue

            cand_id = f"cand-{job_id}-{opp_id}"
            cand = Candidate(
                candidate_id=cand_id,
                job_id=job_id,
                satellite_id=job.get("satellite_id", ""),
                station_id=station_id,
                antenna_id=antenna_id,
                opportunity_id=opp_id,
                band=opp.get("band", ""),
                setup_seconds=setup_sec,
                earliest_setup_start_sec=to_integer_seconds(earliest_allowed_setup_start, origin_dt),
                earliest_comm_start_sec=to_integer_seconds(earliest_allowed_comm_start, origin_dt),
                latest_comm_end_sec=to_integer_seconds(latest_allowed_comm_end, origin_dt),
                max_comm_duration_sec=max_duration,
                effective_rate_bps=effective_rate,
                max_transferable_bytes=max_transferable,
                job_newly_plannable_bytes=newly_plannable,
                allow_split=allow_split,
                job_priority=priority,
                job_created_at=created_at,
                job_deadline_dt=deadline_dt,
                opp_start_dt=opp_start_dt,
                opp_end_dt=opp_end_dt,
                origin_dt=origin_dt,
            )
            candidates.append(cand)

    # Sort stably
    candidates.sort(
        key=lambda c: (
            c.earliest_comm_start_sec,
            c.job_id,
            c.opportunity_id,
        )
    )

    return candidates, job_rejection_reasons
