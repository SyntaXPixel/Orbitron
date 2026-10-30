"""Tests for 120-satellite scale workload."""

import time
from simulation.controller.loop import FleetController
from simulation.fixtures.scenarios.suite import get_scale_scenario
from simulation.replay.engine import replay_scenario


def test_120_satellite_scale_simulation(test_config, scale_scenario):
    controller = FleetController(config=test_config)
    controller.load_catalog(scale_scenario["catalog"], scenario_id=scale_scenario["id"])

    assert len(controller.satellites) == 120
    assert len(controller.gateways) == 12

    controller.clock.resume()

    t_start = time.monotonic()
    tick = controller.execute_tick()
    t_elapsed = time.monotonic() - t_start

    assert tick is not None
    assert len(tick.telemetry) == 120
    assert len(tick.station_heartbeats) == 12

    # Verification: 120 satellites should execute well within 1 second locally
    assert t_elapsed < 1.0


def test_120_satellite_replay(scale_scenario):
    res = replay_scenario(scale_scenario, algorithm="fifo")
    assert res["algorithm"] == "fifo"
    assert res["metrics"]["total_jobs"] == 120
    assert res["metrics"]["resource_conflicts"] == 0

