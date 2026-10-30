"""Supervised startup command for Orbitron simulation environment."""

from __future__ import annotations

import argparse
import logging
import multiprocessing
import os
from pathlib import Path
import signal
import sys
import time
from typing import List

import uvicorn

from simulation.cli.prepare import prepare_environment
from simulation.config import SimulationConfig
from simulation.controller.loop import FleetController
from simulation.fixtures.scenarios.suite import get_default_scenario
from simulation.transport.backend_client import BackendClient
from simulation.transport.gateway_server import create_gateway_app
from simulation.transport.receiver_server import create_receiver_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("simulation.supervisor")


def _run_gateway_process(station_id: str, port: int, buffer_dir_str: str, backend_url: str, token: str) -> None:
    """Run a single station gateway Uvicorn server."""
    backend_client = BackendClient(base_url=backend_url, default_token=token)
    app = create_gateway_app(
        station_id=station_id,
        buffer_dir=Path(buffer_dir_str),
        backend_client=backend_client,
    )
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def _run_receiver_process(org_id: str, port: int, verified_dir_str: str, key_bytes: bytes, backend_url: str, token: str) -> None:
    """Run a single owner receiver Uvicorn server."""
    backend_client = BackendClient(base_url=backend_url, default_token=token)
    app = create_receiver_app(
        owner_org_id=org_id,
        payload_key=key_bytes,
        verified_dir=Path(verified_dir_str),
        backend_client=backend_client,
    )
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


class ProcessSupervisor:
    """Supervises gateway and receiver background processes and the fleet controller."""

    def __init__(self, config: SimulationConfig):
        self.config: SimulationConfig = config
        self.processes: List[multiprocessing.Process] = []
        self._shutdown_requested: bool = False

    def start_servers(self) -> None:
        """Start gateway and receiver processes on configured loopback ports."""
        # Start Gateways
        for st_idx, st_num in enumerate((1, 2, 3)):
            station_id = f"station-{st_num:02d}"
            port = self.config.gateway_base_port + st_idx
            buf_dir = self.config.gateway_buffer_dir(station_id)
            token = self.config.credentials.gateway_tokens.get(station_id, "")

            p = multiprocessing.Process(
                target=_run_gateway_process,
                args=(station_id, port, str(buf_dir), self.config.backend_url, token),
                daemon=True,
            )
            p.start()
            self.processes.append(p)
            logger.info("Started Gateway process for %s on port %d (PID %d)", station_id, port, p.pid)

        # Start Owner Receivers
        for org_idx, org_id in enumerate(("org-a", "org-b")):
            port = self.config.receiver_base_port + org_idx
            ver_dir = self.config.receiver_verified_dir(org_id)
            key_path = self.config.owner_keys_dir(org_id) / "payload.key"
            key_bytes = key_path.read_bytes() if key_path.exists() else os.urandom(32)
            token = self.config.credentials.receiver_tokens.get(org_id, "")

            p = multiprocessing.Process(
                target=_run_receiver_process,
                args=(org_id, port, str(ver_dir), key_bytes, self.config.backend_url, token),
                daemon=True,
            )
            p.start()
            self.processes.append(p)
            logger.info("Started Owner Receiver process for %s on port %d (PID %d)", org_id, port, p.pid)

    def shutdown(self) -> None:
        """Stop all supervised child processes."""
        self._shutdown_requested = True
        logger.info("Terminating supervised child processes...")
        for p in self.processes:
            if p.is_alive():
                p.terminate()
                p.join(timeout=2.0)
        logger.info("Supervised processes stopped cleanly.")


def run_supervisor(
    backend_url: str,
    credentials_file: str,
    runtime_dir: str = "simulation/.runtime",
    standalone_mode: bool = False,
) -> int:
    """Supervised execution loop."""
    prepare_environment(backend_url, credentials_file, runtime_dir)

    cfg = SimulationConfig.load(
        backend_url=backend_url,
        credentials_file=credentials_file,
        runtime_dir=runtime_dir,
    )

    supervisor = ProcessSupervisor(cfg)

    # Setup signal handler
    def handle_signal(sig, frame):
        logger.info("Shutdown signal received (%s). Exiting...", sig)
        supervisor.shutdown()
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
    except (ValueError, AttributeError):
        pass  # Running in non-main thread

    # Start child processes
    supervisor.start_servers()
    time.sleep(1.0)  # Brief wait for ports to open

    # Create and run fleet controller
    backend_client = None if standalone_mode else BackendClient(
        base_url=backend_url,
        default_token=cfg.credentials.controller_token,
    )
    controller = FleetController(config=cfg, backend_client=backend_client)

    # Load default scenario
    default_scenario = get_default_scenario()
    controller.load_catalog(default_scenario["catalog"], scenario_id=default_scenario["id"])

    logger.info("Fleet controller initialized with scenario %s", controller.scenario_id)

    try:
        while not supervisor._shutdown_requested:
            # Poll work
            if backend_client:
                try:
                    controller.poll_and_process_work()
                except Exception as exc:
                    logger.debug("Backend polling check: %s", exc)

            # Execute tick if running / stepping
            controller.execute_tick()
            time.sleep(cfg.tick_size_seconds / cfg.speed_multiplier)

    except KeyboardInterrupt:
        logger.info("Simulation interrupted by user.")
    finally:
        supervisor.shutdown()

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run supervised Orbitron simulation environment.")
    parser.add_argument("--backend-url", default="http://localhost:8000/api/v1", help="Backend API base URL")
    parser.add_argument("--credentials-file", default="backend/.runtime/service-credentials.json", help="Service credentials JSON")
    parser.add_argument("--runtime-dir", default="simulation/.runtime", help="Runtime directory path")
    parser.add_argument("--standalone", action="store_true", help="Run standalone without live backend connection")

    args = parser.parse_args()
    code = run_supervisor(
        backend_url=args.backend_url,
        credentials_file=args.credentials_file,
        runtime_dir=args.runtime_dir,
        standalone_mode=args.standalone,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
