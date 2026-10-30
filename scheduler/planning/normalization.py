"""Input normalization and problem consistency validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from scheduler.contracts import (
    CONTRACT_VERSION,
    DEFAULT_ALLOW_ACTIVE_PREEMPTION,
    DEFAULT_MINIMUM_CONTACT_SECONDS,
    DEFAULT_PROTECT_ACTIVE_CONTACTS,
    DEFAULT_RANDOM_SEED,
    parse_iso_utc,
)
from scheduler.exceptions import SchedulerInputError


class NormalizedProblem:
    """Validated, normalized, and indexed planning problem."""

    def __init__(
        self,
        raw_problem: dict[str, Any],
        simulation_time_dt: datetime,
        horizon_from_dt: datetime,
        horizon_to_dt: datetime,
        policy: dict[str, Any],
        jobs_by_id: dict[str, dict[str, Any]],
        satellites_by_id: dict[str, dict[str, Any]],
        stations_by_id: dict[str, dict[str, Any]],
        antennas_by_station_and_ant_id: dict[tuple[str, str], dict[str, Any]],
        opportunities_by_id: dict[str, dict[str, Any]],
        protected_contacts: list[dict[str, Any]],
        mutable_contacts: list[dict[str, Any]],
        approved_sharing_set: set[tuple[str, str]],
        job_newly_plannable_bytes: dict[str, int],
        eligible_job_ids: list[str],
        contradictory_protected_reasons: list[str],
    ) -> None:
        self.raw_problem = raw_problem
        self.simulation_time_dt = simulation_time_dt
        self.horizon_from_dt = horizon_from_dt
        self.horizon_to_dt = horizon_to_dt
        self.policy = policy
        self.jobs_by_id = jobs_by_id
        self.satellites_by_id = satellites_by_id
        self.stations_by_id = stations_by_id
        self.antennas_by_station_and_ant_id = antennas_by_station_and_ant_id
        self.opportunities_by_id = opportunities_by_id
        self.protected_contacts = protected_contacts
        self.mutable_contacts = mutable_contacts
        self.approved_sharing_set = approved_sharing_set
        self.job_newly_plannable_bytes = job_newly_plannable_bytes
        self.eligible_job_ids = eligible_job_ids
        self.contradictory_protected_reasons = contradictory_protected_reasons


def normalize_problem(problem: dict[str, Any]) -> NormalizedProblem:
    """Validate and normalize an incoming planning problem."""
    if not isinstance(problem, dict):
        raise SchedulerInputError(f"Problem must be a dictionary, got {type(problem).__name__}")

    # Validate contract version
    contract_ver = problem.get("contract_version")
    if contract_ver != CONTRACT_VERSION:
        raise SchedulerInputError(
            f"Unsupported contract version '{contract_ver}'. Expected '{CONTRACT_VERSION}'."
        )

    # Validate simulation time
    sim_time_str = problem.get("simulation_time")
    if not sim_time_str:
        raise SchedulerInputError("Missing required 'simulation_time' in problem")
    try:
        sim_time_dt = parse_iso_utc(sim_time_str)
    except Exception as exc:
        raise SchedulerInputError(f"Invalid simulation_time format '{sim_time_str}': {exc}") from exc

    # Validate horizon
    horizon = problem.get("horizon")
    if not isinstance(horizon, dict):
        raise SchedulerInputError("Missing or invalid 'horizon' in problem")
    from_at_str = horizon.get("from_at")
    to_at_str = horizon.get("to_at")
    if not from_at_str or not to_at_str:
        raise SchedulerInputError("Horizon must contain 'from_at' and 'to_at'")
    try:
        horizon_from_dt = parse_iso_utc(from_at_str)
        horizon_to_dt = parse_iso_utc(to_at_str)
    except Exception as exc:
        raise SchedulerInputError(f"Invalid horizon format: {exc}") from exc
    if horizon_from_dt >= horizon_to_dt:
        raise SchedulerInputError("Horizon 'from_at' must be before 'to_at'")

    # Policy
    raw_policy = problem.get("policy") or {}
    if not isinstance(raw_policy, dict):
        raise SchedulerInputError("Policy must be a dictionary")
    policy = {
        "protect_active_contacts": raw_policy.get("protect_active_contacts", DEFAULT_PROTECT_ACTIVE_CONTACTS),
        "allow_active_preemption": raw_policy.get("allow_active_preemption", DEFAULT_ALLOW_ACTIVE_PREEMPTION),
        "minimum_contact_seconds": raw_policy.get("minimum_contact_seconds", DEFAULT_MINIMUM_CONTACT_SECONDS),
        "random_seed": raw_policy.get("random_seed", DEFAULT_RANDOM_SEED),
        "locked_contact_ids": set(raw_policy.get("locked_contact_ids") or []),
    }

    # Index Satellites
    satellites = problem.get("satellites", [])
    if not isinstance(satellites, list):
        raise SchedulerInputError("Satellites must be a list")
    satellites_by_id: dict[str, dict[str, Any]] = {}
    for sat in satellites:
        sat_id = sat.get("id")
        if not sat_id:
            raise SchedulerInputError(f"Satellite missing id: {sat}")
        satellites_by_id[sat_id] = sat

    # Index Stations and Antennas
    stations = problem.get("stations", [])
    if not isinstance(stations, list):
        raise SchedulerInputError("Stations must be a list")
    stations_by_id: dict[str, dict[str, Any]] = {}
    antennas_by_station_and_ant_id: dict[tuple[str, str], dict[str, Any]] = {}
    for station in stations:
        station_id = station.get("id")
        if not station_id:
            raise SchedulerInputError(f"Station missing id: {station}")
        stations_by_id[station_id] = station
        for ant in station.get("antennas", []):
            ant_id = ant.get("id")
            if ant_id:
                antennas_by_station_and_ant_id[(station_id, ant_id)] = ant

    # Index Opportunities
    opportunities = problem.get("opportunities", [])
    if not isinstance(opportunities, list):
        raise SchedulerInputError("Opportunities must be a list")
    opportunities_by_id: dict[str, dict[str, Any]] = {}
    for opp in opportunities:
        opp_id = opp.get("id")
        if not opp_id:
            raise SchedulerInputError(f"Opportunity missing id: {opp}")
        opportunities_by_id[opp_id] = opp

    # Index Jobs
    jobs = problem.get("jobs", [])
    if not isinstance(jobs, list):
        raise SchedulerInputError("Jobs must be a list")
    jobs_by_id: dict[str, dict[str, Any]] = {}
    for job in jobs:
        job_id = job.get("id")
        if not job_id:
            raise SchedulerInputError(f"Job missing id: {job}")
        jobs_by_id[job_id] = job

    # Index Approved Sharing Relationships
    approved_sharing_list = problem.get("approved_sharing_relationships", [])
    if not isinstance(approved_sharing_list, list):
        raise SchedulerInputError("Approved sharing relationships must be a list")
    approved_sharing_set: set[tuple[str, str]] = set()
    for rel in approved_sharing_list:
        if isinstance(rel, dict):
            owner_org = rel.get("owner_org_id")
            station_id = rel.get("station_id")
            if owner_org and station_id:
                approved_sharing_set.add((owner_org, station_id))

    # Existing contacts: separate protected vs mutable
    existing_contacts = problem.get("existing_contacts", [])
    if not isinstance(existing_contacts, list):
        raise SchedulerInputError("Existing contacts must be a list")

    protected_contacts: list[dict[str, Any]] = []
    mutable_contacts: list[dict[str, Any]] = []
    locked_ids = policy["locked_contact_ids"]
    protect_active = policy["protect_active_contacts"]

    for contact in existing_contacts:
        c_id = contact.get("id", "")
        status = contact.get("status", "")
        is_locked = c_id in locked_ids
        is_active_status = status in ("active", "in_progress", "communicating", "setup")

        setup_start_str = contact.get("setup_start_at")
        end_str = contact.get("end_at")
        is_in_window = False
        if setup_start_str and end_str:
            try:
                setup_dt = parse_iso_utc(setup_start_str)
                end_dt = parse_iso_utc(end_str)
                if setup_dt <= sim_time_dt < end_dt:
                    is_in_window = True
            except Exception:
                pass

        if is_locked or (protect_active and (is_active_status or is_in_window)):
            protected_contacts.append(contact)
        else:
            mutable_contacts.append(contact)

    # Validate protected contacts mutual consistency
    contradictory_reasons: list[str] = []
    # Check antenna exclusivity among protected contacts
    antenna_intervals: dict[str, list[tuple[datetime, datetime, str]]] = {}
    for c in protected_contacts:
        ant_id = c.get("antenna_id", "")
        try:
            s_dt = parse_iso_utc(c["setup_start_at"])
            e_dt = parse_iso_utc(c["end_at"])
        except Exception:
            continue
        if ant_id not in antenna_intervals:
            antenna_intervals[ant_id] = []
        antenna_intervals[ant_id].append((s_dt, e_dt, c.get("id", "")))

    for ant_id, intervals in antenna_intervals.items():
        intervals.sort(key=lambda x: x[0])
        for i in range(len(intervals) - 1):
            if intervals[i][1] > intervals[i + 1][0]:
                msg = (
                    f"Protected contacts conflict: {intervals[i][2]} and {intervals[i + 1][2]} "
                    f"overlap on antenna '{ant_id}'"
                )
                contradictory_reasons.append(msg)

    # Job newly plannable data accounting
    job_newly_plannable_bytes: dict[str, int] = {}
    job_protected_reservations: dict[str, int] = {}

    for c in protected_contacts:
        j_id = c.get("job_id", "")
        alloc = c.get("allocated_bytes", 0)
        xfer = c.get("transferred_bytes", 0)
        reserved = max(0, alloc - xfer)
        job_protected_reservations[j_id] = job_protected_reservations.get(j_id, 0) + reserved

    eligible_job_ids: list[str] = []
    for job_id, job in jobs_by_id.items():
        status = job.get("status", "")
        if status in ("completed", "cancelled"):
            continue

        remaining = job.get("remaining_bytes", 0)
        if remaining <= 0:
            continue

        reserved = job_protected_reservations.get(job_id, 0)
        if reserved > remaining:
            msg = (
                f"Job '{job_id}' has protected contact reservation {reserved} bytes "
                f"exceeding remaining {remaining} bytes"
            )
            contradictory_reasons.append(msg)
            newly_plannable = 0
        else:
            newly_plannable = remaining - reserved

        job_newly_plannable_bytes[job_id] = newly_plannable
        if newly_plannable > 0:
            eligible_job_ids.append(job_id)

    # Stable ordering of eligible jobs: priority (if useful), created_at, id
    eligible_job_ids.sort(
        key=lambda jid: (
            jobs_by_id[jid].get("created_at", ""),
            jid,
        )
    )

    return NormalizedProblem(
        raw_problem=problem,
        simulation_time_dt=sim_time_dt,
        horizon_from_dt=horizon_from_dt,
        horizon_to_dt=horizon_to_dt,
        policy=policy,
        jobs_by_id=jobs_by_id,
        satellites_by_id=satellites_by_id,
        stations_by_id=stations_by_id,
        antennas_by_station_and_ant_id=antennas_by_station_and_ant_id,
        opportunities_by_id=opportunities_by_id,
        protected_contacts=protected_contacts,
        mutable_contacts=mutable_contacts,
        approved_sharing_set=approved_sharing_set,
        job_newly_plannable_bytes=job_newly_plannable_bytes,
        eligible_job_ids=eligible_job_ids,
        contradictory_protected_reasons=contradictory_reasons,
    )
