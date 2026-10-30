"""Tests for contact progress calculation, setup periods, and disruptions."""

from simulation.model.progress import ContactProgressTracker, parse_utc


def test_contact_timing_and_setup_boundaries():
    contact_data = {
        "id": "contact-test-1",
        "job_id": "job-1",
        "satellite_id": "sat-1",
        "station_id": "station-1",
        "setup_start_at": "2026-10-31T06:00:00Z",
        "start_at": "2026-10-31T06:05:00Z",
        "end_at": "2026-10-31T06:15:00Z",
        "allocated_bytes": 100_000_000,
        "expected_rate_bps": 100_000_000,
        "transferred_bytes": 0,
    }
    tracker = ContactProgressTracker(contact_data)

    # 1. During setup period [06:00, 06:04) -> 0 bytes transferred
    bytes_setup, is_final = tracker.calculate_tick_progress(
        tick_start=parse_utc("2026-10-31T06:00:00Z"),
        tick_end=parse_utc("2026-10-31T06:04:00Z"),
        contact_status="confirmed",
        has_allowed_authorization=True,
        station_is_operational=True,
        satellite_is_operational=True,
    )
    assert bytes_setup == 0
    assert is_final is False
    assert tracker.cumulative_transferred_bytes == 0

    # 2. Inside executable contact interval [06:05, 06:06) -> 1 minute of transmission
    # Rate: 100 Mbps = 12.5 MB/s -> 60s = 750,000,000 bits = 93,750,000 bytes (bounded by 100MB alloc)
    bytes_contact, is_final = tracker.calculate_tick_progress(
        tick_start=parse_utc("2026-10-31T06:05:00Z"),
        tick_end=parse_utc("2026-10-31T06:05:05Z"),  # 5 seconds
        contact_status="confirmed",
        has_allowed_authorization=True,
        station_is_operational=True,
        satellite_is_operational=True,
    )
    # 100,000,000 bps * 5s / 8 = 62,500,000 bytes
    assert bytes_contact == 62_500_000
    assert tracker.cumulative_transferred_bytes == 62_500_000
    assert is_final is False

    # 3. Next tick completes the allocation (100MB cap)
    bytes_finish, is_final = tracker.calculate_tick_progress(
        tick_start=parse_utc("2026-10-31T06:05:05Z"),
        tick_end=parse_utc("2026-10-31T06:05:10Z"),  # 5 seconds would yield 62.5MB, but only 37.5MB left
        contact_status="confirmed",
        has_allowed_authorization=True,
        station_is_operational=True,
        satellite_is_operational=True,
    )
    assert bytes_finish == 37_500_000
    assert tracker.cumulative_transferred_bytes == 100_000_000
    assert is_final is True


def test_contact_blocked_by_authorization_or_outage():
    contact_data = {
        "id": "contact-test-2",
        "job_id": "job-2",
        "satellite_id": "sat-2",
        "station_id": "station-2",
        "start_at": "2026-10-31T06:00:00Z",
        "end_at": "2026-10-31T06:10:00Z",
        "allocated_bytes": 50_000_000,
        "expected_rate_bps": 100_000_000,
    }
    tracker = ContactProgressTracker(contact_data)

    # Missing authorization blocks execution
    b_no_auth, _ = tracker.calculate_tick_progress(
        tick_start=parse_utc("2026-10-31T06:01:00Z"),
        tick_end=parse_utc("2026-10-31T06:02:00Z"),
        contact_status="confirmed",
        has_allowed_authorization=False,
        station_is_operational=True,
        satellite_is_operational=True,
    )
    assert b_no_auth == 0

    # Station outage blocks execution
    b_outage, _ = tracker.calculate_tick_progress(
        tick_start=parse_utc("2026-10-31T06:01:00Z"),
        tick_end=parse_utc("2026-10-31T06:02:00Z"),
        contact_status="confirmed",
        has_allowed_authorization=True,
        station_is_operational=False,
        satellite_is_operational=True,
    )
    assert b_outage == 0


def test_contact_rain_capacity_reduction():
    contact_data = {
        "id": "contact-test-rain",
        "job_id": "job-3",
        "satellite_id": "sat-3",
        "station_id": "station-3",
        "start_at": "2026-10-31T06:00:00Z",
        "end_at": "2026-10-31T06:10:00Z",
        "allocated_bytes": 100_000_000,
        "expected_rate_bps": 80_000_000,  # 10 MB/s
    }
    tracker = ContactProgressTracker(contact_data)

    # 1 second with 50% rain factor (capacity factor = 0.5)
    # Expected: 80 Mbps * 0.5 = 40 Mbps = 5,000,000 bytes
    b_rain, _ = tracker.calculate_tick_progress(
        tick_start=parse_utc("2026-10-31T06:00:00Z"),
        tick_end=parse_utc("2026-10-31T06:00:01Z"),
        contact_status="confirmed",
        has_allowed_authorization=True,
        station_is_operational=True,
        satellite_is_operational=True,
        weather_capacity_factor=0.5,
    )
    assert b_rain == 5_000_000
