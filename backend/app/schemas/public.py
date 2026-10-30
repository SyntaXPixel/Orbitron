from datetime import datetime, timezone
from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, field_serializer

def to_iso_z(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    s = dt.isoformat()
    if s.endswith("+00:00"):
        s = s[:-6] + "Z"
    elif not s.endswith("Z"):
        s += "Z"
    return s

Priority = Literal["routine", "high", "emergency"]
Role = Literal["operator", "network_admin"]
JobStatus = Literal["pending", "scheduled", "active", "completed", "blocked", "cancelled"]
ContactStatus = Literal["tentative", "confirmed", "active", "completed", "failed", "cancelled"]
AuthorizationStatus = Literal["pending", "allowed", "denied", "expired", "revoked"]
OperationStatus = Literal["queued", "running", "succeeded", "failed"]

class Reason(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    message: str
    resource_ids: List[str]

class Organization(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str

class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_name: str
    email: str
    organization_id: str
    role: Role

class Session(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user: User
    csrf_token: str
    expires_at: str

    @field_serializer("expires_at", when_used="json")
    def serialize_expires_at(self, v: str) -> str:
        return v

class Position(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    latitude_deg: float
    longitude_deg: float
    altitude_km: float
    observed_at: str

class Satellite(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    owner_org_id: str
    supported_bands: List[str]
    max_downlink_rate_bps: int
    max_parallel_contacts: int
    onboard_bytes: int
    operational_status: Literal["available", "communicating", "fault"]
    telemetry_status: Literal["fresh", "stale", "never_seen"]
    position: Optional[Position] = None
    last_telemetry_at: Optional[str] = None
    source: Literal["simulated"] = "simulated"
    orbit_source: Literal["public_tle", "synthetic"] = "synthetic"
    orbit_epoch_at: Optional[str] = None

class Antenna(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    supported_bands: List[str]
    max_rate_bps: int
    setup_seconds: int
    status: Literal["available", "maintenance", "offline"]

class Station(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    owner_org_id: str
    latitude_deg: float
    longitude_deg: float
    min_elevation_deg: float
    operational_status: Literal["online", "degraded", "offline"]
    connection_status: Literal["connected", "stale", "disconnected"]
    weather_capacity_factor: float
    sharing_enabled: bool
    approved_partner_org_ids: List[str]
    antennas: List[Antenna]
    last_heartbeat_at: Optional[str] = None

class Job(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    satellite_id: str
    owner_org_id: str
    requested_bytes: int
    delivered_bytes: int
    remaining_bytes: int
    priority: Priority
    deadline_at: str
    allow_split: bool
    status: JobStatus
    reasons: List[Reason]
    created_at: str
    updated_at: str

class Opportunity(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    satellite_id: str
    station_id: str
    antenna_id: str
    band: str
    start_at: str
    end_at: str
    predicted_rate_bps: int

class Contact(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    job_id: str
    satellite_id: str
    station_id: str
    antenna_id: str
    opportunity_id: str
    band: str
    window_start_at: str
    window_end_at: str
    setup_start_at: str
    start_at: str
    end_at: str
    expected_rate_bps: int
    allocated_bytes: int
    transferred_bytes: int
    status: ContactStatus
    authorization_status: AuthorizationStatus
    schedule_version: int
    reasons: List[Reason]

class ScheduleChange(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    schedule_version: int
    job_id: str
    old_contact_ids: List[str]
    new_contact_ids: List[str]
    reasons: List[Reason]
    created_at: str

class DisruptionEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    type: Literal["rain", "station_outage", "station_recovery"]
    station_id: str
    capacity_factor: Optional[float] = None
    status: Literal["pending", "applied", "failed"]
    occurred_at: str
    operation_id: Optional[str] = None
    reasons: List[Reason]

class Transfer(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    contact_id: str
    owner_org_id: str
    partner_station_id: str
    status: Literal["queued", "encrypting", "forwarding", "delivered", "verification_failed", "failed"]
    total_bytes: int
    forwarded_bytes: int
    ciphertext_sha256: Optional[str] = None
    expected_plaintext_sha256: Optional[str] = None
    owner_plaintext_sha256: Optional[str] = None
    integrity_status: Literal["pending", "verified", "failed"]
    owner_decryption_status: Literal["pending", "succeeded", "failed"]
    partner_key_access: Literal["not_provisioned", "unknown"]
    reasons: List[Reason]

class SecurityCheck(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    test_case: Literal["expired_authorization", "wrong_station", "tampered_payload"]
    status: Literal["queued", "running", "completed", "failed"]
    passed: Optional[bool] = None
    expected_outcome: str
    observed_outcome: Optional[str] = None
    reasons: List[Reason]

class SchedulerMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    requested_bytes: int
    delivered_before_deadline_bytes: int
    total_jobs: int
    on_time_jobs: int
    urgent_jobs: int
    urgent_on_time_jobs: int
    resource_conflicts: int
    scheduling_duration_ms: int
    bookings_changed: int

class Evaluation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    scenario_id: str
    workload_id: str
    event_trace_id: str
    status: Literal["queued", "running", "completed", "failed"]
    fifo: Optional[SchedulerMetrics] = None
    optimized: Optional[SchedulerMetrics] = None
    reasons: List[Reason]

class Operation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: Literal["schedule", "disruption", "simulation", "transfer", "security_check", "evaluation"]
    status: OperationStatus
    resource_id: Optional[str] = None
    submitted_at: str
    completed_at: Optional[str] = None
    reasons: List[Reason]

class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    actor_name: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    outcome: Literal["allowed", "denied", "succeeded", "failed"]
    message: str
    timestamp: str
    clock_basis: Literal["server", "simulation"]

class SimulatorState(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    connection_status: Literal["connected", "stale", "disconnected"]
    run_state: Literal["running", "paused", "stopped"]
    speed_multiplier: float
    last_heartbeat_at: Optional[str] = None

class Scenario(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    seed: int
    start_at: str
    end_at: str
    ready_for_evaluation: bool

class SnapshotServices(BaseModel):
    scheduler: Literal["ready", "unavailable"]
    security: Literal["ready", "unavailable"]

class SnapshotMeta(BaseModel):
    contract_version: Literal["orbitron.v1"] = "orbitron.v1"
    mode: Literal["simulation"] = "simulation"
    state_revision: int
    schedule_version: int
    server_time: str
    simulation_time: str
    visible_start_at: str
    visible_end_at: str
    services: SnapshotServices

class Snapshot(BaseModel):
    meta: SnapshotMeta
    user: User
    organizations: List[Organization]
    satellites: List[Satellite]
    stations: List[Station]
    jobs: List[Job]
    opportunities: List[Opportunity]
    contacts: List[Contact]
    schedule_changes: List[ScheduleChange]
    events: List[DisruptionEvent]
    transfers: List[Transfer]
    security_checks: List[SecurityCheck]
    evaluations: List[Evaluation]
    operations: List[Operation]
    audit: List[AuditEntry]
    simulator: SimulatorState
    scenario: Optional[Scenario] = None

class HealthResponse(BaseModel):
    service: str = "orbitron-backend"
    contract_version: str = "orbitron.v1"
    status: Literal["ready", "degraded"]
