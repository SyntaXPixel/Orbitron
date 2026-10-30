"""Tests for offline scenario evaluation replay and public SchedulerMetrics."""

import pytest
from simulation.api import replay_scenario
from simulation.fixtures.scenarios.suite import (
    get_default_scenario,
    get_emergency_job_scenario,
    get_outage_scenario,
    get_rain_scenario,
)


def test_replay_fifo_and_optimized():
    scenario = get_default_scenario()

    # Replay under FIFO
    res_fifo = replay_scenario(scenario, algorithm="fifo")
    assert res_fifo["algorithm"] == "fifo"
    m_fifo = res_fifo["metrics"]
    assert "requested_bytes" in m_fifo
    assert "delivered_before_deadline_bytes" in m_fifo
    assert "total_jobs" in m_fifo
    assert "on_time_jobs" in m_fifo
    assert "urgent_jobs" in m_fifo
    assert "resource_conflicts" in m_fifo
    assert m_fifo["total_jobs"] == len(scenario["initial_jobs"])
    assert m_fifo["resource_conflicts"] == 0

    # Replay under Optimized
    res_opt = replay_scenario(scenario, algorithm="optimized")
    assert res_opt["algorithm"] == "optimized"
    m_opt = res_opt["metrics"]
    assert m_opt["total_jobs"] == len(scenario["initial_jobs"])
    assert m_opt["resource_conflicts"] == 0


def test_replay_with_disruptions():
    # Rain disruption
    rain_scen = get_rain_scenario()
    res_rain = replay_scenario(rain_scen, algorithm="optimized")
    assert res_rain["metrics"]["total_jobs"] == 10

    # Outage disruption
    outage_scen = get_outage_scenario()
    res_outage = replay_scenario(outage_scen, algorithm="fifo")
    assert res_outage["metrics"]["total_jobs"] == 10

    # Emergency job arrival
    emerg_scen = get_emergency_job_scenario()
    res_emerg = replay_scenario(emerg_scen, algorithm="optimized")
    assert res_emerg["metrics"]["urgent_jobs"] >= 1


def test_replay_unknown_algorithm_rejected():
    scenario = get_default_scenario()
    with pytest.raises(ValueError):
        replay_scenario(scenario, algorithm="invalid_algo")


def test_replay_isolation_does_not_mutate_original():
    scenario = get_default_scenario()
    orig_job_count = len(scenario["initial_jobs"])

    res = replay_scenario(scenario, algorithm="fifo")
    assert len(scenario["initial_jobs"]) == orig_job_count
