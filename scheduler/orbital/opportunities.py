"""Satellite contact opportunity prediction over a planning horizon."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any
from skyfield.api import wgs84

from scheduler.contracts import (
    format_iso_utc,
    make_opportunity,
    parse_iso_utc,
    round_down_second,
    round_up_second,
)
from scheduler.exceptions import OrbitalDataError, SchedulerInputError
from scheduler.orbital.cache import get_timescale
from scheduler.orbital.tle import validate_orbit_definition


def generate_opportunity_id(
    satellite_id: str,
    station_id: str,
    antenna_id: str,
    band: str,
    start_at: str,
    end_at: str,
) -> str:
    """Generate a deterministic opportunity ID."""
    content = f"{satellite_id}:{station_id}:{antenna_id}:{band}:{start_at}:{end_at}"
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    return f"opp-{satellite_id}-{station_id}-{antenna_id}-{band}-{digest}"


def calculate_visibility_windows(
    satellite: Any,
    station_topos: Any,
    from_dt: datetime,
    to_dt: datetime,
    min_elevation_deg: float,
) -> list[tuple[datetime, datetime]]:
    """Find geometric visibility intervals [pass_start, pass_end) within horizon."""
    ts = get_timescale()
    t0 = ts.from_datetime(from_dt)
    t1 = ts.from_datetime(to_dt)

    # Check initial and final visibility
    alt0 = (satellite - station_topos).at(t0).altaz()[0].degrees
    alt1 = (satellite - station_topos).at(t1).altaz()[0].degrees
    initial_visible = alt0 >= min_elevation_deg
    final_visible = alt1 >= min_elevation_deg

    times, events = satellite.find_events(station_topos, t0, t1, altitude_degrees=min_elevation_deg)

    intervals: list[tuple[datetime, datetime]] = []
    current_pass_start: datetime | None = from_dt if initial_visible else None

    for ti, event in zip(times, events):
        event_dt = ti.utc_datetime()
        if event == 0:  # Rise
            if current_pass_start is None:
                current_pass_start = max(event_dt, from_dt)
        elif event == 2:  # Set
            if current_pass_start is not None:
                pass_end = min(event_dt, to_dt)
                if pass_end > current_pass_start:
                    intervals.append((current_pass_start, pass_end))
                current_pass_start = None
        elif event == 1:
            # Culmination event (peak elevation); pass continues
            pass

    # If pass was still open at horizon end
    if current_pass_start is not None:
        pass_end = to_dt
        if pass_end > current_pass_start:
            intervals.append((current_pass_start, pass_end))
    elif len(events) == 0 and initial_visible and final_visible:
        # No rise/set events, but visible through whole horizon
        intervals.append((from_dt, to_dt))

    # Apply clipping and conservative rounding
    rounded_intervals: list[tuple[datetime, datetime]] = []
    for start_dt, end_dt in intervals:
        clipped_start = max(start_dt, from_dt)
        clipped_end = min(end_dt, to_dt)

        r_start = round_up_second(clipped_start)
        r_end = round_down_second(clipped_end)

        if r_start < r_end:
            rounded_intervals.append((r_start, r_end))

    return rounded_intervals


def predict_opportunities(
    catalog: dict[str, Any],
    horizon: dict[str, Any],
) -> list[dict[str, Any]]:
    """Predict satellite contact opportunities for the given catalog and horizon.

    Matches frontend Opportunity interface:
    - id
    - satellite_id
    - station_id
    - antenna_id
    - band
    - start_at
    - end_at
    - predicted_rate_bps
    """
    if not isinstance(catalog, dict):
        raise SchedulerInputError(f"Catalog must be a dict, got {type(catalog).__name__}")
    if not isinstance(horizon, dict):
        raise SchedulerInputError(f"Horizon must be a dict, got {type(horizon).__name__}")

    from_at_str = horizon.get("from_at")
    to_at_str = horizon.get("to_at")
    if not from_at_str or not to_at_str:
        raise SchedulerInputError("Horizon must contain 'from_at' and 'to_at'")

    try:
        from_dt = parse_iso_utc(from_at_str)
        to_dt = parse_iso_utc(to_at_str)
    except Exception as exc:
        raise SchedulerInputError(f"Failed to parse horizon timestamps: {exc}") from exc

    if from_dt >= to_dt:
        raise SchedulerInputError(f"Horizon 'from_at' ({from_at_str}) must be earlier than 'to_at' ({to_at_str})")

    satellites = catalog.get("satellites", [])
    stations = catalog.get("stations", [])
    orbit_definitions = catalog.get("orbit_definitions", [])

    if not isinstance(satellites, list) or not isinstance(stations, list) or not isinstance(orbit_definitions, list):
        raise SchedulerInputError("Catalog 'satellites', 'stations', and 'orbit_definitions' must be lists")

    # Map satellite_id to orbit definition
    orbit_map: dict[str, dict[str, Any]] = {}
    for orbit_def in orbit_definitions:
        sat_id = orbit_def.get("satellite_id")
        if not sat_id:
            raise OrbitalDataError(f"Orbital definition missing satellite_id: {orbit_def}")
        if sat_id in orbit_map:
            raise OrbitalDataError(f"Duplicate orbital definition for satellite '{sat_id}'")
        orbit_map[sat_id] = orbit_def

    # Validate each satellite has an orbit definition and parse EarthSatellite
    sat_objects: dict[str, Any] = {}
    sat_records: dict[str, dict[str, Any]] = {}
    for sat in satellites:
        sat_id = sat.get("id")
        if not sat_id:
            raise SchedulerInputError(f"Satellite missing 'id': {sat}")
        if sat_id not in orbit_map:
            raise OrbitalDataError(f"Satellite '{sat_id}' has no matching orbital definition")
        orbit_def = orbit_map[sat_id]
        earth_satellite = validate_orbit_definition(orbit_def, at=from_dt)
        sat_objects[sat_id] = earth_satellite
        sat_records[sat_id] = sat

    opportunities: list[dict[str, Any]] = []

    for station in stations:
        station_id = station.get("id")
        if not station_id:
            raise SchedulerInputError(f"Station missing 'id': {station}")

        lat = station.get("latitude_deg")
        lon = station.get("longitude_deg")
        if lat is None or lon is None:
            raise SchedulerInputError(f"Station '{station_id}' missing latitude_deg or longitude_deg")

        min_elevation = float(station.get("min_elevation_deg", 10.0))
        elevation_m = float(station.get("elevation_m", 0.0))
        station_topos = wgs84.latlon(lat, lon, elevation_m=elevation_m)
        antennas = station.get("antennas", [])

        for sat_id, sat in sat_records.items():
            earth_sat = sat_objects[sat_id]
            intervals = calculate_visibility_windows(earth_sat, station_topos, from_dt, to_dt, min_elevation)

            for pass_start, pass_end in intervals:
                start_iso = format_iso_utc(pass_start)
                end_iso = format_iso_utc(pass_end)

                # Find compatible antennas and bands
                sat_bands = sat.get("supported_bands", [])
                max_sat_rate = sat.get("max_downlink_rate_bps", 0)

                for ant in antennas:
                    ant_id = ant.get("id")
                    if not ant_id:
                        continue
                    ant_bands = ant.get("supported_bands", [])
                    max_ant_rate = ant.get("max_rate_bps", 0)

                    common_bands = sorted([b for b in sat_bands if b in ant_bands])
                    nominal_rate = min(max_sat_rate, max_ant_rate)

                    if nominal_rate <= 0:
                        continue

                    for band in common_bands:
                        opp_id = generate_opportunity_id(
                            sat_id, station_id, ant_id, band, start_iso, end_iso
                        )
                        opp = make_opportunity(
                            opp_id=opp_id,
                            satellite_id=sat_id,
                            station_id=station_id,
                            antenna_id=ant_id,
                            band=band,
                            start_at=start_iso,
                            end_at=end_iso,
                            predicted_rate_bps=nominal_rate,
                        )
                        opportunities.append(opp)

    # Sort stably: by start_at, satellite_id, station_id, antenna_id, band
    opportunities.sort(
        key=lambda o: (
            o["start_at"],
            o["satellite_id"],
            o["station_id"],
            o["antenna_id"],
            o["band"],
            o["id"],
        )
    )

    return opportunities
