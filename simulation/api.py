"""Public Python interface for the Orbitron simulation module."""

from __future__ import annotations

from typing import Any, Dict

from simulation.config import SimulationConfig
from simulation.controller.loop import FleetController
from simulation.orbital_adapter import propagate_satellites, set_orbital_propagator
from simulation.replay.engine import replay_scenario
from simulation.security_adapter import (
    canonical_payload_aad,
    decrypt_payload,
    encrypt_payload,
    is_security_available,
    set_security_handlers,
    verify_contact_token,
)
from simulation.transport.gateway_server import create_gateway_app
from simulation.transport.receiver_server import create_receiver_app

__all__ = [
    "replay_scenario",
    "FleetController",
    "SimulationConfig",
    "create_gateway_app",
    "create_receiver_app",
    "propagate_satellites",
    "set_orbital_propagator",
    "encrypt_payload",
    "decrypt_payload",
    "verify_contact_token",
    "canonical_payload_aad",
    "is_security_available",
    "set_security_handlers",
]

