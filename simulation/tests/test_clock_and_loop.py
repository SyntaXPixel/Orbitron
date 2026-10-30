"""Tests for simulation clock, atomic ticks, and controller loop."""

import pytest
from datetime import datetime, timezone
from simulation.controller.clock import SimulationClock, parse_utc
from simulation.controller.loop import FleetController
from simulation.contracts import ServiceCommand


def test_clock_pause_resume_and_step():
    clock = SimulationClock(
        initial_simulation_time="2026-10-31T06:00:00Z",
        speed_multiplier=1.0,
        default_tick_seconds=1.0,
        max_tick_seconds=60.0,
    )

    # Initial state is paused
    assert clock.is_paused is True
    prev, next_time, elapsed = clock.calculate_next_tick()
    assert elapsed == 0.0
    assert prev == next_time == "2026-10-31T06:00:00Z"

    # 60-second step
    clock.start_step(60.0)
    assert clock.is_stepping is True
    assert clock.is_paused is False

    # Perform step tick (clock default tick is 1.0, so advances step until completed)
    total_elapsed = 0.0
    while clock.is_stepping:
        prev, next_time, el = clock.calculate_next_tick()
        total_elapsed += el
        clock.commit_advance(next_time)

    assert total_elapsed == 60.0
    assert clock.simulation_time == parse_utc("2026-10-31T06:01:00Z")
    assert clock.is_paused is True  # Remained paused after step completes

    # Resume
    clock.resume()
    assert clock.is_paused is False
    prev, next_time, el = clock.calculate_next_tick()
    assert el > 0.0
    clock.commit_advance(next_time)
    assert clock.simulation_time > parse_utc("2026-10-31T06:01:00Z")


def test_clock_monotonicity_and_step_bounds():
    clock = SimulationClock(initial_simulation_time="2026-10-31T06:00:00Z")
    with pytest.raises(Exception):
        # Step greater than 60 seconds rejected
        clock.start_step(61.0)

    with pytest.raises(Exception):
        # Negative step rejected
        clock.start_step(-1.0)


def test_controller_tick_generation_and_monotonicity(test_config, default_scenario):
    controller = FleetController(config=test_config)
    controller.load_catalog(default_scenario["catalog"], scenario_id=default_scenario["id"])

    assert len(controller.satellites) == 10
    assert len(controller.gateways) == 3

    # Unpause controller clock
    controller.clock.resume()

    # Tick 1
    tick1 = controller.execute_tick()
    assert tick1 is not None
    assert tick1.simulation_time == "2026-10-31T06:00:01Z"
    assert len(tick1.telemetry) == 10
    assert len(tick1.station_heartbeats) == 3

    counters_tick1 = {t.satellite_id: t.generated_bytes_total for t in tick1.telemetry}
    for sat_id, count in counters_tick1.items():
        assert count > 0

    # Tick 2
    tick2 = controller.execute_tick()
    assert tick2 is not None
    assert tick2.simulation_time == "2026-10-31T06:00:02Z"

    # Verify monotonic generation counters
    for t in tick2.telemetry:
        assert t.generated_bytes_total >= counters_tick1[t.satellite_id]


def test_controller_commands_dispatch(test_config, default_scenario):
    controller = FleetController(config=test_config)
    controller.load_catalog(default_scenario["catalog"], scenario_id="scenario-cmd-test")

    # 1. Step command
    step_cmd = ServiceCommand(
        id="cmd-1",
        scenario_id="scenario-cmd-test",
        kind="step",
        payload={"step_seconds": 60},
        created_at="2026-10-31T06:00:00Z",
    )
    ack_step = controller.dispatcher.dispatch(step_cmd)
    assert ack_step.status == "completed"

    # 2. Pause command
    pause_cmd = ServiceCommand(
        id="cmd-2",
        scenario_id="scenario-cmd-test",
        kind="pause",
        payload={},
        created_at="2026-10-31T06:01:00Z",
    )
    ack_pause = controller.dispatcher.dispatch(pause_cmd)
    assert ack_pause.status == "completed"
    assert controller.clock.is_paused is True

    # 3. Reset command
    reset_cmd = ServiceCommand(
        id="cmd-3",
        scenario_id="scenario-cmd-test",
        kind="reset",
        payload={"new_scenario_id": "scenario-cmd-test-gen2"},
        created_at="2026-10-31T06:01:00Z",
    )
    ack_reset = controller.dispatcher.dispatch(reset_cmd)
    assert ack_reset.status == "completed"
    assert controller.scenario_id == "scenario-cmd-test-gen2"

