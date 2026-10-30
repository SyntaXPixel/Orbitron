"""Explanation and diagnostic reason generation for schedule outcomes."""

from __future__ import annotations

from typing import Any

from scheduler.contracts import (
    REASON_ANTENNA_BUSY,
    REASON_BAND_MISMATCH,
    REASON_DEADLINE_UNREACHABLE,
    REASON_INSUFFICIENT_CAPACITY,
    REASON_NO_VISIBLE_PASS,
    REASON_PARTIAL_DELIVERY,
    REASON_PARTNER_NOT_APPROVED,
    REASON_SETUP_CONFLICT,
    REASON_STATION_OFFLINE,
    REASON_WEATHER_DEGRADED,
    make_reason,
    make_unassigned_job,
    parse_iso_utc,
)
from scheduler.planning.candidates import Candidate
from scheduler.planning.normalization import NormalizedProblem


def build_unassigned_reasons_for_job(
    job_id: str,
    problem: NormalizedProblem,
    candidates: list[Candidate],
    allocated_bytes: int,
    rejection_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Determine precise reasons for unassigned or partially assigned job data."""
    job = problem.jobs_by_id[job_id]
    sat_id = job.get("satellite_id", "")
    newly_plannable = problem.job_newly_plannable_bytes.get(job_id, 0)
    allow_split = job.get("allow_split", False)

    reasons: list[dict[str, Any]] = []

    # Case 1: Partial delivery for a split job
    if 0 < allocated_bytes < newly_plannable:
        unallocated = newly_plannable - allocated_bytes
        reasons.append(
            make_reason(
                REASON_PARTIAL_DELIVERY,
                f"{allocated_bytes} bytes allocated in current planning window. "
                f"Remaining {unallocated} bytes requires another compatible opportunity.",
                [job_id],
            )
        )
        return reasons

    # Case 2: Zero bytes allocated
    # Check if satellite has any opportunities in the problem at all
    sat_opps = [o for o in problem.opportunities_by_id.values() if o.get("satellite_id") == sat_id]
    if not sat_opps:
        reasons.append(
            make_reason(
                REASON_NO_VISIBLE_PASS,
                f"No compatible visible pass found for satellite '{sat_id}' within current planning horizon.",
                [job_id, sat_id],
            )
        )
        return reasons

    # Check deadline relation to opportunities
    try:
        deadline_dt = parse_iso_utc(job.get("deadline_at", ""))
        all_after_deadline = all(parse_iso_utc(o["start_at"]) >= deadline_dt for o in sat_opps)
        if all_after_deadline:
            reasons.append(
                make_reason(
                    REASON_DEADLINE_UNREACHABLE,
                    f"Job deadline '{job.get('deadline_at')}' occurs before any available contact opportunity.",
                    [job_id],
                )
            )
            return reasons
    except Exception:
        pass

    # Check rejection evidence if no candidates were viable
    job_cands = [c for c in candidates if c.job_id == job_id]
    if not job_cands:
        # Check specific rejection reasons collected during compatibility filtering
        codes = {r.get("code") for r in rejection_evidence}
        if REASON_PARTNER_NOT_APPROVED in codes:
            reasons.append(
                make_reason(
                    REASON_PARTNER_NOT_APPROVED,
                    "Partner sharing is not approved on visible stations.",
                    [job_id],
                )
            )
        elif REASON_STATION_OFFLINE in codes:
            reasons.append(
                make_reason(
                    REASON_STATION_OFFLINE,
                    "Ground stations visible during horizon are offline.",
                    [job_id],
                )
            )
        elif REASON_BAND_MISMATCH in codes:
            reasons.append(
                make_reason(
                    REASON_BAND_MISMATCH,
                    "No ground station antenna supports the satellite frequency band.",
                    [job_id, sat_id],
                )
            )
        elif REASON_WEATHER_DEGRADED in codes:
            reasons.append(
                make_reason(
                    REASON_WEATHER_DEGRADED,
                    "Severe weather has reduced ground station capacity factor to zero.",
                    [job_id],
                )
            )
        elif REASON_SETUP_CONFLICT in codes:
            reasons.append(
                make_reason(
                    REASON_SETUP_CONFLICT,
                    "Antenna setup time cannot fit before pass end or job deadline.",
                    [job_id],
                )
            )
        elif not allow_split:
            reasons.append(
                make_reason(
                    REASON_INSUFFICIENT_CAPACITY,
                    f"Unsplit job remaining data ({newly_plannable} bytes) exceeds the single-pass capacity "
                    f"of all available opportunities before the deadline.",
                    [job_id],
                )
            )
        else:
            reasons.append(
                make_reason(
                    REASON_INSUFFICIENT_CAPACITY,
                    "Available contact opportunities have insufficient usable capacity before deadline.",
                    [job_id],
                )
            )
        return reasons

    # Candidates existed, but were not assigned because of competition / antenna busy
    reasons.append(
        make_reason(
            REASON_ANTENNA_BUSY,
            "Compatible antenna opportunities were allocated to higher-priority work or constrained by resources.",
            [job_id],
        )
    )
    return reasons


def build_unassigned_jobs_list(
    problem: NormalizedProblem,
    candidates: list[Candidate],
    assignments: list[dict[str, Any]],
    job_rejection_evidence: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Build unassigned jobs list for all eligible jobs with unallocated work."""
    # Compute allocated bytes per job from assignments
    allocated_by_job: dict[str, int] = {}
    for asgn in assignments:
        jid = asgn["job_id"]
        allocated_by_job[jid] = allocated_by_job.get(jid, 0) + asgn.get("allocated_bytes", 0)

    unassigned_list: list[dict[str, Any]] = []

    for job_id in problem.eligible_job_ids:
        newly_plannable = problem.job_newly_plannable_bytes.get(job_id, 0)
        allocated = allocated_by_job.get(job_id, 0)

        if allocated < newly_plannable:
            reasons = build_unassigned_reasons_for_job(
                job_id=job_id,
                problem=problem,
                candidates=candidates,
                allocated_bytes=allocated,
                rejection_evidence=job_rejection_evidence.get(job_id, []),
            )
            unassigned_list.append(make_unassigned_job(job_id, reasons))

    return unassigned_list
