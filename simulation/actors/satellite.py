"""Virtual satellite actor."""

from __future__ import annotations

import base64
import hashlib
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from simulation.contracts import JobCreateRequest, PayloadAssociatedData, Position, TelemetryRecord
from simulation.model.generation import SatelliteDataGenerator, SatelliteGenerationProfile
from simulation import security_adapter


class SatelliteProfile(BaseModel):
    """Configuration profile for a virtual satellite."""
    automatic_requests_enabled: bool = True
    request_threshold_bytes: int = 500_000_000  # 500 MB
    maximum_request_bytes: int = 2_000_000_000   # 2 GB
    deadline_offset_seconds: int = 7200         # 2 hours
    priority: str = "routine"
    allow_split: bool = True
    supported_bands: List[str] = ["X", "Ka"]
    max_rate_bps: int = 300_000_000


class VirtualSatelliteActor:
    """Represents a simulated satellite in the Orbitron fleet."""

    def __init__(
        self,
        satellite_id: str,
        owner_org_id: str,
        profile: Optional[SatelliteProfile] = None,
        generation_profile: Optional[SatelliteGenerationProfile] = None,
    ):
        self.satellite_id: str = satellite_id
        self.owner_org_id: str = owner_org_id
        self.profile: SatelliteProfile = profile or SatelliteProfile()
        self.data_generator: SatelliteDataGenerator = SatelliteDataGenerator(
            satellite_id=satellite_id,
            profile=generation_profile,
        )
        self.position: Optional[Position] = None
        self.operational_status: str = "nominal"
        self.sequence: int = 0

    def update_position(self, pos: Position) -> None:
        """Update current orbital position."""
        self.position = pos

    def generate_data(self, elapsed_seconds: float, in_comms_fault: bool = False) -> int:
        """Advance monotonic data generation counter."""
        return self.data_generator.advance(elapsed_seconds, in_comms_fault=in_comms_fault)

    def produce_telemetry(self, scenario_id: str, observed_at: str, event_id: str) -> TelemetryRecord:
        """Assemble current telemetry observation record."""
        self.sequence += 1
        pos = self.position or Position(
            latitude_deg=0.0,
            longitude_deg=0.0,
            altitude_km=500.0,
            observed_at=observed_at,
        )
        return TelemetryRecord(
            event_id=event_id,
            scenario_id=scenario_id,
            sequence=self.sequence,
            satellite_id=self.satellite_id,
            observed_at=observed_at,
            position=pos,
            operational_status=self.operational_status,
            generated_bytes_total=self.data_generator.generated_bytes_total,
        )

    def evaluate_downlink_request(
        self,
        onboard_bytes: int,
        existing_jobs: List[Dict[str, Any]],
        simulation_time_iso: str,
    ) -> Optional[JobCreateRequest]:
        """Check unreserved backlog and construct automatic downlink request if threshold met."""
        if not self.profile.automatic_requests_enabled:
            return None

        # Calculate reserved bytes by pending / scheduled / active jobs
        reserved_bytes = 0
        for job in existing_jobs:
            if job.get("satellite_id") == self.satellite_id:
                status = job.get("status", "")
                if status not in ("completed", "cancelled", "failed"):
                    reserved_bytes += job.get("remaining_bytes", 0)

        unreserved_backlog = max(0, onboard_bytes - reserved_bytes)
        if unreserved_backlog < self.profile.request_threshold_bytes:
            return None

        request_bytes = min(unreserved_backlog, self.profile.maximum_request_bytes)

        # Calculate deadline
        from simulation.model.progress import parse_utc
        from datetime import timedelta
        sim_dt = parse_utc(simulation_time_iso)
        deadline_dt = sim_dt + timedelta(seconds=self.profile.deadline_offset_seconds)
        deadline_iso = deadline_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        return JobCreateRequest(
            satellite_id=self.satellite_id,
            data_bytes=request_bytes,
            deadline_at=deadline_iso,
            priority=self.profile.priority,
            allow_split=self.profile.allow_split,
        )

    def prepare_encrypted_sample(
        self,
        sample_plaintext: bytes,
        owner_payload_key: bytes,
        scenario_id: str,
        transfer_id: str,
        contact_id: str,
        station_id: str,
    ) -> Dict[str, Any]:
        """Encrypt sample payload using owner's payload key.

        Returns envelope dict with metadata and sha256 hashes.
        """
        plaintext_sha256 = hashlib.sha256(sample_plaintext).hexdigest()

        aad = PayloadAssociatedData(
            scenario_id=scenario_id,
            transfer_id=transfer_id,
            contact_id=contact_id,
            satellite_id=self.satellite_id,
            station_id=station_id,
            owner_org_id=self.owner_org_id,
            expected_plaintext_sha256=plaintext_sha256,
        )
        aad_bytes = aad.to_canonical_bytes()

        # Call security adapter
        envelope = security_adapter.encrypt_payload(
            plaintext=sample_plaintext,
            key=owner_payload_key,
            associated_data=aad_bytes,
        )

        ciphertext_bytes = base64.b64decode(envelope["ciphertext_b64"])
        ciphertext_sha256 = hashlib.sha256(ciphertext_bytes).hexdigest()

        return {
            "transfer_id": transfer_id,
            "envelope": envelope,
            "ciphertext_bytes": ciphertext_bytes,
            "total_bytes": len(ciphertext_bytes),
            "expected_plaintext_sha256": plaintext_sha256,
            "ciphertext_sha256": ciphertext_sha256,
            "aad": aad,
        }

