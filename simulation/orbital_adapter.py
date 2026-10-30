"""Orbital propagation adapter for the simulation module.

Delegates satellite position calculations to the shared orbital library
at scheduler.api.propagate_satellites, preserving source and provenance.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional
from simulation.exceptions import IntegrationDependencyError

logger = logging.getLogger(__name__)

# Type for propagator callable: (orbit_definitions: list[dict], at: str) -> list[dict]
PropagatorFunc = Callable[[List[Dict[str, Any]], str], List[Dict[str, Any]]]

_custom_propagator: Optional[PropagatorFunc] = None


def set_orbital_propagator(func: Optional[PropagatorFunc]) -> None:
    """Allow injecting or overriding the orbital propagator (useful in tests or standalone evaluation)."""
    global _custom_propagator
    _custom_propagator = func


def propagate_satellites(orbit_definitions: List[Dict[str, Any]], at: str) -> List[Dict[str, Any]]:
    """Calculate satellite positions at target timestamp using the shared scheduler function.

    Args:
        orbit_definitions: List of orbital definitions from catalogue.
        at: Target simulation timestamp in UTC (ending in 'Z').

    Returns:
        List of position records matching scheduler.api.propagate_satellites specification.

    Raises:
        IntegrationDependencyError: If scheduler.api.propagate_satellites is missing and no fallback is set.
    """
    if _custom_propagator is not None:
        return _custom_propagator(orbit_definitions, at)

    try:
        from scheduler.api import propagate_satellites as scheduler_propagate
        return scheduler_propagate(orbit_definitions, at=at)
    except (ImportError, AttributeError) as exc:
        logger.warning("Shared scheduler orbital library (scheduler.api.propagate_satellites) is unavailable.")
        raise IntegrationDependencyError(
            "Shared orbital propagation interface scheduler.api.propagate_satellites is not available."
        ) from exc
