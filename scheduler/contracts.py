"""Shared contracts, types, constants, and time/unit helpers for Orbitron scheduler."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

CONTRACT_VERSION = "orbitron.v1"

# Reason codes defined by Orbitron specifications
REASON_NO_VISIBLE_PASS = "NO_VISIBLE_PASS"
REASON_BAND_MISMATCH = "BAND_MISMATCH"
REASON_STATION_OFFLINE = "STATION_OFFLINE"
REASON_ANTENNA_BUSY = "ANTENNA_BUSY"
REASON_SETUP_CONFLICT = "SETUP_CONFLICT"
REASON_DEADLINE_UNREACHABLE = "DEADLINE_UNREACHABLE"
REASON_INSUFFICIENT_CAPACITY = "INSUFFICIENT_CAPACITY"
REASON_PARTNER_NOT_APPROVED = "PARTNER_NOT_APPROVED"
REASON_AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
REASON_ACTIVE_CONTACT_PROTECTED = "ACTIVE_CONTACT_PROTECTED"
REASON_PARTIAL_DELIVERY = "PARTIAL_DELIVERY"
REASON_WEATHER_DEGRADED = "WEATHER_DEGRADED"
REASON_EMERGENCY_REPLAN = "EMERGENCY_REPLAN"
REASON_SCHEDULER_UNAVAILABLE = "SCHEDULER_UNAVAILABLE"
REASON_STALE_SCHEDULE = "STALE_SCHEDULE"

# Supported algorithms
ALGORITHM_FIFO = "fifo"
ALGORITHM_OPTIMIZED = "optimized"
SUPPORTED_ALGORITHMS = {ALGORITHM_FIFO, ALGORITHM_OPTIMIZED}

# Solve result statuses
STATUS_FEASIBLE = "feasible"
STATUS_INFEASIBLE = "infeasible"
STATUS_UNAVAILABLE = "unavailable"
SUPPORTED_RESULT_STATUSES = {STATUS_FEASIBLE, STATUS_INFEASIBLE, STATUS_UNAVAILABLE}

# Priority levels
PRIORITY_EMERGENCY = "emergency"
PRIORITY_HIGH = "high"
PRIORITY_ROUTINE = "routine"
PRIORITY_ORDER = [PRIORITY_EMERGENCY, PRIORITY_HIGH, PRIORITY_ROUTINE]
PRIORITY_WEIGHTS = {
    PRIORITY_EMERGENCY: 3,
    PRIORITY_HIGH: 2,
    PRIORITY_ROUTINE: 1,
}

# Policy defaults
DEFAULT_PROTECT_ACTIVE_CONTACTS = True
DEFAULT_ALLOW_ACTIVE_PREEMPTION = False
DEFAULT_MINIMUM_CONTACT_SECONDS = 1
DEFAULT_RANDOM_SEED = 42
DEFAULT_MAX_ORBITAL_AGE_DAYS = 30.0


# ---------------------------------------------------------------------------
# Time formatting and conversion utilities
# ---------------------------------------------------------------------------

def parse_iso_utc(value: str) -> datetime:
    """Parse an ISO 8601 UTC timestamp string ending with Z into a timezone-aware UTC datetime."""
    if not isinstance(value, str):
        raise ValueError(f"Expected ISO timestamp string, got {type(value).__name__}: {value}")
    val = value.strip()
    if val.endswith("Z") or val.endswith("z"):
        val = val[:-1] + "+00:00"
    dt = datetime.fromisoformat(val)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def format_iso_utc(dt: datetime) -> str:
    """Format a timezone-aware UTC datetime as an ISO 8601 string ending with Z."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def round_up_second(dt: datetime) -> datetime:
    """Conservatively round upward to the nearest integer second."""
    if dt.microsecond > 0:
        return dt.replace(microsecond=0) + datetime.resolution * 1000000
    return dt


def round_down_second(dt: datetime) -> datetime:
    """Conservatively round downward to the nearest integer second."""
    return dt.replace(microsecond=0)


def to_integer_seconds(dt: datetime, origin: datetime) -> int:
    """Convert datetime to integer seconds relative to planning origin."""
    return int((dt - origin).total_seconds())


def from_integer_seconds(sec: int, origin: datetime) -> datetime:
    """Convert integer seconds relative to planning origin back to UTC datetime."""
    from datetime import timedelta
    return origin + timedelta(seconds=sec)


# ---------------------------------------------------------------------------
# Unit and capacity calculations
# ---------------------------------------------------------------------------

def calculate_transferable_bytes(rate_bps: int, duration_seconds: int) -> int:
    """Calculate maximum bytes transferable in duration at rate.

    transferable_bytes = floor(rate_bps * duration_seconds / 8)
    """
    if rate_bps <= 0 or duration_seconds <= 0:
        return 0
    return math.floor(rate_bps * duration_seconds / 8)


def calculate_required_duration_seconds(bytes_to_transfer: int, rate_bps: int) -> int:
    """Calculate required duration in integer seconds to transfer bytes at rate.

    duration_seconds = ceil(8 * allocated_bytes / rate_bps)
    """
    if bytes_to_transfer <= 0:
        return 0
    if rate_bps <= 0:
        raise ValueError("Cannot calculate duration for non-positive rate")
    return math.ceil(8 * bytes_to_transfer / rate_bps)


def calculate_effective_rate_bps(nominal_rate_bps: int, weather_capacity_factor: float) -> int:
    """Calculate effective rate considering station weather capacity factor.

    effective_rate_bps = floor(nominal_opportunity_rate_bps * weather_factor)
    """
    if nominal_rate_bps <= 0 or weather_capacity_factor <= 0.0:
        return 0
    return math.floor(nominal_rate_bps * weather_capacity_factor)


# ---------------------------------------------------------------------------
# Record constructor helpers
# ---------------------------------------------------------------------------

def make_reason(code: str, message: str, resource_ids: list[str] | None = None) -> dict[str, Any]:
    """Construct a JSON-compatible Reason object."""
    return {
        "code": code,
        "message": message,
        "resource_ids": sorted(resource_ids or []),
    }


def make_position(lat_deg: float, lon_deg: float, alt_km: float, observed_at: str) -> dict[str, Any]:
    """Construct a JSON-compatible Position object."""
    return {
        "latitude_deg": round(lat_deg, 6),
        "longitude_deg": round(lon_deg, 6),
        "altitude_km": round(alt_km, 3),
        "observed_at": observed_at,
    }


def make_opportunity(
    opp_id: str,
    satellite_id: str,
    station_id: str,
    antenna_id: str,
    band: str,
    start_at: str,
    end_at: str,
    predicted_rate_bps: int,
) -> dict[str, Any]:
    """Construct a JSON-compatible Opportunity object."""
    return {
        "id": opp_id,
        "satellite_id": satellite_id,
        "station_id": station_id,
        "antenna_id": antenna_id,
        "band": band,
        "start_at": start_at,
        "end_at": end_at,
        "predicted_rate_bps": predicted_rate_bps,
    }


def make_assignment(
    job_id: str,
    satellite_id: str,
    station_id: str,
    antenna_id: str,
    opportunity_id: str,
    band: str,
    setup_start_at: str,
    start_at: str,
    end_at: str,
    expected_rate_bps: int,
    allocated_bytes: int,
    reasons: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Construct a JSON-compatible Assignment object."""
    return {
        "job_id": job_id,
        "satellite_id": satellite_id,
        "station_id": station_id,
        "antenna_id": antenna_id,
        "opportunity_id": opportunity_id,
        "band": band,
        "setup_start_at": setup_start_at,
        "start_at": start_at,
        "end_at": end_at,
        "expected_rate_bps": expected_rate_bps,
        "allocated_bytes": allocated_bytes,
        "reasons": reasons or [],
    }


def make_unassigned_job(job_id: str, reasons: list[dict[str, Any]]) -> dict[str, Any]:
    """Construct a JSON-compatible UnassignedJob object."""
    return {
        "job_id": job_id,
        "reasons": reasons,
    }
