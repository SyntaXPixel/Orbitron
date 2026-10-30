"""Suite of standard and disruptive test scenarios.

Implements all 16 scenario profiles specified in simulation/plan.md Section 24.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List


def generate_scenario(
    scenario_id: str,
    name: str,
    num_satellites: int = 10,
    num_stations: int = 3,
    seed: int = 42,
    events: List[Dict[str, Any]] = None,
    custom_jobs: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate a valid scenario definition."""
    orgs = [
        {"id": "org-a", "name": "Alpha Constellations", "slug": "alpha"},
        {"id": "org-b", "name": "Beta Ground Networks", "slug": "beta"},
    ]

    satellites = []
    orbit_definitions = []
    for i in range(1, num_satellites + 1):
        org_id = "org-a" if i % 2 == 1 else "org-b"
        sat_id = f"sat-{org_id[-1]}-{i:03d}"
        satellites.append({
            "id": sat_id,
            "owner_org_id": org_id,
            "name": f"Orbiter {i}",
            "bands": ["X", "Ka"] if i % 2 == 1 else ["S", "X"],
            "max_downlink_rate_bps": 300_000_000,
            "source": "simulated",
            "generation_rate_bytes_per_second": 1_000_000,
        })
        # Synthetic TLE definition
        orbit_definitions.append({
            "satellite_id": sat_id,
            "format": "tle",
            "line1": f"1 {25540 + i:05d}U 98067A   26304.25000000  .00016717  00000-0  10270-3 0  9001",
            "line2": f"2 {25540 + i:05d}  51.6400 {(i * 30.0) % 360:08.4f} 0006703 130.5360 325.0288 15.72125391563537",
            "epoch_at": "2026-10-31T00:00:00Z",
            "orbit_source": "synthetic",
        })

    stations = []
    for s in range(1, num_stations + 1):
        st_id = f"station-{s:02d}"
        owner_id = "org-b" if s % 2 == 0 else "org-a"
        stations.append({
            "id": st_id,
            "owner_org_id": owner_id,
            "name": f"Ground Station {s}",
            "latitude_deg": -30.0 + (s * 20.0),
            "longitude_deg": -100.0 + (s * 35.0),
            "altitude_m": 150.0,
            "operational_status": "operational",
            "antennas": [
                {
                    "id": f"{st_id}-ant-1",
                    "station_id": st_id,
                    "bands": ["S", "X", "Ka"],
                    "max_rate_bps": 400_000_000,
                    "operational_status": "operational",
                }
            ],
        })

    # Default initial opportunities
    opportunities = []
    for sat in satellites:
        for st in stations:
            opp_id = f"opp-{sat['id']}-{st['id']}"
            opportunities.append({
                "id": opp_id,
                "satellite_id": sat["id"],
                "station_id": st["id"],
                "antenna_id": f"{st['id']}-ant-1",
                "start_at": "2026-10-31T06:15:00Z",
                "end_at": "2026-10-31T06:25:00Z",
                "expected_rate_bps": 200_000_000,
            })

    # Default jobs
    jobs = custom_jobs or [
        {
            "id": f"job-{sat['id']}-01",
            "satellite_id": sat["id"],
            "owner_org_id": sat["owner_org_id"],
            "data_bytes": 500_000_000,
            "deadline_at": "2026-10-31T07:30:00Z",
            "priority": "routine" if i % 3 != 0 else "emergency",
            "allow_split": True,
            "created_at": "2026-10-31T06:00:00Z",
        }
        for i, sat in enumerate(satellites)
    ]

    return {
        "id": scenario_id,
        "name": name,
        "seed": seed,
        "start_at": "2026-10-31T06:00:00Z",
        "end_at": "2026-10-31T12:00:00Z",
        "catalog": {
            "organizations": orgs,
            "satellites": satellites,
            "stations": stations,
            "orbit_definitions": orbit_definitions,
        },
        "opportunities": opportunities,
        "initial_jobs": jobs,
        "events": events or [],
        "policy": {
            "protect_active_contacts": True,
            "allow_active_preemption": False,
        },
    }


def get_default_scenario() -> Dict[str, Any]:
    """Default baseline scenario: 10 satellites, 3 stations, 2 organisations."""
    return generate_scenario("scenario-default", "Default Operations Fleet", num_satellites=10, num_stations=3)


def get_scale_scenario() -> Dict[str, Any]:
    """Scale scenario: 120 satellites, 12 stations."""
    return generate_scenario("scenario-scale-120", "Large Scale Fleet (120 Satellites)", num_satellites=120, num_stations=12)


def get_rain_scenario() -> Dict[str, Any]:
    """Rain disruption scenario reducing capacity."""
    events = [
        {
            "at": "2026-10-31T06:10:00Z",
            "type": "rain",
            "payload": {"station_id": "station-01", "capacity_factor": 0.4},
        }
    ]
    return generate_scenario("scenario-rain", "Rain Capacity Disruption", num_satellites=10, num_stations=3, events=events)


def get_outage_scenario() -> Dict[str, Any]:
    """Station outage and recovery scenario."""
    events = [
        {
            "at": "2026-10-31T06:12:00Z",
            "type": "station_outage",
            "payload": {"station_id": "station-02"},
        },
        {
            "at": "2026-10-31T06:45:00Z",
            "type": "station_recovery",
            "payload": {"station_id": "station-02"},
        },
    ]
    return generate_scenario("scenario-outage", "Station Outage and Recovery", num_satellites=10, num_stations=3, events=events)


def get_emergency_job_scenario() -> Dict[str, Any]:
    """Scenario with emergency request arrival."""
    events = [
        {
            "at": "2026-10-31T06:05:00Z",
            "type": "job_arrival",
            "payload": {
                "job": {
                    "id": "job-emergency-999",
                    "satellite_id": "sat-a-001",
                    "owner_org_id": "org-a",
                    "data_bytes": 300_000_000,
                    "deadline_at": "2026-10-31T06:20:00Z",
                    "priority": "emergency",
                    "allow_split": False,
                    "created_at": "2026-10-31T06:05:00Z",
                }
            },
        }
    ]
    return generate_scenario("scenario-emergency", "Emergency Priority Arrival", num_satellites=10, num_stations=3, events=events)
