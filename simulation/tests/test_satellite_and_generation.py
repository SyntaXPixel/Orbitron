"""Tests for satellite data generation and automatic downlink requests."""

from simulation.actors.satellite import SatelliteProfile, VirtualSatelliteActor
from simulation.model.generation import SatelliteDataGenerator, SatelliteGenerationProfile


def test_fractional_credit_data_generation():
    # 10 bytes per second -> 0.1s gives 1 byte, 0.05s gives 0.5 byte (accumulated across ticks)
    gen = SatelliteDataGenerator(
        satellite_id="sat-test",
        profile=SatelliteGenerationProfile(generation_rate_bytes_per_second=10),
    )

    # 0.05s elapsed -> 0.5 byte -> 0 integer bytes, 0.5 fractional credit
    b1 = gen.advance(0.05)
    assert b1 == 0
    assert gen.generated_bytes_total == 0

    # Another 0.05s elapsed -> 0.5 byte + 0.5 credit = 1.0 -> 1 integer byte
    b2 = gen.advance(0.05)
    assert b2 == 1
    assert gen.generated_bytes_total == 1


def test_comms_fault_behavior():
    # Continues during comms fault
    gen_continue = SatelliteDataGenerator(
        satellite_id="sat-c",
        profile=SatelliteGenerationProfile(generation_rate_bytes_per_second=1000, continues_during_comms_fault=True),
    )
    b_cont = gen_continue.advance(1.0, in_comms_fault=True)
    assert b_cont == 1000

    # Stops during comms fault
    gen_stop = SatelliteDataGenerator(
        satellite_id="sat-s",
        profile=SatelliteGenerationProfile(generation_rate_bytes_per_second=1000, continues_during_comms_fault=False),
    )
    b_stop = gen_stop.advance(1.0, in_comms_fault=True)
    assert b_stop == 0


def test_automatic_downlink_request_evaluation():
    sat = VirtualSatelliteActor(
        satellite_id="sat-auto-01",
        owner_org_id="org-a",
        profile=SatelliteProfile(
            automatic_requests_enabled=True,
            request_threshold_bytes=100_000_000,
            maximum_request_bytes=500_000_000,
        ),
    )

    # 1. Backlog below threshold -> no request
    req = sat.evaluate_downlink_request(
        onboard_bytes=50_000_000,
        existing_jobs=[],
        simulation_time_iso="2026-10-31T06:00:00Z",
    )
    assert req is None

    # 2. Backlog above threshold -> request created
    req2 = sat.evaluate_downlink_request(
        onboard_bytes=200_000_000,
        existing_jobs=[],
        simulation_time_iso="2026-10-31T06:00:00Z",
    )
    assert req2 is not None
    assert req2.satellite_id == "sat-auto-01"
    assert req2.data_bytes == 200_000_000

    # 3. Existing uncompleted jobs reserve backlog -> no duplicate request
    existing_jobs = [
        {"satellite_id": "sat-auto-01", "status": "pending", "remaining_bytes": 150_000_000}
    ]
    # Remaining unreserved backlog is 200MB - 150MB = 50MB < 100MB threshold
    req3 = sat.evaluate_downlink_request(
        onboard_bytes=200_000_000,
        existing_jobs=existing_jobs,
        simulation_time_iso="2026-10-31T06:00:00Z",
    )
    assert req3 is None
