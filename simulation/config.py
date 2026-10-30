"""Configuration management for the Orbitron simulation module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from simulation.exceptions import ConfigurationError


class ServiceCredentials(BaseModel):
    """Container for principal bearer tokens."""
    controller_token: Optional[str] = None
    satellite_tokens: Dict[str, str] = Field(default_factory=dict)
    gateway_tokens: Dict[str, str] = Field(default_factory=dict)
    receiver_tokens: Dict[str, str] = Field(default_factory=dict)


class SimulationConfig(BaseModel):
    """Runtime configuration for the simulation environment."""
    backend_url: str = "http://localhost:8000/api/v1"
    credentials_file: Optional[Path] = None
    runtime_dir: Path = Path("simulation/.runtime")

    # Clock & Pacing
    tick_size_seconds: float = 1.0
    speed_multiplier: float = 1.0
    max_tick_advance_seconds: int = 60

    # Payload demonstration
    sample_payload_size: int = 65536  # 64 KiB default

    # Network ports
    gateway_base_port: int = 9001
    receiver_base_port: int = 9101

    gateway_ports: Dict[str, int] = Field(default_factory=dict)
    receiver_ports: Dict[str, int] = Field(default_factory=dict)

    # Loaded credentials
    credentials: ServiceCredentials = Field(default_factory=ServiceCredentials)

    @classmethod
    def load(
        cls,
        backend_url: Optional[str] = None,
        credentials_file: Optional[Path | str] = None,
        runtime_dir: Optional[Path | str] = None,
    ) -> "SimulationConfig":
        """Load configuration with optional file overrides."""
        cfg = cls()
        if backend_url:
            cfg.backend_url = backend_url.rstrip("/")
        if runtime_dir:
            cfg.runtime_dir = Path(runtime_dir)

        if credentials_file:
            path = Path(credentials_file)
            cfg.credentials_file = path
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    cfg.credentials = ServiceCredentials(**data)
                except Exception as exc:
                    raise ConfigurationError(f"Failed to parse credentials file: {exc}") from exc

        return cfg

    @property
    def checkpoints_dir(self) -> Path:
        return self.runtime_dir / "checkpoints"

    def owner_keys_dir(self, org_id: str) -> Path:
        return self.runtime_dir / "owners" / org_id / "keys"

    def owner_samples_dir(self, org_id: str) -> Path:
        return self.runtime_dir / "owners" / org_id / "samples"

    def gateway_buffer_dir(self, station_id: str) -> Path:
        return self.runtime_dir / "gateways" / station_id / "ciphertext"

    def receiver_verified_dir(self, org_id: str) -> Path:
        return self.runtime_dir / "receivers" / org_id / "verified"

    def ensure_directories(self) -> None:
        """Create runtime directory hierarchy."""
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

