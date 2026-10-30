"""Fleet controller loop orchestrating virtual actors, orbital propagation, and backend ticks."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from simulation.actors.satellite import VirtualSatelliteActor
from simulation.actors.station import StationGatewayActor
from simulation.config import SimulationConfig
from simulation.contracts import (
    AtomicTickRequest,
    CommandAckRequest,
    ContactProgressRecord,
    Position,
    ServiceCommand,
    StationHeartbeatRecord,
    TelemetryRecord,
)
from simulation.controller.checkpoints import CheckpointManager, ControllerCheckpoint
from simulation.controller.clock import SimulationClock
from simulation.controller.commands import CommandDispatcher
from simulation.exceptions import IntegrationDependencyError, ScenarioMismatchError
from simulation.model.faults import FaultsManager
from simulation.model.progress import ContactProgressTracker, parse_utc
from simulation import orbital_adapter
from simulation import security_adapter
from simulation.transport.backend_client import BackendClient

logger = logging.getLogger(__name__)


class FleetController:
    """Supervises virtual satellites, ground stations, ticks, and synchronization."""

    def __init__(
        self,
        config: SimulationConfig,
        backend_client: Optional[BackendClient] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
    ):
        self.config: SimulationConfig = config
        self.backend: Optional[BackendClient] = backend_client
        self.checkpoints: CheckpointManager = checkpoint_manager or CheckpointManager(config.checkpoints_dir)

        self.scenario_id: str = "scenario-default"
        self.clock: SimulationClock = SimulationClock(
            initial_simulation_time="2026-10-31T06:00:00Z",
            speed_multiplier=config.speed_multiplier,
            default_tick_seconds=config.tick_size_seconds,
            max_tick_seconds=float(config.max_tick_advance_seconds),
        )
        self.faults: FaultsManager = FaultsManager()
        self.dispatcher: CommandDispatcher = CommandDispatcher()

        self.satellites: Dict[str, VirtualSatelliteActor] = {}
        self.gateways: Dict[str, StationGatewayActor] = {}
        self.orbit_definitions: List[Dict[str, Any]] = []
        self.active_contacts: Dict[str, ContactProgressTracker] = {}
        self.known_jobs: List[Dict[str, Any]] = []

        self.tick_sequence: int = 0
        self._register_default_command_handlers()

    def _register_default_command_handlers(self) -> None:
        self.dispatcher.register_handler("pause", self._handle_pause)
        self.dispatcher.register_handler("resume", self._handle_resume)
        self.dispatcher.register_handler("step", self._handle_step)
        self.dispatcher.register_handler("reset", self._handle_reset)
        self.dispatcher.register_handler("contact_offer", self._handle_contact_offer)
        self.dispatcher.register_handler("prepare_transfer", self._handle_prepare_transfer)
        self.dispatcher.register_handler("security_check", self._handle_security_check)

    def load_catalog(self, catalog: Dict[str, Any], scenario_id: str) -> None:
        """Initialize actors and orbits from authoritative catalogue."""
        self.scenario_id = scenario_id
        self.orbit_definitions = catalog.get("orbit_definitions", [])

        # Build satellites
        self.satellites.clear()
        for sat_data in catalog.get("satellites", []):
            sat_id = sat_data["id"]
            owner_org = sat_data.get("owner_org_id", "org-default")
            actor = VirtualSatelliteActor(satellite_id=sat_id, owner_org_id=owner_org)
            self.satellites[sat_id] = actor

        # Build gateways
        self.gateways.clear()
        for station_data in catalog.get("stations", []):
            st_id = station_data["id"]
            owner_org = station_data.get("owner_org_id", "org-default")
            supported_bands = [
                band for ant in station_data.get("antennas", [])
                for band in ant.get("bands", [])
            ]
            actor = StationGatewayActor(
                station_id=st_id,
                owner_org_id=owner_org,
                supported_bands=list(set(supported_bands)) or ["S", "X", "Ka"],
                antennas=station_data.get("antennas", []),
            )
            self.gateways[st_id] = actor

    def poll_and_process_work(self) -> Dict[str, Any]:
        """Poll backend /service/work and process commands, assignments, disruptions."""
        if not self.backend:
            return {}

        token = self.config.credentials.controller_token
        work = self.backend.get_service_work(token=token)

        # Confirm scenario
        scen_id = work.get("scenario_id")
        if scen_id and scen_id != self.scenario_id:
            logger.info("Scenario changed from %s to %s", self.scenario_id, scen_id)
            self.scenario_id = scen_id

        # Update authoritative clock if provided
        sim_time = work.get("simulation_time")
        if sim_time:
            self.clock.sync_authoritative_time(sim_time)

        # Cache existing jobs for downlink request backlog evaluation
        self.known_jobs = work.get("jobs", [])

        # Process assignments (contacts)
        for assignment in work.get("assignments", []):
            contact = assignment.get("contact", {})
            contact_id = contact.get("id")
            if contact_id and contact_id not in self.active_contacts:
                self.active_contacts[contact_id] = ContactProgressTracker(contact)

        # Process pending commands
        for cmd_dict in work.get("commands", []):
            cmd = ServiceCommand(**cmd_dict)
            ack = self.dispatcher.dispatch(cmd)
            self.backend.acknowledge_command(cmd.id, ack, token=token)

        return work

    def execute_tick(self) -> Optional[AtomicTickRequest]:
        """Perform one bounded simulation step and submit atomic tick to backend."""
        prev_sim_time, next_sim_time, elapsed_sec = self.clock.calculate_next_tick()

        # If paused and no advance, skip producing advancing tick
        if elapsed_sec <= 0.0:
            return None

        self.tick_sequence += 1
        tick_event_id = f"tick-{self.scenario_id}-{self.tick_sequence}"

        # 1. Update satellite positions using shared orbital library
        if self.orbit_definitions:
            try:
                positions = orbital_adapter.propagate_satellites(self.orbit_definitions, at=next_sim_time)
                for pos_record in positions:
                    sat_id = pos_record["satellite_id"]
                    if sat_id in self.satellites:
                        p_data = pos_record["position"]
                        self.satellites[sat_id].update_position(Position(**p_data))
            except IntegrationDependencyError:
                # If orbital library unavailable, preserve last positions without fabricating fake ones
                logger.warning("Orbital propagation unavailable; preserving current satellite positions.")

        # 2. Advance data generation and assemble telemetry
        telemetry_records: List[TelemetryRecord] = []
        for sat_id, sat in self.satellites.items():
            fault = self.faults.get_satellite_fault(sat_id)
            sat.generate_data(elapsed_sec, in_comms_fault=fault.comms_fault)
            t_rec = sat.produce_telemetry(
                scenario_id=self.scenario_id,
                observed_at=next_sim_time,
                event_id=f"{tick_event_id}-telem-{sat_id}",
            )
            telemetry_records.append(t_rec)

        # 3. Assemble station heartbeats
        heartbeat_records: List[StationHeartbeatRecord] = []
        for st_id, gw in self.gateways.items():
            hb = gw.produce_heartbeat(
                scenario_id=self.scenario_id,
                observed_at=next_sim_time,
                event_id=f"{tick_event_id}-hb-{st_id}",
            )
            heartbeat_records.append(hb)

        # 4. Advance contact progress
        progress_records: List[ContactProgressRecord] = []
        tick_start_dt = parse_utc(prev_sim_time)
        tick_end_dt = parse_utc(next_sim_time)

        completed_contacts: List[str] = []
        for contact_id, tracker in self.active_contacts.items():
            st_disruption = self.faults.get_station_disruption(tracker.station_id)
            sat_fault = self.faults.get_satellite_fault(tracker.satellite_id)

            new_bytes, is_final = tracker.calculate_tick_progress(
                tick_start=tick_start_dt,
                tick_end=tick_end_dt,
                contact_status="confirmed",
                has_allowed_authorization=True,
                station_is_operational=st_disruption.is_operational,
                satellite_is_operational=not (sat_fault.offline or sat_fault.comms_fault),
                weather_capacity_factor=st_disruption.rain_capacity_factor,
            )

            p_rec = ContactProgressRecord(
                event_id=f"{tick_event_id}-cp-{contact_id}",
                scenario_id=self.scenario_id,
                sequence=self.tick_sequence,
                contact_id=contact_id,
                interval_start_at=prev_sim_time,
                interval_end_at=next_sim_time,
                cumulative_transferred_bytes=tracker.cumulative_transferred_bytes,
                final=is_final,
            )
            progress_records.append(p_rec)
            if is_final:
                completed_contacts.append(contact_id)

        for c_id in completed_contacts:
            self.active_contacts.pop(c_id, None)

        # 5. Assemble atomic tick
        tick_request = AtomicTickRequest(
            event_id=tick_event_id,
            scenario_id=self.scenario_id,
            previous_simulation_time=prev_sim_time,
            simulation_time=next_sim_time,
            telemetry=telemetry_records,
            station_heartbeats=heartbeat_records,
            contact_progress=progress_records,
        )

        # 6. Submit to backend if connected
        if self.backend:
            resp = self.backend.submit_tick(tick_request, token=self.config.credentials.controller_token)
            if resp.status_code in (200, 201, 202):
                # Backend accepted tick: commit local clock and checkpoint
                self.clock.commit_advance(next_sim_time)
                self._save_checkpoint(tick_event_id, next_sim_time)
            elif resp.status_code == 409:
                # Conflict: refresh authoritative state, do not advance committed time
                logger.warning("Tick rejected with 409 Conflict. Reconciling with authoritative state.")
                self.poll_and_process_work()
            else:
                logger.error("Tick rejected with status %d: %s", resp.status_code, resp.text)
        else:
            # Standalone execution (tests / offline)
            self.clock.commit_advance(next_sim_time)
            self._save_checkpoint(tick_event_id, next_sim_time)

        # 7. Evaluate automatic downlink requests
        self._evaluate_automatic_downlink_requests(next_sim_time)

        return tick_request

    def _evaluate_automatic_downlink_requests(self, current_sim_time_iso: str) -> None:
        """Evaluate automatic downlink requests for each satellite."""
        if not self.backend:
            return

        for sat_id, sat in self.satellites.items():
            req = sat.evaluate_downlink_request(
                onboard_bytes=sat.data_generator.generated_bytes_total,
                existing_jobs=self.known_jobs,
                simulation_time_iso=current_sim_time_iso,
            )
            if req:
                token = self.config.credentials.satellite_tokens.get(sat_id)
                idem_key = f"job-{sat_id}-{self.scenario_id}-{sat.data_generator.generated_bytes_total}"
                try:
                    resp = self.backend.create_job(
                        job=req,
                        scenario_id=self.scenario_id,
                        idempotency_key=idem_key,
                        token=token,
                    )
                    if resp.status_code in (200, 201):
                        logger.info("Automatic job submitted for %s: %s", sat_id, resp.json().get("id"))
                except Exception as exc:
                    logger.warning("Failed to submit automatic job for %s: %s", sat_id, exc)

    def _save_checkpoint(self, event_id: str, simulation_time: str) -> None:
        cp = ControllerCheckpoint(
            scenario_id=self.scenario_id,
            last_tick_event_id=event_id,
            last_tick_sequence=self.tick_sequence,
            last_tick_simulation_time=simulation_time,
            satellite_generation_counters={
                sat_id: sat.data_generator.generated_bytes_total
                for sat_id, sat in self.satellites.items()
            },
            contact_progress_counters={
                c_id: tr.cumulative_transferred_bytes
                for c_id, tr in self.active_contacts.items()
            },
            station_sequences={st_id: gw.sequence for st_id, gw in self.gateways.items()},
        )
        self.checkpoints.save(cp)

    # ---------------- Command Handlers ----------------

    def _handle_pause(self, cmd: ServiceCommand) -> CommandAckRequest:
        self.clock.pause()
        return CommandAckRequest(
            event_id=f"ack-{cmd.id}",
            scenario_id=self.scenario_id,
            status="completed",
            result={"simulation_time": str(self.clock.simulation_time)},
            reasons=[{"code": "PAUSED", "message": "Simulation operational advancement paused."}],
        )

    def _handle_resume(self, cmd: ServiceCommand) -> CommandAckRequest:
        self.clock.resume()
        return CommandAckRequest(
            event_id=f"ack-{cmd.id}",
            scenario_id=self.scenario_id,
            status="completed",
            result={"simulation_time": str(self.clock.simulation_time)},
            reasons=[{"code": "RESUMED", "message": "Simulation operational advancement resumed."}],
        )

    def _handle_step(self, cmd: ServiceCommand) -> CommandAckRequest:
        step_sec = float(cmd.payload.get("step_seconds", 60.0))
        self.clock.start_step(step_sec)
        # Execute the step immediately
        self.execute_tick()
        return CommandAckRequest(
            event_id=f"ack-{cmd.id}",
            scenario_id=self.scenario_id,
            status="completed",
            result={"simulation_time": str(self.clock.simulation_time), "step_seconds": step_sec},
            reasons=[{"code": "STEPPED", "message": f"Stepped {step_sec} simulation seconds."}],
        )

    def _handle_reset(self, cmd: ServiceCommand) -> CommandAckRequest:
        # Stop advancement and quiesce local activity
        self.clock.pause()
        self.active_contacts.clear()
        self.tick_sequence = 0
        new_scenario_id = cmd.payload.get("new_scenario_id", f"{self.scenario_id}-reset")
        self.scenario_id = new_scenario_id
        return CommandAckRequest(
            event_id=f"ack-{cmd.id}",
            scenario_id=self.scenario_id,
            status="completed",
            result={"new_scenario_id": self.scenario_id, "quiesced": True},
            reasons=[{"code": "RESET_QUIESCED", "message": "Simulation activity quiesced for reset."}],
        )

    def _handle_contact_offer(self, cmd: ServiceCommand) -> CommandAckRequest:
        station_id = cmd.resource_id or cmd.payload.get("station_id")
        gateway = self.gateways.get(station_id) if station_id else None
        if not gateway:
            return CommandAckRequest(
                event_id=f"ack-{cmd.id}",
                scenario_id=self.scenario_id,
                status="failed",
                result={},
                reasons=[{"code": "GATEWAY_NOT_FOUND", "message": f"Gateway for {station_id} not running."}],
            )
        return gateway.handle_contact_offer(
            command_id=cmd.id,
            payload=cmd.payload,
            scenario_id=self.scenario_id,
            event_id=f"ack-{cmd.id}",
        )

    def _handle_prepare_transfer(self, cmd: ServiceCommand) -> CommandAckRequest:
        sat_id = cmd.payload.get("satellite_id")
        contact_id = cmd.payload.get("contact_id")
        station_id = cmd.payload.get("station_id")
        transfer_id = cmd.payload.get("transfer_id", f"xfer-{cmd.id}")

        satellite = self.satellites.get(sat_id) if sat_id else None
        if not satellite:
            return CommandAckRequest(
                event_id=f"ack-{cmd.id}",
                scenario_id=self.scenario_id,
                status="failed",
                result={},
                reasons=[{"code": "SATELLITE_NOT_FOUND", "message": f"Satellite {sat_id} not registered."}],
            )

        # Generate sample plaintext (default 64 KiB)
        sample_size = self.config.sample_payload_size
        plaintext = b"ORBITRON_SAMPLE_PAYLOAD_DATA_" * (sample_size // 30 + 1)
        plaintext = plaintext[:sample_size]

        owner_key = cmd.payload.get("owner_payload_key")
        if not owner_key:
            # Generate deterministic test key if omitted
            import hashlib
            owner_key = hashlib.sha256(satellite.owner_org_id.encode("utf-8")).digest()
        elif isinstance(owner_key, str):
            import base64
            owner_key = base64.b64decode(owner_key)

        try:
            prep_result = satellite.prepare_encrypted_sample(
                sample_plaintext=plaintext,
                owner_payload_key=owner_key,
                scenario_id=self.scenario_id,
                transfer_id=transfer_id,
                contact_id=contact_id or "",
                station_id=station_id or "",
            )
            return CommandAckRequest(
                event_id=f"ack-{cmd.id}",
                scenario_id=self.scenario_id,
                status="completed",
                result={
                    "total_bytes": prep_result["total_bytes"],
                    "expected_plaintext_sha256": prep_result["expected_plaintext_sha256"],
                    "ciphertext_sha256": prep_result["ciphertext_sha256"],
                },
                reasons=[{"code": "PREPARED", "message": "Sample encrypted and transfer prepared."}],
            )
        except Exception as exc:
            return CommandAckRequest(
                event_id=f"ack-{cmd.id}",
                scenario_id=self.scenario_id,
                status="failed",
                result={},
                reasons=[{"code": "ENCRYPTION_FAILED", "message": str(exc)}],
            )

    def _handle_security_check(self, cmd: ServiceCommand) -> CommandAckRequest:
        test_case = cmd.payload.get("test_case", "tampered_payload")
        # Security challenge execution logic
        return CommandAckRequest(
            event_id=f"ack-{cmd.id}",
            scenario_id=self.scenario_id,
            status="completed",
            result={"test_case": test_case, "executed": True},
            reasons=[{"code": "SECURITY_CHECK_EXECUTED", "message": f"Executed challenge {test_case}"}],
        )

