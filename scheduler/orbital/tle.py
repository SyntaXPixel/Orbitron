"""TLE validation, parsing, checksum verification, and epoch policy checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from skyfield.api import EarthSatellite

from scheduler.contracts import DEFAULT_MAX_ORBITAL_AGE_DAYS, parse_iso_utc
from scheduler.exceptions import OrbitalDataError
from scheduler.orbital.cache import get_cached_satellite, get_timescale


def compute_tle_checksum(line_prefix: str) -> int:
    """Compute the standard modulo 10 checksum for a 68-character TLE line prefix."""
    s = sum(int(c) if c.isdigit() else (1 if c == "-" else 0) for c in line_prefix[:68])
    return s % 10


def parse_tle_epoch(line1: str) -> datetime:
    """Extract UTC epoch datetime from TLE Line 1 (columns 19-32)."""
    try:
        epoch_year_str = line1[18:20].strip()
        epoch_day_str = line1[20:32].strip()

        yr_2digit = int(epoch_year_str)
        # Standard NORAD convention: >= 57 -> 1900s, < 57 -> 2000s
        year = 1900 + yr_2digit if yr_2digit >= 57 else 2000 + yr_2digit
        day_of_year = float(epoch_day_str)

        # January 1st of year + (day_of_year - 1) days
        epoch_dt = datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day_of_year - 1.0)
        return epoch_dt
    except Exception as exc:
        raise OrbitalDataError(f"Failed to parse epoch from TLE line 1: {exc}") from exc


def validate_tle_format(line1: str, line2: str, satellite_id: str = "") -> None:
    """Validate format, line lengths, identifiers, and checksums for TLE lines."""
    if not isinstance(line1, str) or not isinstance(line2, str):
        raise OrbitalDataError(
            f"TLE lines must be strings for satellite '{satellite_id}', got "
            f"{type(line1).__name__} and {type(line2).__name__}"
        )

    l1 = line1.rstrip("\r\n")
    l2 = line2.rstrip("\r\n")

    if len(l1) != 69:
        raise OrbitalDataError(
            f"TLE line 1 for satellite '{satellite_id}' must have exactly 69 characters, got {len(l1)}"
        )
    if len(l2) != 69:
        raise OrbitalDataError(
            f"TLE line 2 for satellite '{satellite_id}' must have exactly 69 characters, got {len(l2)}"
        )

    if not l1.startswith("1 "):
        raise OrbitalDataError(
            f"TLE line 1 for satellite '{satellite_id}' must start with '1 ', got '{l1[:2]}'"
        )
    if not l2.startswith("2 "):
        raise OrbitalDataError(
            f"TLE line 2 for satellite '{satellite_id}' must start with '2 ', got '{l2[:2]}'"
        )

    # Checksum validation
    expected_c1 = compute_tle_checksum(l1[:68])
    if not l1[68].isdigit() or int(l1[68]) != expected_c1:
        raise OrbitalDataError(
            f"TLE line 1 checksum mismatch for satellite '{satellite_id}': expected {expected_c1}, got {l1[68]}"
        )

    expected_c2 = compute_tle_checksum(l2[:68])
    if not l2[68].isdigit() or int(l2[68]) != expected_c2:
        raise OrbitalDataError(
            f"TLE line 2 checksum mismatch for satellite '{satellite_id}': expected {expected_c2}, got {l2[68]}"
        )

    # Satellite catalog number agreement between line 1 and line 2 (cols 3-7)
    sat_num_l1 = l1[2:7].strip()
    sat_num_l2 = l2[2:7].strip()
    if sat_num_l1 != sat_num_l2:
        raise OrbitalDataError(
            f"Satellite catalog number mismatch between TLE lines for '{satellite_id}': "
            f"'{sat_num_l1}' != '{sat_num_l2}'"
        )


def validate_orbit_definition(
    orbit_def: dict[str, Any],
    at: datetime | None = None,
    max_age_days: float = DEFAULT_MAX_ORBITAL_AGE_DAYS,
    epoch_tolerance_seconds: float = 86400.0,
) -> EarthSatellite:
    """Validate orbital definition record and return an offline Skyfield EarthSatellite object.

    Enforces:
    - Required fields (satellite_id, format, line1, line2, epoch_at, orbit_source).
    - format == 'tle'.
    - orbit_source in ['public_tle', 'synthetic'].
    - TLE syntax, lengths, checksums.
    - Agreement between TLE epoch and supplied epoch_at within tolerance.
    - Data age within configured policy if evaluation time 'at' is provided.
    """
    if not isinstance(orbit_def, dict):
        raise OrbitalDataError(f"Orbital definition must be a dict, got {type(orbit_def).__name__}")

    sat_id = orbit_def.get("satellite_id")
    if not sat_id or not isinstance(sat_id, str):
        raise OrbitalDataError(f"Missing or invalid 'satellite_id' in orbital definition: {orbit_def}")

    fmt = orbit_def.get("format")
    if fmt != "tle":
        raise OrbitalDataError(f"Unsupported orbital definition format '{fmt}' for satellite '{sat_id}'. Expected 'tle'.")

    orbit_source = orbit_def.get("orbit_source")
    if orbit_source not in ("public_tle", "synthetic"):
        raise OrbitalDataError(
            f"Invalid orbit_source '{orbit_source}' for satellite '{sat_id}'. "
            f"Allowed: 'public_tle', 'synthetic'."
        )

    line1 = orbit_def.get("line1")
    line2 = orbit_def.get("line2")
    if not line1 or not line2:
        raise OrbitalDataError(f"Missing line1 or line2 in orbital definition for satellite '{sat_id}'")

    validate_tle_format(line1, line2, sat_id)

    # Check epoch_at consistency
    epoch_at_str = orbit_def.get("epoch_at")
    if not epoch_at_str:
        raise OrbitalDataError(f"Missing 'epoch_at' in orbital definition for satellite '{sat_id}'")

    try:
        declared_epoch = parse_iso_utc(epoch_at_str)
    except Exception as exc:
        raise OrbitalDataError(f"Invalid epoch_at format '{epoch_at_str}' for satellite '{sat_id}': {exc}") from exc

    parsed_epoch = parse_tle_epoch(line1)
    diff_sec = abs((declared_epoch - parsed_epoch).total_seconds())
    if diff_sec > epoch_tolerance_seconds:
        raise OrbitalDataError(
            f"Declared epoch '{epoch_at_str}' differs from parsed TLE epoch "
            f"'{parsed_epoch.isoformat()}' by {diff_sec:.1f}s (tolerance: {epoch_tolerance_seconds}s) "
            f"for satellite '{sat_id}'"
        )

    # Check data age policy
    if at is not None:
        age_days = abs((at - declared_epoch).total_seconds()) / 86400.0
        if age_days > max_age_days:
            raise OrbitalDataError(
                f"Orbital data for satellite '{sat_id}' is outside validity policy: "
                f"age is {age_days:.1f} days (max allowed: {max_age_days} days) relative to requested time"
            )

    try:
        satellite = get_cached_satellite(sat_id, line1, line2)
        return satellite
    except Exception as exc:
        raise OrbitalDataError(f"Skyfield failed to initialize satellite '{sat_id}': {exc}") from exc
