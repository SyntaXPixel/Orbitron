"""Satellite orbital propagation using Skyfield and SGP4."""

from __future__ import annotations

import math
from typing import Any
from skyfield.api import wgs84

from scheduler.contracts import make_position, parse_iso_utc, format_iso_utc
from scheduler.exceptions import OrbitalDataError
from scheduler.orbital.cache import get_timescale
from scheduler.orbital.tle import validate_orbit_definition


def normalize_longitude(lon_deg: float) -> float:
    """Normalize longitude to [-180.0, 180.0] degrees."""
    lon = ((lon_deg + 180.0) % 360.0) - 180.0
    # Handle floating point boundary edge case
    if lon == -180.0 and lon_deg > 0:
        return 180.0
    return lon


def propagate_single_satellite(orbit_def: dict[str, Any], at_dt: Any) -> dict[str, Any]:
    """Propagate a single validated satellite definition at the given datetime."""
    sat_id = orbit_def["satellite_id"]
    satellite = validate_orbit_definition(orbit_def, at=at_dt)
    ts = get_timescale()
    t = ts.from_datetime(at_dt)

    try:
        geocentric = satellite.at(t)
        subpoint = wgs84.subpoint(geocentric)
    except Exception as exc:
        raise OrbitalDataError(f"Propagation failed for satellite '{sat_id}' at {at_dt}: {exc}") from exc

    lat = subpoint.latitude.degrees
    raw_lon = subpoint.longitude.degrees
    alt = subpoint.elevation.km

    if not (math.isfinite(lat) and math.isfinite(raw_lon) and math.isfinite(alt)):
        raise OrbitalDataError(
            f"Non-finite propagation coordinates for satellite '{sat_id}': lat={lat}, lon={raw_lon}, alt={alt}"
        )

    if not (-90.0 <= lat <= 90.0):
        raise OrbitalDataError(f"Invalid latitude {lat} for satellite '{sat_id}'")

    if alt < 80.0:
        raise OrbitalDataError(f"Satellite '{sat_id}' altitude {alt:.1f} km indicates decay or invalid orbit")

    lon = normalize_longitude(raw_lon)
    observed_at_str = format_iso_utc(at_dt)

    return {
        "satellite_id": sat_id,
        "position": make_position(lat, lon, alt, observed_at_str),
    }


def propagate_satellites(
    orbit_definitions: list[dict[str, Any]],
    at: str,
) -> list[dict[str, Any]]:
    """Propagate orbital definitions at an explicit UTC timestamp string.

    Returns a list of records matching the required contract:
    [
        {
            "satellite_id": str,
            "position": {
                "latitude_deg": float,
                "longitude_deg": float,
                "altitude_km": float,
                "observed_at": str
            }
        }
    ]
    """
    if not isinstance(orbit_definitions, list):
        raise OrbitalDataError(f"Expected list of orbital definitions, got {type(orbit_definitions).__name__}")

    try:
        at_dt = parse_iso_utc(at)
    except Exception as exc:
        raise OrbitalDataError(f"Invalid propagation timestamp '{at}': {exc}") from exc

    results: list[dict[str, Any]] = []
    seen_satellite_ids: set[str] = set()

    for idx, orbit_def in enumerate(orbit_definitions):
        if not isinstance(orbit_def, dict):
            raise OrbitalDataError(f"Orbital definition at index {idx} is not a dictionary")
        sat_id = orbit_def.get("satellite_id")
        if sat_id in seen_satellite_ids:
            raise OrbitalDataError(f"Duplicate orbital definition for satellite '{sat_id}' at index {idx}")
        if sat_id:
            seen_satellite_ids.add(sat_id)

        result = propagate_single_satellite(orbit_def, at_dt)
        results.append(result)

    return results
