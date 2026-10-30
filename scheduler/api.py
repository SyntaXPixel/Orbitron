"""Public API for the Orbitron scheduler and orbital prediction module."""

from __future__ import annotations

import copy
import time
from typing import Any

from scheduler.contracts import (
    ALGORITHM_FIFO,
    ALGORITHM_OPTIMIZED,
    SUPPORTED_ALGORITHMS,
)
from scheduler.exceptions import SchedulerInputError
from scheduler.orbital.opportunities import predict_opportunities as _predict_opportunities
from scheduler.orbital.propagation import propagate_satellites as _propagate_satellites
from scheduler.planning.fifo import run_fifo_scheduler
from scheduler.planning.normalization import normalize_problem
from scheduler.planning.optimized import run_optimized_scheduler


def predict_opportunities(
    catalog: dict,
    horizon: dict,
) -> list[dict]:
    """Predict satellite-to-station contact opportunities over a planning horizon.

    Parameters:
        catalog: Catalogue dict containing 'satellites', 'stations', and 'orbit_definitions'.
        horizon: Horizon dict containing 'from_at' and 'to_at' ISO timestamps.

    Returns:
        List of opportunity dicts matching the orbitron.v1 Opportunity interface.
    """
    # Defensive deepcopy to guarantee input immutability
    catalog_copy = copy.deepcopy(catalog)
    horizon_copy = copy.deepcopy(horizon)
    return _predict_opportunities(catalog_copy, horizon_copy)


def propagate_satellites(
    orbit_definitions: list[dict],
    at: str,
) -> list[dict]:
    """Calculate satellite positions at an explicit UTC timestamp string.

    Parameters:
        orbit_definitions: List of orbital definition dicts with format='tle'.
        at: ISO 8601 UTC timestamp string ending with 'Z'.

    Returns:
        List of satellite position records.
    """
    definitions_copy = copy.deepcopy(orbit_definitions)
    return _propagate_satellites(definitions_copy, at)


def solve_schedule(
    problem: dict,
    algorithm: str,
    time_limit_seconds: int = 5,
) -> dict:
    """Solve the communication scheduling problem using the requested algorithm.

    Parameters:
        problem: Immutable planning problem dictionary matching orbitron.v1 contract.
        algorithm: 'fifo' or 'optimized'. Unknown values are rejected explicitly.
        time_limit_seconds: Total time budget in seconds (default 5).

    Returns:
        Dict containing:
        - status: 'feasible', 'infeasible', or 'unavailable'
        - assignments: List of proposed assignments
        - unassigned_jobs: List of unassigned job records with reasons
        - metrics: Diagnostic metrics
    """
    start_time = time.monotonic()

    if not isinstance(algorithm, str) or algorithm not in SUPPORTED_ALGORITHMS:
        raise SchedulerInputError(
            f"Unsupported algorithm '{algorithm}'. Must be one of: {sorted(SUPPORTED_ALGORITHMS)}"
        )

    # Defensive deepcopy to guarantee input immutability
    problem_copy = copy.deepcopy(problem)
    normalized = normalize_problem(problem_copy)

    if algorithm == ALGORITHM_FIFO:
        status, assignments, unassigned_jobs, metrics = run_fifo_scheduler(normalized)
    elif algorithm == ALGORITHM_OPTIMIZED:
        status, assignments, unassigned_jobs, metrics = run_optimized_scheduler(
            normalized, time_limit_seconds=time_limit_seconds
        )
    else:
        raise SchedulerInputError(f"Unsupported algorithm '{algorithm}'")

    metrics["elapsed_ms"] = int((time.monotonic() - start_time) * 1000)

    return {
        "status": status,
        "assignments": assignments,
        "unassigned_jobs": unassigned_jobs,
        "metrics": metrics,
    }
