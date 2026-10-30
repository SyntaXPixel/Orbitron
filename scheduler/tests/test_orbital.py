"""Tests for orbital calculations, TLE validation, propagation, and opportunity prediction."""

from __future__ import annotations

import copy
import pytest
from datetime import datetime, timezone

from scheduler.api import predict_opportunities, propagate_satellites
from scheduler.contracts import parse_iso_utc
from scheduler.exceptions import OrbitalDataError, SchedulerInputError
from scheduler.orbital.tle import (
    compute_tle_checksum,
    parse_tle_epoch,
    validate_orbit_definition,
    validate_tle_format,
)


VALID_LINE1 = "1 25544U 98067A   26304.00000000  .00001000  00000+0  10000-3 0  9999"
VALID_LINE2 = "2 25544  51.6400 120.0000 0000478  60.0000  30.0000 15.50000000    11"


def test_tle_checksum():
    """Verify standard TLE modulo-10 checksum computation."""
    calc_c1 = compute_tle_checksum(VALID_LINE1[:68])
    assert str(calc_c1) == VALID_LINE1[68]
    calc_c2 = compute_tle_checksum(VALID_LINE2[:68])
    assert str(calc_c2) == VALID_LINE2[68]


def test_valid_tle_format():
    """Verify valid TLE line lengths and structure pass validation."""
    validate_tle_format(VALID_LINE1, VALID_LINE2, "sat-test")


@pytest.mark.parametrize(
    "l1,l2,err_substr",
    [
        (VALID_LINE1[:-1], VALID_LINE2, "must have exactly 69 characters"),
        (VALID_LINE1, VALID_LINE2 + " ", "must have exactly 69 characters"),
        ("2" + VALID_LINE1[1:], VALID_LINE2, "must start with '1 '"),
        (VALID_LINE1, "1" + VALID_LINE2[1:], "must start with '2 '"),
        (VALID_LINE1[:68] + "0", VALID_LINE2, "checksum mismatch"),
        (VALID_LINE1, VALID_LINE2[:68] + "0", "checksum mismatch"),
        (VALID_LINE1, "2 25545" + VALID_LINE2[7:68] + "2", "Satellite catalog number mismatch"),
    ],
)
def test_invalid_tle_format(l1, l2, err_substr):
    """Verify malformed or corrupted TLE lines are rejected with OrbitalDataError."""
    with pytest.raises(OrbitalDataError, match=err_substr):
        validate_tle_format(l1, l2, "sat-test")


def test_epoch_agreement_and_data_age():
    """Verify epoch parsing and tolerance checks."""
    odef = {
        "satellite_id": "sat-a",
        "format": "tle",
        "line1": VALID_LINE1,
        "line2": VALID_LINE2,
        "epoch_at": "2026-10-31T00:00:00Z",
        "orbit_source": "synthetic",
    }
    # Valid epoch agreement
    sat = validate_orbit_definition(odef)
    assert sat is not None

    # Epoch mismatch outside tolerance
    bad_epoch_def = dict(odef, epoch_at="2026-10-25T00:00:00Z")
    with pytest.raises(OrbitalDataError, match="differs from parsed TLE epoch"):
        validate_orbit_definition(bad_epoch_def, epoch_tolerance_seconds=3600.0)

    # Data age policy enforcement
    eval_time = datetime(2027, 2, 1, tzinfo=timezone.utc)
    with pytest.raises(OrbitalDataError, match="outside validity policy"):
        validate_orbit_definition(odef, at=eval_time, max_age_days=30.0)


def test_propagation_accuracy_and_stability():
    """Verify satellite propagation produces finite coordinates and deterministic results."""
    defs = [
        {
            "satellite_id": "sat-a-001",
            "format": "tle",
            "line1": VALID_LINE1,
            "line2": VALID_LINE2,
            "epoch_at": "2026-10-31T00:00:00Z",
            "orbit_source": "synthetic",
        }
    ]
    timestamp = "2026-10-31T06:00:00Z"

    pos1 = propagate_satellites(defs, timestamp)
    pos2 = propagate_satellites(defs, timestamp)

    assert len(pos1) == 1
    p1 = pos1[0]["position"]
    p2 = pos2[0]["position"]

    # Repeated calls must be perfectly stable
    assert p1["latitude_deg"] == p2["latitude_deg"]
    assert p1["longitude_deg"] == p2["longitude_deg"]
    assert p1["altitude_km"] == p2["altitude_km"]
    assert p1["observed_at"] == timestamp

    # Coordinates must be physically valid
    assert -90.0 <= p1["latitude_deg"] <= 90.0
    assert -180.0 <= p1["longitude_deg"] <= 180.0
    assert 200.0 < p1["altitude_km"] < 1000.0


def test_propagation_input_immutability():
    """Verify that propagate_satellites does not mutate its inputs."""
    defs = [
        {
            "satellite_id": "sat-a-001",
            "format": "tle",
            "line1": VALID_LINE1,
            "line2": VALID_LINE2,
            "epoch_at": "2026-10-31T00:00:00Z",
            "orbit_source": "synthetic",
        }
    ]
    defs_snapshot = copy.deepcopy(defs)
    propagate_satellites(defs, "2026-10-31T06:00:00Z")
    assert defs == defs_snapshot


def test_propagation_invalid_timestamp():
    """Verify propagate_satellites rejects malformed timestamps."""
    defs = [
        {
            "satellite_id": "sat-a-001",
            "format": "tle",
            "line1": VALID_LINE1,
            "line2": VALID_LINE2,
            "epoch_at": "2026-10-31T00:00:00Z",
            "orbit_source": "synthetic",
        }
    ]
    with pytest.raises(OrbitalDataError, match="Invalid propagation timestamp"):
        propagate_satellites(defs, "invalid-time")


def test_predict_opportunities_nominal_rate_and_clipping():
    """Verify opportunity prediction rate calculation and conservative interval clipping."""
    catalog = {
        "satellites": [
            {
                "id": "sat-1",
                "name": "Sat 1",
                "supported_bands": ["X"],
                "max_downlink_rate_bps": 12000000,
            }
        ],
        "stations": [
            {
                "id": "gs-1",
                "name": "GS 1",
                "latitude_deg": 51.5,
                "longitude_deg": 0.0,
                "min_elevation_deg": 10.0,
                "antennas": [
                    {
                        "id": "ant-1",
                        "supported_bands": ["X"],
                        "max_rate_bps": 20000000,
                        "setup_seconds": 20,
                    }
                ],
            }
        ],
        "orbit_definitions": [
            {
                "satellite_id": "sat-1",
                "format": "tle",
                "line1": VALID_LINE1,
                "line2": VALID_LINE2,
                "epoch_at": "2026-10-31T00:00:00Z",
                "orbit_source": "synthetic",
            }
        ],
    }

    horizon = {
        "from_at": "2026-10-31T12:00:00Z",
        "to_at": "2026-10-31T20:00:00Z",
    }

    opps = predict_opportunities(catalog, horizon)
    assert len(opps) > 0

    from_dt = parse_iso_utc(horizon["from_at"])
    to_dt = parse_iso_utc(horizon["to_at"])

    for opp in opps:
        # Rate must be min(sat_max, ant_max) = min(12M, 20M) = 12M
        assert opp["predicted_rate_bps"] == 12000000
        assert opp["band"] == "X"
        assert opp["satellite_id"] == "sat-1"
        assert opp["station_id"] == "gs-1"
        assert opp["antenna_id"] == "ant-1"

        # Must be strictly within horizon
        start_dt = parse_iso_utc(opp["start_at"])
        end_dt = parse_iso_utc(opp["end_at"])
        assert start_dt >= from_dt
        assert end_dt <= to_dt
        assert start_dt < end_dt
