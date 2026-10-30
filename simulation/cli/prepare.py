"""Local environment preparation command."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sys

from simulation.config import SimulationConfig


def prepare_environment(backend_url: str, credentials_file: str, runtime_dir: str = "simulation/.runtime") -> int:
    """Prepare runtime directories, demonstration keys, and synthetic sample files."""
    r_path = Path(runtime_dir)
    cfg = SimulationConfig.load(
        backend_url=backend_url,
        credentials_file=credentials_file,
        runtime_dir=r_path,
    )
    cfg.ensure_directories()

    # Create directories for demonstration organisations
    org_ids = ["org-a", "org-b"]
    for org_id in org_ids:
        keys_dir = cfg.owner_keys_dir(org_id)
        samples_dir = cfg.owner_samples_dir(org_id)
        verified_dir = cfg.receiver_verified_dir(org_id)

        keys_dir.mkdir(parents=True, exist_ok=True)
        samples_dir.mkdir(parents=True, exist_ok=True)
        verified_dir.mkdir(parents=True, exist_ok=True)

        # Generate a 256-bit AES key if absent
        key_file = keys_dir / "payload.key"
        if not key_file.exists():
            key_file.write_bytes(os.urandom(32))

        # Generate sample demonstration file (64 KiB default)
        sample_file = samples_dir / "sample_64k.bin"
        if not sample_file.exists():
            content = (f"ORBITRON_SYNTHETIC_DEMO_DATA_FOR_{org_id.upper()}_".encode("utf-8") * 2000)[: cfg.sample_payload_size]
            sample_file.write_bytes(content)

    # Create directories for default gateways
    for st_num in (1, 2, 3):
        st_id = f"station-{st_num:02d}"
        cfg.gateway_buffer_dir(st_id).mkdir(parents=True, exist_ok=True)

    print(f"Simulation runtime directories prepared under: {r_path.resolve()}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Orbitron simulation runtime environment.")
    parser.add_argument(
        "--backend-url",
        default="http://localhost:8000/api/v1",
        help="Backend API base URL",
    )
    parser.add_argument(
        "--credentials-file",
        default="backend/.runtime/service-credentials.json",
        help="Path to backend service credentials JSON",
    )
    parser.add_argument(
        "--runtime-dir",
        default="simulation/.runtime",
        help="Local runtime directory path",
    )
    args = parser.parse_args()
    code = prepare_environment(
        backend_url=args.backend_url,
        credentials_file=args.credentials_file,
        runtime_dir=args.runtime_dir,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
