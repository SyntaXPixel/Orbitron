"""Data contracts and schemas for the Orbitron simulation module.

Aligned with shared contract orbitron.v1.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional
from pydantic import BaseModel, Field

CONTRACT_VERSION = "orbitron.v1"
PAYLOAD_ENVELOPE_VERSION = "orbitron.payload.v1"


class Position(BaseModel):
    """Geographic position and observation time."""
    latitude_deg: float
    longitude_deg: float
    altitude_km: float
    observed_at: str


class TelemetryRecord(BaseModel):
    """Telemetry report submitted for a virtual satellite."""
    event_id: str
    scenario_id: str
    sequence: int
    satellite_id: str
    observed_at: str
    position: Position
    operational_status: str = "nominal"  # nominal, degraded, critical, offline
    generated_bytes_total: int = 0


class StationHeartbeatRecord(BaseModel):
    """Heartbeat report submitted for a station gateway."""
    event_id: str
    scenario_id: str
    sequence: int
    station_id: str
    observed_at: str
    operational_status: str = "operational"  # operational, unavailable, degraded, offline


class ContactProgressRecord(BaseModel):
    """Contact progress report representing mission-data downlink progress."""
    event_id: str
    scenario_id: str
    sequence: int
    contact_id: str
    interval_start_at: str
    interval_end_at: str
    cumulative_transferred_bytes: int
    final: bool = False


class AtomicTickRequest(BaseModel):
    """Atomic tick submitted by the fleet controller to advance authoritative time."""
    event_id: str
    scenario_id: str
    previous_simulation_time: str
    simulation_time: str
    telemetry: List[TelemetryRecord] = Field(default_factory=list)
    station_heartbeats: List[StationHeartbeatRecord] = Field(default_factory=list)
    contact_progress: List[ContactProgressRecord] = Field(default_factory=list)


class ServicePrincipal(BaseModel):
    """Authenticated service principal information."""
    id: str
    role: str  # simulator_controller, satellite, station_gateway, owner_receiver
    permitted_resource_ids: List[str] = Field(default_factory=list)


class ServiceCommand(BaseModel):
    """Command received from backend /service/work."""
    id: str
    operation_id: Optional[str] = None
    scenario_id: str
    kind: str  # initialize_scenario, pause, resume, step, reset, contact_offer, prepare_transfer, security_check
    resource_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    expires_at: Optional[str] = None


class CommandAckRequest(BaseModel):
    """Acknowledgement submitted for a service command."""
    event_id: str
    scenario_id: str
    status: str  # completed, failed
    result: dict[str, Any] = Field(default_factory=dict)
    reasons: List[dict[str, Any]] = Field(default_factory=list)


class TransferProgressRecord(BaseModel):
    """Progress reported by a partner gateway forwarding ciphertext bytes."""
    event_id: str
    scenario_id: str
    transfer_id: str
    forwarded_bytes: int
    ciphertext_sha256: str


class DeliveryReceiptRecord(BaseModel):
    """Delivery receipt reported by an owner receiver after authenticated decryption."""
    event_id: str
    scenario_id: str
    transfer_id: str
    owner_plaintext_sha256: str
    integrity_status: str  # verified, corrupted, mismatch
    owner_decryption_status: str  # success, failed


class JobCreateRequest(BaseModel):
    """Job creation body matching public backend schema."""
    satellite_id: str
    data_bytes: int
    deadline_at: str
    priority: str = "routine"  # routine, high, emergency
    allow_split: bool = True


class PayloadEnvelope(BaseModel):
    """Cryptographic envelope structure for encrypted sample transfers."""
    version: str = PAYLOAD_ENVELOPE_VERSION
    algorithm: str = "AES-256-GCM"
    nonce_b64: str
    ciphertext_b64: str


class PayloadAssociatedData(BaseModel):
    """Canonical associated data fields for payload authenticated encryption."""
    scenario_id: str
    transfer_id: str
    contact_id: str
    satellite_id: str
    station_id: str
    owner_org_id: str
    expected_plaintext_sha256: str

    def to_canonical_bytes(self) -> bytes:
        """Encode canonical UTF-8 JSON with stable key ordering and compact separators."""
        data = {
            "contact_id": self.contact_id,
            "expected_plaintext_sha256": self.expected_plaintext_sha256,
            "owner_org_id": self.owner_org_id,
            "satellite_id": self.satellite_id,
            "scenario_id": self.scenario_id,
            "station_id": self.station_id,
            "transfer_id": self.transfer_id,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


class SchedulerMetrics(BaseModel):
    """Exact public metrics shape returned by evaluation replay."""
    requested_bytes: int = 0
    delivered_before_deadline_bytes: int = 0
    total_jobs: int = 0
    on_time_jobs: int = 0
    urgent_jobs: int = 0
    urgent_on_time_jobs: int = 0
    resource_conflicts: int = 0
    scheduling_duration_ms: int = 0
    bookings_changed: int = 0


class ReplayResult(BaseModel):
    """Result returned by evaluation replay function."""
    algorithm: str
    metrics: SchedulerMetrics
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    delivery_events: List[dict[str, Any]] = Field(default_factory=list)
    final_jobs: List[dict[str, Any]] = Field(default_factory=list)
