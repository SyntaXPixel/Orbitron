"""Independent schedule validation separate from optimization construction."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from scheduler.contracts import (
    calculate_effective_rate_bps,
    calculate_transferable_bytes,
    parse_iso_utc,
)
from scheduler.planning.normalization import NormalizedProblem


def validate_proposed_schedule(
    problem: NormalizedProblem,
    assignments: list[dict[str, Any]],
    unassigned_jobs: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """Perform independent constraint verification on proposed schedule.

    Returns:
    (is_valid, list_of_conflict_reasons)
    """
    conflicts: list[str] = []

    # Check for underlying contradictory protected contacts first
    if problem.contradictory_protected_reasons:
        for reason in problem.contradictory_protected_reasons:
            conflicts.append(f"Infeasible baseline: {reason}")
        return False, conflicts

    min_contact_sec = problem.policy.get("minimum_contact_seconds", 1)

    # Track allocations per job
    job_allocations: dict[str, list[dict[str, Any]]] = {}
    job_total_bytes: dict[str, int] = {}

    # Track antenna occupancy intervals [setup_start, end)
    antenna_intervals: dict[str, list[tuple[datetime, datetime, str]]] = {}
    # Track satellite communication intervals [start, end)
    satellite_intervals: dict[str, list[tuple[datetime, datetime, str]]] = {}

    # 16. Initialize intervals with protected contacts
    for pc in problem.protected_contacts:
        pc_id = pc.get("id", "protected")
        try:
            pc_setup = parse_iso_utc(pc["setup_start_at"])
            pc_start = parse_iso_utc(pc["start_at"])
            pc_end = parse_iso_utc(pc["end_at"])
        except Exception as exc:
            conflicts.append(f"Invalid timestamp in protected contact '{pc_id}': {exc}")
            continue

        ant_id = pc.get("antenna_id", "")
        if ant_id not in antenna_intervals:
            antenna_intervals[ant_id] = []
        antenna_intervals[ant_id].append((pc_setup, pc_end, f"protected:{pc_id}"))

        sat_id = pc.get("satellite_id", "")
        if sat_id not in satellite_intervals:
            satellite_intervals[sat_id] = []
        satellite_intervals[sat_id].append((pc_start, pc_end, f"protected:{pc_id}"))

    # Validate each new assignment
    for idx, asgn in enumerate(assignments):
        prefix = f"Assignment #{idx} (job={asgn.get('job_id')}, opp={asgn.get('opportunity_id')})"

        job_id = asgn.get("job_id")
        sat_id = asgn.get("satellite_id")
        station_id = asgn.get("station_id")
        antenna_id = asgn.get("antenna_id")
        opp_id = asgn.get("opportunity_id")
        band = asgn.get("band")

        # 1. IDs resolve correctly
        job = problem.jobs_by_id.get(job_id)
        if not job:
            conflicts.append(f"{prefix}: Job '{job_id}' not found in problem")
            continue

        satellite = problem.satellites_by_id.get(sat_id)
        if not satellite:
            conflicts.append(f"{prefix}: Satellite '{sat_id}' not found in problem")
            continue

        station = problem.stations_by_id.get(station_id)
        if not station:
            conflicts.append(f"{prefix}: Station '{station_id}' not found in problem")
            continue

        antenna = problem.antennas_by_station_and_ant_id.get((station_id, antenna_id))
        if not antenna:
            conflicts.append(f"{prefix}: Antenna '{antenna_id}' not found on station '{station_id}'")
            continue

        opp = problem.opportunities_by_id.get(opp_id)
        if not opp:
            conflicts.append(f"{prefix}: Opportunity '{opp_id}' not found in problem")
            continue

        # 2. Job/satellite relationship
        if job.get("satellite_id") != sat_id:
            conflicts.append(
                f"{prefix}: Job satellite '{job.get('satellite_id')}' != assignment satellite '{sat_id}'"
            )

        # 3. Opportunity resource matching
        if opp.get("satellite_id") != sat_id or opp.get("station_id") != station_id or opp.get("antenna_id") != antenna_id:
            conflicts.append(f"{prefix}: Assignment resources do not match opportunity '{opp_id}'")

        # 4. Band compatibility
        if band not in satellite.get("supported_bands", []) or band not in antenna.get("supported_bands", []):
            conflicts.append(f"{prefix}: Band '{band}' not supported by both satellite and antenna")

        # 5. Sharing permissions
        job_org = job.get("owner_org_id", "")
        station_org = station.get("owner_org_id", "")
        if job_org != station_org:
            sharing_enabled = station.get("sharing_enabled", False)
            approved_partners = station.get("approved_partner_org_ids", [])
            has_approved_rel = (job_org, station_id) in problem.approved_sharing_set
            if not (sharing_enabled and (job_org in approved_partners) and has_approved_rel):
                conflicts.append(f"{prefix}: Unapproved partner sharing for org '{job_org}' on station '{station_id}'")

        # Parse timing
        try:
            setup_start_dt = parse_iso_utc(asgn["setup_start_at"])
            start_dt = parse_iso_utc(asgn["start_at"])
            end_dt = parse_iso_utc(asgn["end_at"])
            opp_start_dt = parse_iso_utc(opp["start_at"])
            opp_end_dt = parse_iso_utc(opp["end_at"])
            deadline_dt = parse_iso_utc(job.get("deadline_at", opp["end_at"]))
        except Exception as exc:
            conflicts.append(f"{prefix}: Failed to parse timestamps: {exc}")
            continue

        # 6. Positive duration
        comm_seconds = int((end_dt - start_dt).total_seconds())
        if comm_seconds < min_contact_sec:
            conflicts.append(
                f"{prefix}: Communication duration {comm_seconds}s is below minimum {min_contact_sec}s"
            )

        # 18. Planning boundary
        if setup_start_dt < problem.simulation_time_dt:
            conflicts.append(
                f"{prefix}: Setup start {asgn['setup_start_at']} is before simulation time {problem.raw_problem.get('simulation_time')}"
            )

        # 7. Visibility bounds
        if start_dt < opp_start_dt or end_dt > opp_end_dt:
            conflicts.append(
                f"{prefix}: Communication [{asgn['start_at']}, {asgn['end_at']}) outside visibility [{opp['start_at']}, {opp['end_at']})"
            )

        # 8. Deadline bounds
        if end_dt > deadline_dt:
            conflicts.append(
                f"{prefix}: Communication end {asgn['end_at']} exceeds job deadline {job.get('deadline_at')}"
            )

        # 9. Setup duration
        setup_sec = int(antenna.get("setup_seconds", 0))
        expected_setup_start = start_dt - timedelta(seconds=setup_sec)
        if abs((setup_start_dt - expected_setup_start).total_seconds()) > 0.001:
            conflicts.append(
                f"{prefix}: Setup start {asgn['setup_start_at']} does not match start_at - {setup_sec}s"
            )

        # 13 & 14. Allocated bytes and effective rate capacity
        allocated = asgn.get("allocated_bytes", 0)
        if allocated < 1:
            conflicts.append(f"{prefix}: Allocated bytes {allocated} must be >= 1")

        weather_factor = float(station.get("weather_capacity_factor", 1.0))
        nominal_rate = int(opp.get("predicted_rate_bps", 0))
        effective_rate = calculate_effective_rate_bps(nominal_rate, weather_factor)
        max_possible_bytes = calculate_transferable_bytes(effective_rate, comm_seconds)

        if allocated > max_possible_bytes:
            conflicts.append(
                f"{prefix}: Allocated bytes {allocated} exceeds transfer capacity {max_possible_bytes} "
                f"at rate {effective_rate} bps over {comm_seconds}s"
            )

        # Add to tracking
        if job_id not in job_allocations:
            job_allocations[job_id] = []
            job_total_bytes[job_id] = 0
        job_allocations[job_id].append(asgn)
        job_total_bytes[job_id] += allocated

        if antenna_id not in antenna_intervals:
            antenna_intervals[antenna_id] = []
        antenna_intervals[antenna_id].append((setup_start_dt, end_dt, f"new:{prefix}"))

        if sat_id not in satellite_intervals:
            satellite_intervals[sat_id] = []
        satellite_intervals[sat_id].append((start_dt, end_dt, f"new:{prefix}"))

    # 10. Antenna occupancy no-overlap check
    for ant_id, intervals in antenna_intervals.items():
        intervals.sort(key=lambda x: x[0])
        for i in range(len(intervals) - 1):
            curr_end = intervals[i][1]
            next_start = intervals[i + 1][0]
            if curr_end > next_start:
                conflicts.append(
                    f"Antenna '{ant_id}' overlap between {intervals[i][2]} (ends {curr_end.isoformat()}) "
                    f"and {intervals[i + 1][2]} (starts {next_start.isoformat()})"
                )

    # 11. Satellite concurrency check using sweep-line
    for sat_id, intervals in satellite_intervals.items():
        satellite = problem.satellites_by_id.get(sat_id)
        max_parallel = int(satellite.get("max_parallel_contacts", 1)) if satellite else 1

        # Sweep-line points
        events: list[tuple[datetime, int, str]] = []
        for s_dt, e_dt, desc in intervals:
            events.append((s_dt, 1, desc))   # Contact start (+1)
            events.append((e_dt, -1, desc))  # Contact end (-1)

        # Sort: at same time, ends (-1) before starts (+1) for half-open intervals [start, end)
        events.sort(key=lambda x: (x[0], x[1]))

        current_concurrent = 0
        for ev_dt, ev_type, desc in events:
            current_concurrent += ev_type
            if current_concurrent > max_parallel:
                conflicts.append(
                    f"Satellite '{sat_id}' concurrency limit {max_parallel} exceeded "
                    f"({current_concurrent} concurrent at {ev_dt.isoformat()})"
                )
                break

    # 12 & 15. Job concurrency and split restrictions
    for job_id, asgns in job_allocations.items():
        job = problem.jobs_by_id[job_id]
        allow_split = job.get("allow_split", False)
        newly_plannable = problem.job_newly_plannable_bytes.get(job_id, 0)
        tot_bytes = job_total_bytes[job_id]

        if tot_bytes > newly_plannable:
            conflicts.append(
                f"Job '{job_id}' total allocated bytes {tot_bytes} exceeds newly plannable {newly_plannable}"
            )

        if not allow_split:
            if len(asgns) > 1:
                conflicts.append(f"Unsplit job '{job_id}' assigned to multiple contacts ({len(asgns)})")
            elif len(asgns) == 1 and tot_bytes != newly_plannable:
                conflicts.append(
                    f"Unsplit job '{job_id}' allocated {tot_bytes} bytes instead of full remainder {newly_plannable}"
                )

        # Job communication intervals must not overlap
        comm_intervals: list[tuple[datetime, datetime]] = []
        for a in asgns:
            comm_intervals.append((parse_iso_utc(a["start_at"]), parse_iso_utc(a["end_at"])))
        comm_intervals.sort(key=lambda x: x[0])
        for i in range(len(comm_intervals) - 1):
            if comm_intervals[i][1] > comm_intervals[i + 1][0]:
                conflicts.append(f"Job '{job_id}' has overlapping communication intervals")

    is_valid = len(conflicts) == 0
    return is_valid, conflicts
