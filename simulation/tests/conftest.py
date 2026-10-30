"""Pytest fixtures and configuration for simulation module tests."""

import base64
import os
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from simulation import orbital_adapter, security_adapter
from simulation.config import SimulationConfig
from simulation.fixtures.scenarios.suite import get_default_scenario, get_scale_scenario


@pytest.fixture(autouse=True)
def setup_security_and_orbital_handlers():
    """Configure genuine cryptographic handlers and orbital test propagator for unit tests."""
    def test_encrypt(plaintext: bytes, key: bytes, associated_data: bytes) -> dict:
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
        return {
            "version": "orbitron.payload.v1",
            "algorithm": "AES-256-GCM",
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
        }

    def test_decrypt(envelope: dict, key: bytes, associated_data: bytes) -> bytes:
        aesgcm = AESGCM(key)
        nonce = base64.b64decode(envelope["nonce_b64"])
        ciphertext = base64.b64decode(envelope["ciphertext_b64"])
        return aesgcm.decrypt(nonce, ciphertext, associated_data)

    def test_verify_token(token: str, public_key: bytes, expected_scope: dict, server_time: str, sim_time: str) -> dict:
        if token == "expired-token":
            raise ValueError("Token has expired.")
        if token == "invalid-station-token":
            raise ValueError("Station ID in token does not match expected scope.")
        return {"authorized": True, "scope": expected_scope}

    def test_propagate(orbit_definitions: list, at: str) -> list:
        # Realistic deterministic propagation for unit test definitions
        results = []
        for i, o_def in enumerate(orbit_definitions):
            sat_id = o_def["satellite_id"]
            results.append({
                "satellite_id": sat_id,
                "position": {
                    "latitude_deg": -15.0 + (i * 5.0) % 60.0,
                    "longitude_deg": 10.0 + (i * 12.0) % 180.0,
                    "altitude_km": 540.0,
                    "observed_at": at,
                },
            })
        return results

    security_adapter.set_security_handlers(
        encrypt_handler=test_encrypt,
        decrypt_handler=test_decrypt,
        verify_token_handler=test_verify_token,
    )
    orbital_adapter.set_orbital_propagator(test_propagate)

    yield

    # Teardown
    security_adapter.set_security_handlers(None, None, None)
    orbital_adapter.set_orbital_propagator(None)


@pytest.fixture
def tmp_runtime_dir(tmp_path):
    """Temporary runtime directory for tests."""
    r_dir = tmp_path / ".runtime"
    r_dir.mkdir(parents=True, exist_ok=True)
    return r_dir


@pytest.fixture
def test_config(tmp_runtime_dir):
    return SimulationConfig(
        backend_url="http://localhost:8000/api/v1",
        runtime_dir=tmp_runtime_dir,
        tick_size_seconds=1.0,
        speed_multiplier=1.0,
        max_tick_advance_seconds=60,
    )


@pytest.fixture
def default_scenario():
    return get_default_scenario()


@pytest.fixture
def scale_scenario():
    return get_scale_scenario()

