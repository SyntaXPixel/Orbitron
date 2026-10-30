"""Compatibility filtering and rejection explanation evidence."""

from __future__ import annotations

import math
from typing import Any

from scheduler.contracts import (
    REASON_ANTENNA_BUSY,
    REASON_BAND_MISMATCH,
    REASON_DEADLINE_UNREACHABLE,
    REASON_INSUFFICIENT_CAPACITY,
    REASON_NO_VISIBLE_PASS,
    REASON_PARTNER_NOT_APPROVED,
    REASON_SETUP_CONFLICT,
    REASON_STATION_OFFLINE,
    REASON_WEATHER_DEGRADED,
    calculate_effective_rate_bps,
    make_reason,
    parse_iso_utc,
)
from scheduler.planning.normalization import NormalizedProblem


def check_job_opportunity_compatibility(
    job: dict[str, Any],
    opp: dict[str, Any],
    problem: NormalizedProblem,
) -> tuple[bool, dict[str, Any] | None, int]:
    """Check whether a job is compatible with an opportunity.

    Returns:
    (is_compatible, rejection_reason, effective_rate_bps)
    """
    job_id = job.get("id", "")
    sat_id = job.get("satellite_id", "")
    opp_sat_id = opp.get("satellite_id", "")

    # 1. Satellite match
    if sat_id != opp_sat_id:
        return False, make_reason(
            REASON_NO_VISIBLE_PASS,
            f"Opportunity satellite '{opp_sat_id}' does not match job satellite '{sat_id}'",
            [job_id, opp.get("id", "")],
        ), 0

    satellite = problem.satellites_by_id.get(sat_id)
    if not satellite:
        return False, make_reason(
            REASON_NO_VISIBLE_PASS,
            f"Satellite '{sat_id}' not found in catalogue",
            [job_id, sat_id],
        ), 0

    # 12. Satellite operational fault
    if satellite.get("operational_status") == "fault":
        return False, make_reason(
            REASON_INSUFFICIENT_CAPACITY,
            f"Satellite '{sat_id}' is in fault state",
            [job_id, sat_id],
        ), 0

    # 2. Station exists
    station_id = opp.get("station_id", "")
    station = problem.stations_by_id.get(station_id)
    if not station:
        return False, make_reason(
            REASON_STATION_OFFLINE,
            f"Station '{station_id}' not found in problem",
            [job_id, station_id],
        ), 0

    # 5. Station not offline
    if station.get("operational_status") == "offline":
        return False, make_reason(
            REASON_STATION_OFFLINE,
            f"Station '{station_id}' is offline",
            [job_id, station_id],
        ), 0

    # 3. Antenna exists and belongs to station
    antenna_id = opp.get("antenna_id", "")
    antenna = problem.antennas_by_station_and_ant_id.get((station_id, antenna_id))
    if not antenna:
        return False, make_reason(
            REASON_ANTENNA_BUSY,
            f"Antenna '{antenna_id}' not found on station '{station_id}'",
            [job_id, station_id, antenna_id],
        ), 0

    # 6. Antenna available
    if antenna.get("status") in ("maintenance", "offline"):
        return False, make_reason(
            REASON_ANTENNA_BUSY,
            f"Antenna '{antenna_id}' on station '{station_id}' status is '{antenna.get('status')}'",
            [job_id, station_id, antenna_id],
        ), 0

    # 4. Band compatibility
    band = opp.get("band", "")
    sat_bands = satellite.get("supported_bands", [])
    ant_bands = antenna.get("supported_bands", [])
    if band not in sat_bands or band not in ant_bands:
        return False, make_reason(
            REASON_BAND_MISMATCH,
            f"Band '{band}' not supported by both satellite '{sat_id}' and antenna '{antenna_id}'",
            [job_id, sat_id, antenna_id],
        ), 0

    # 7. Sharing permissions
    job_org = job.get("owner_org_id", "")
    station_org = station.get("owner_org_id", "")
    if job_org != station_org:
        sharing_enabled = station.get("sharing_enabled", False)
        approved_partners = station.get("approved_partner_org_ids", [])
        has_approved_rel = (job_org, station_id) in problem.approved_sharing_set
        if not (sharing_enabled and (job_org in approved_partners) and has_approved_rel):
            return False, make_reason(
                REASON_PARTNER_NOT_APPROVED,
                f"Partner sharing not approved for org '{job_org}' on station '{station_id}'",
                [job_id, station_id],
            ), 0

    # 8. Usable positive duration
    try:
        opp_start_dt = parse_iso_utc(opp["start_at"])
        opp_end_dt = parse_iso_utc(opp["end_at"])
    except Exception:
        return False, make_reason(
            REASON_NO_VISIBLE_PASS,
            "Invalid opportunity timestamps",
            [job_id, opp.get("id", "")],
        ), 0

    if opp_start_dt >= opp_end_dt:
        return False, make_reason(
            REASON_NO_VISIBLE_PASS,
            "Opportunity has non-positive duration",
            [job_id, opp.get("id", "")],
        ), 0

    # 9. Opportunity before deadline
    deadline_str = job.get("deadline_at", "")
    try:
        deadline_dt = parse_iso_utc(deadline_str)
    except Exception:
        deadline_dt = problem.horizon_to_dt

    if opp_start_dt >= deadline_dt:
        return False, make_reason(
            REASON_DEADLINE_UNREACHABLE,
            f"Opportunity start {opp['start_at']} is at or after job deadline {deadline_str}",
            [job_id, opp.get("id", "")],
        ), 0

    # 10. Effective rate
    weather_factor = float(station.get("weather_capacity_factor", 1.0))
    if weather_factor <= 0.0:
        return False, make_reason(
            REASON_WEATHER_DEGRADED,
            f"Station '{station_id}' has weather capacity factor {weather_factor}",
            [job_id, station_id],
        ), 0

    nominal_rate = int(opp.get("predicted_rate_bps", 0))
    effective_rate = calculate_effective_rate_bps(nominal_rate, weather_factor)
    if effective_rate <= 0:
        return False, make_reason(
            REASON_INSUFFICIENT_CAPACITY,
            f"Opportunity has zero effective transfer rate (nominal {nominal_rate} bps, factor {weather_factor})",
            [job_id, opp.get("id", "")],
        ), 0

    # 11. Required setup can fit
    setup_sec = int(antenna.get("setup_seconds", 0))
    from datetime import timedelta
    earliest_allowed_comm_start = max(opp_start_dt, problem.simulation_time_dt + timedelta(seconds=setup_sec))
    latest_allowed_comm_end = min(opp_end_dt, deadline_dt)

    min_contact_sec = problem.policy.get("minimum_contact_seconds", 1)
    if (latest_allowed_comm_end - earliest_allowed_comm_start).total_seconds() < min_contact_sec:
        return False, make_reason(
            REASON_SETUP_CONFLICT,
            f"Setup cannot fit before deadline or opportunity end for antenna '{antenna_id}'",
            [job_id, antenna_id, opp.get("id", "")],
        ), 0

    return True, None, effective_rate
