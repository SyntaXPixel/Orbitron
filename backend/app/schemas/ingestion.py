from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

class CatalogIngestRequest(BaseModel):
    event_id: str
    scenario_id: str
    organizations: List[Dict[str, Any]]
    satellites: List[Dict[str, Any]]
    stations: List[Dict[str, Any]]
    orbit_definitions: List[Dict[str, Any]]

class IngestPosition(BaseModel):
    latitude_deg: float
    longitude_deg: float
    altitude_km: float
    observed_at: str

class TelemetryIngestRequest(BaseModel):
    event_id: str
    scenario_id: str
    sequence: int
    satellite_id: str
    observed_at: str
    position: Optional[IngestPosition] = None
    operational_status: Literal["available", "communicating", "fault"]
    generated_bytes_total: int

class StationHeartbeatRequest(BaseModel):
    event_id: str
    scenario_id: str
    sequence: int
    station_id: str
    observed_at: str
    operational_status: Literal["online", "degraded", "offline"]

class ContactProgressRequest(BaseModel):
    event_id: str
    scenario_id: str
    sequence: int
    contact_id: str
    interval_start_at: str
    interval_end_at: str
    cumulative_transferred_bytes: int
    final: bool

class TickIngestRequest(BaseModel):
    event_id: str
    scenario_id: str
    previous_simulation_time: str
    simulation_time: str
    telemetry: List[TelemetryIngestRequest] = Field(default_factory=list)
    station_heartbeats: List[StationHeartbeatRequest] = Field(default_factory=list)
    contact_progress: List[ContactProgressRequest] = Field(default_factory=list)

class CommandAckRequest(BaseModel):
    event_id: str
    scenario_id: str
    status: Literal["completed", "failed"]
    result: Optional[Dict[str, Any]] = None
    reasons: List[Dict[str, Any]] = Field(default_factory=list)

class TransferProgressRequest(BaseModel):
    event_id: str
    scenario_id: str
    transfer_id: str
    forwarded_bytes: int
    ciphertext_sha256: Optional[str] = None

class DeliveryReceiptRequest(BaseModel):
    event_id: str
    scenario_id: str
    transfer_id: str
    owner_plaintext_sha256: str
    integrity_status: Literal["verified", "failed"]
    owner_decryption_status: Literal["succeeded", "failed"]
