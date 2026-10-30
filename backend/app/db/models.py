from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON, Index
)
from sqlalchemy.orm import relationship
from app.db.session import Base

def utc_now():
    return datetime.now(timezone.utc)

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    satellites = relationship("Satellite", back_populates="owner_org", cascade="all, delete-orphan")
    stations = relationship("Station", back_populates="owner_org", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="owner_org", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)  # operator | network_admin
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    organization = relationship("Organization", back_populates="users")
    sessions = relationship("SessionModel", back_populates="user", cascade="all, delete-orphan")


class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    session_token_hash = Column(String, unique=True, index=True, nullable=False)
    csrf_token = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="sessions")


class ServicePrincipal(Base):
    __tablename__ = "service_principals"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)  # simulator_controller, satellite, station_gateway, owner_receiver
    organization_id = Column(String, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    permitted_resources_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    credentials = relationship("ServiceCredential", back_populates="principal", cascade="all, delete-orphan")
    commands = relationship("ServiceCommand", back_populates="principal", cascade="all, delete-orphan")


class ServiceCredential(Base):
    __tablename__ = "service_credentials"

    id = Column(String, primary_key=True)
    principal_id = Column(String, ForeignKey("service_principals.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String, unique=True, index=True, nullable=False)
    scope = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    principal = relationship("ServicePrincipal", back_populates="credentials")


class Satellite(Base):
    __tablename__ = "satellites"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    owner_org_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    supported_bands_json = Column(JSON, default=list, nullable=False)
    max_downlink_rate_bps = Column(Integer, nullable=False)
    max_parallel_contacts = Column(Integer, default=1, nullable=False)
    onboard_bytes = Column(Integer, default=0, nullable=False)
    reserved_bytes = Column(Integer, default=0, nullable=False)

    operational_status = Column(String, default="available", nullable=False)  # available | communicating | fault
    telemetry_status = Column(String, default="never_seen", nullable=False)    # fresh | stale | never_seen

    position_lat = Column(Float, nullable=True)
    position_lon = Column(Float, nullable=True)
    position_alt = Column(Float, nullable=True)
    position_observed_at = Column(DateTime(timezone=True), nullable=True)

    last_telemetry_at = Column(DateTime(timezone=True), nullable=True)
    source = Column(String, default="simulated", nullable=False)
    orbit_source = Column(String, default="synthetic", nullable=False)  # public_tle | synthetic
    orbit_epoch_at = Column(DateTime(timezone=True), nullable=True)
    generated_bytes_total = Column(Integer, default=0, nullable=False)
    version = Column(Integer, default=1, nullable=False)

    owner_org = relationship("Organization", back_populates="satellites")
    orbits = relationship("SatelliteOrbit", back_populates="satellite", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="satellite", cascade="all, delete-orphan")


class SatelliteOrbit(Base):
    __tablename__ = "satellite_orbits"

    id = Column(String, primary_key=True)
    satellite_id = Column(String, ForeignKey("satellites.id", ondelete="CASCADE"), nullable=False)
    format = Column(String, default="tle", nullable=False)
    line1 = Column(String, nullable=False)
    line2 = Column(String, nullable=False)
    epoch_at = Column(DateTime(timezone=True), nullable=False)
    orbit_source = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    satellite = relationship("Satellite", back_populates="orbits")


class SatelliteObservation(Base):
    __tablename__ = "satellite_observations"

    id = Column(String, primary_key=True)
    event_id = Column(String, nullable=False)
    scenario_id = Column(String, nullable=False)
    satellite_id = Column(String, ForeignKey("satellites.id", ondelete="CASCADE"), nullable=False)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    operational_status = Column(String, nullable=False)
    position_lat = Column(Float, nullable=True)
    position_lon = Column(Float, nullable=True)
    position_alt = Column(Float, nullable=True)
    generated_bytes_total = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class Station(Base):
    __tablename__ = "stations"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    owner_org_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    latitude_deg = Column(Float, nullable=False)
    longitude_deg = Column(Float, nullable=False)
    min_elevation_deg = Column(Float, default=5.0, nullable=False)

    operational_status = Column(String, default="online", nullable=False)  # online | degraded | offline
    connection_status = Column(String, default="disconnected", nullable=False)  # connected | stale | disconnected
    weather_capacity_factor = Column(Float, default=1.0, nullable=False)
    sharing_enabled = Column(Boolean, default=False, nullable=False)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, default=1, nullable=False)

    owner_org = relationship("Organization", back_populates="stations")
    antennas = relationship("Antenna", back_populates="station", cascade="all, delete-orphan")
    partner_permissions = relationship("StationPartnerPermission", back_populates="station", cascade="all, delete-orphan")


class Antenna(Base):
    __tablename__ = "antennas"

    id = Column(String, primary_key=True)
    station_id = Column(String, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    supported_bands_json = Column(JSON, default=list, nullable=False)
    max_rate_bps = Column(Integer, nullable=False)
    setup_seconds = Column(Integer, default=60, nullable=False)
    status = Column(String, default="available", nullable=False)  # available | maintenance | offline

    station = relationship("Station", back_populates="antennas")


class StationPartnerPermission(Base):
    __tablename__ = "station_partner_permissions"

    id = Column(String, primary_key=True)
    station_id = Column(String, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False)
    partner_org_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    station = relationship("Station", back_populates="partner_permissions")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    satellite_id = Column(String, ForeignKey("satellites.id", ondelete="CASCADE"), nullable=False)
    owner_org_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)

    requested_bytes = Column(Integer, nullable=False)
    delivered_bytes = Column(Integer, default=0, nullable=False)
    remaining_bytes = Column(Integer, nullable=False)

    priority = Column(String, nullable=False)  # routine | high | emergency
    deadline_at = Column(DateTime(timezone=True), nullable=False)
    allow_split = Column(Boolean, default=True, nullable=False)
    status = Column(String, default="pending", nullable=False)  # pending | scheduled | active | completed | blocked | cancelled

    reasons_json = Column(JSON, default=list, nullable=False)
    arrival_sequence = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

    satellite = relationship("Satellite", back_populates="jobs")
    owner_org = relationship("Organization", back_populates="jobs")
    contacts = relationship("Contact", back_populates="job", cascade="all, delete-orphan")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(String, primary_key=True)
    scenario_id = Column(String, nullable=False)
    satellite_id = Column(String, ForeignKey("satellites.id", ondelete="CASCADE"), nullable=False)
    station_id = Column(String, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False)
    antenna_id = Column(String, ForeignKey("antennas.id", ondelete="CASCADE"), nullable=False)
    band = Column(String, nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    predicted_rate_bps = Column(Integer, nullable=False)


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(String, primary_key=True)
    job_id = Column(String, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    satellite_id = Column(String, ForeignKey("satellites.id", ondelete="CASCADE"), nullable=False)
    station_id = Column(String, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False)
    antenna_id = Column(String, ForeignKey("antennas.id", ondelete="CASCADE"), nullable=False)
    opportunity_id = Column(String, ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False)
    band = Column(String, nullable=False)

    window_start_at = Column(DateTime(timezone=True), nullable=False)
    window_end_at = Column(DateTime(timezone=True), nullable=False)

    setup_start_at = Column(DateTime(timezone=True), nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)

    expected_rate_bps = Column(Integer, nullable=False)
    allocated_bytes = Column(Integer, nullable=False)
    transferred_bytes = Column(Integer, default=0, nullable=False)

    status = Column(String, default="tentative", nullable=False)  # tentative | confirmed | active | completed | failed | cancelled
    authorization_status = Column(String, default="pending", nullable=False)  # pending | allowed | denied | expired | revoked
    schedule_version = Column(Integer, default=0, nullable=False)
    reasons_json = Column(JSON, default=list, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    job = relationship("Job", back_populates="contacts")
    authorizations = relationship("ContactAuthorization", back_populates="contact", cascade="all, delete-orphan")
    progress_reports = relationship("ContactProgress", back_populates="contact", cascade="all, delete-orphan")
    transfers = relationship("Transfer", back_populates="contact", cascade="all, delete-orphan")


class ContactAuthorization(Base):
    __tablename__ = "contact_authorizations"

    id = Column(String, primary_key=True)
    contact_id = Column(String, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    allowed = Column(Boolean, nullable=False)
    reasons_json = Column(JSON, default=list, nullable=False)
    scope_json = Column(JSON, default=dict, nullable=False)
    expires_at_server = Column(DateTime(timezone=True), nullable=True)
    expires_at_sim = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    contact = relationship("Contact", back_populates="authorizations")


class ContactProgress(Base):
    __tablename__ = "contact_progress"

    id = Column(String, primary_key=True)
    event_id = Column(String, nullable=False)
    scenario_id = Column(String, nullable=False)
    contact_id = Column(String, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    interval_start_at = Column(DateTime(timezone=True), nullable=False)
    interval_end_at = Column(DateTime(timezone=True), nullable=False)
    cumulative_transferred_bytes = Column(Integer, nullable=False)
    delta_bytes = Column(Integer, nullable=False)
    is_final = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    contact = relationship("Contact", back_populates="progress_reports")


class ScheduleChange(Base):
    __tablename__ = "schedule_changes"

    id = Column(String, primary_key=True)
    schedule_version = Column(Integer, nullable=False)
    job_id = Column(String, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    old_contact_ids_json = Column(JSON, default=list, nullable=False)
    new_contact_ids_json = Column(JSON, default=list, nullable=False)
    reasons_json = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class DisruptionEvent(Base):
    __tablename__ = "disruption_events"

    id = Column(String, primary_key=True)
    type = Column(String, nullable=False)  # rain | station_outage | station_recovery
    station_id = Column(String, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False)
    capacity_factor = Column(Float, nullable=True)
    status = Column(String, default="pending", nullable=False)  # pending | applied | failed
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    operation_id = Column(String, nullable=True)
    reasons_json = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class Transfer(Base):
    __tablename__ = "transfers"

    id = Column(String, primary_key=True)
    contact_id = Column(String, ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    owner_org_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    partner_station_id = Column(String, ForeignKey("stations.id", ondelete="CASCADE"), nullable=False)

    status = Column(String, default="queued", nullable=False)  # queued | encrypting | forwarding | delivered | verification_failed | failed
    total_bytes = Column(Integer, nullable=False)
    forwarded_bytes = Column(Integer, default=0, nullable=False)

    ciphertext_sha256 = Column(String, nullable=True)
    expected_plaintext_sha256 = Column(String, nullable=True)
    owner_plaintext_sha256 = Column(String, nullable=True)

    integrity_status = Column(String, default="pending", nullable=False)  # pending | verified | failed
    owner_decryption_status = Column(String, default="pending", nullable=False)  # pending | succeeded | failed

    partner_key_access = Column(String, default="not_provisioned", nullable=False)  # not_provisioned | unknown
    reasons_json = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    contact = relationship("Contact", back_populates="transfers")


class SecurityCheck(Base):
    __tablename__ = "security_checks"

    id = Column(String, primary_key=True)
    test_case = Column(String, nullable=False)  # expired_authorization | wrong_station | tampered_payload
    contact_id = Column(String, nullable=True)
    status = Column(String, default="queued", nullable=False)  # queued | running | completed | failed
    passed = Column(Boolean, nullable=True)
    expected_outcome = Column(String, nullable=False)
    observed_outcome = Column(String, nullable=True)
    reasons_json = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class Operation(Base):
    __tablename__ = "operations"

    id = Column(String, primary_key=True)
    kind = Column(String, nullable=False)  # schedule | disruption | simulation | transfer | security_check | evaluation
    status = Column(String, default="queued", nullable=False)  # queued | running | succeeded | failed
    resource_id = Column(String, nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    reasons_json = Column(JSON, default=list, nullable=False)
    payload_json = Column(JSON, nullable=True)
    created_by_user_id = Column(String, nullable=True)


class ServiceCommand(Base):
    __tablename__ = "service_commands"

    id = Column(String, primary_key=True)
    principal_id = Column(String, ForeignKey("service_principals.id", ondelete="CASCADE"), nullable=False)
    command_type = Column(String, nullable=False)  # confirm_contact | forward_transfer | decrypt_transfer
    contact_id = Column(String, nullable=True)
    transfer_id = Column(String, nullable=True)
    payload_json = Column(JSON, default=dict, nullable=False)
    status = Column(String, default="pending", nullable=False)  # pending | acknowledged | completed | failed
    result_json = Column(JSON, nullable=True)
    reasons_json = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    principal = relationship("ServicePrincipal", back_populates="commands")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(String, primary_key=True)
    scenario_id = Column(String, nullable=False)
    workload_id = Column(String, nullable=False)
    event_trace_id = Column(String, nullable=False)
    status = Column(String, default="queued", nullable=False)  # queued | running | completed | failed
    fifo_metrics_json = Column(JSON, nullable=True)
    optimized_metrics_json = Column(JSON, nullable=True)
    reasons_json = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id = Column(String, primary_key=True)
    actor_name = Column(String, nullable=False)
    action = Column(String, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_id = Column(String, nullable=True)
    outcome = Column(String, nullable=False)  # allowed | denied | succeeded | failed
    message = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    clock_basis = Column(String, default="server", nullable=False)  # server | simulation


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id = Column(String, primary_key=True)
    key = Column(String, index=True, nullable=False)
    principal = Column(String, nullable=False)
    route = Column(String, nullable=False)
    request_hash = Column(String, nullable=False)
    scenario_id = Column(String, nullable=False)
    status_code = Column(Integer, nullable=False)
    response_body = Column(Text, nullable=False)
    resource_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class IngestionEvent(Base):
    __tablename__ = "ingestion_events"

    id = Column(String, primary_key=True)
    scenario_id = Column(String, nullable=False)
    principal_id = Column(String, nullable=False)
    event_id = Column(String, nullable=False)
    endpoint = Column(String, nullable=False)
    payload_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_ingestion_dedup", "scenario_id", "principal_id", "event_id", unique=True),
    )


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    seed = Column(Integer, nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    ready_for_evaluation = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class ApplicationState(Base):
    __tablename__ = "application_state"

    id = Column(Integer, primary_key=True, default=1)
    contract_version = Column(String, default="orbitron.v1", nullable=False)
    mode = Column(String, default="simulation", nullable=False)
    state_revision = Column(Integer, default=1, nullable=False)
    schedule_version = Column(Integer, default=0, nullable=False)
    planning_revision = Column(Integer, default=0, nullable=False)
    simulation_time = Column(DateTime(timezone=True), nullable=False)
    simulation_run_state = Column(String, default="paused", nullable=False)  # running | paused | stopped
    simulation_speed_multiplier = Column(Float, default=1.0, nullable=False)
    current_scenario_id = Column(String, ForeignKey("scenario_runs.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
