export type ID = string;
export type ISODateTime = string;

export type Priority = "routine" | "high" | "emergency";
export type Role = "operator" | "network_admin";

export type JobStatus =
  | "pending"
  | "scheduled"
  | "active"
  | "completed"
  | "blocked"
  | "cancelled";

export type ContactStatus =
  | "tentative"
  | "confirmed"
  | "active"
  | "completed"
  | "failed"
  | "cancelled";

export type AuthorizationStatus =
  | "pending"
  | "allowed"
  | "denied"
  | "expired"
  | "revoked";

export type OperationStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed";

export interface Reason {
  code: string;
  message: string;
  resource_ids: ID[];
}

export interface Organization {
  id: ID;
  name: string;
}

export interface User {
  id: ID;
  display_name: string;
  email: string;
  organization_id: ID;
  role: Role;
}

export interface Session {
  user: User;
  csrf_token: string;
  expires_at: ISODateTime;
}

export interface Position {
  latitude_deg: number;
  longitude_deg: number;
  altitude_km: number;
  observed_at: ISODateTime;
}

export interface Satellite {
  id: ID;
  name: string;
  owner_org_id: ID;
  supported_bands: string[];
  max_downlink_rate_bps: number;
  max_parallel_contacts: number;
  onboard_bytes: number;

  operational_status:
    | "available"
    | "communicating"
    | "fault";

  telemetry_status:
    | "fresh"
    | "stale"
    | "never_seen";

  position: Position | null;
  last_telemetry_at: ISODateTime | null;

  source: "simulated";
  orbit_source: "public_tle" | "synthetic";
  orbit_epoch_at: ISODateTime | null;
}

export interface Antenna {
  id: ID;
  name: string;
  supported_bands: string[];
  max_rate_bps: number;
  setup_seconds: number;
  status: "available" | "maintenance" | "offline";
}

export interface Station {
  id: ID;
  name: string;
  owner_org_id: ID;

  latitude_deg: number;
  longitude_deg: number;
  min_elevation_deg: number;

  operational_status: "online" | "degraded" | "offline";
  connection_status: "connected" | "stale" | "disconnected";
  weather_capacity_factor: number;

  sharing_enabled: boolean;
  approved_partner_org_ids: ID[];

  antennas: Antenna[];
  last_heartbeat_at: ISODateTime | null;
}

export interface Job {
  id: ID;
  satellite_id: ID;
  owner_org_id: ID;

  requested_bytes: number;
  delivered_bytes: number;
  remaining_bytes: number;

  priority: Priority;
  deadline_at: ISODateTime;
  allow_split: boolean;
  status: JobStatus;

  reasons: Reason[];
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface Opportunity {
  id: ID;
  satellite_id: ID;
  station_id: ID;
  antenna_id: ID;
  band: string;

  start_at: ISODateTime;
  end_at: ISODateTime;
  predicted_rate_bps: number;
}

export interface Contact {
  id: ID;
  job_id: ID;
  satellite_id: ID;
  station_id: ID;
  antenna_id: ID;
  opportunity_id: ID;
  band: string;

  window_start_at: ISODateTime;
  window_end_at: ISODateTime;

  setup_start_at: ISODateTime;
  start_at: ISODateTime;
  end_at: ISODateTime;

  expected_rate_bps: number;
  allocated_bytes: number;
  transferred_bytes: number;

  status: ContactStatus;
  authorization_status: AuthorizationStatus;
  schedule_version: number;
  reasons: Reason[];
}

export interface ScheduleChange {
  id: ID;
  schedule_version: number;
  job_id: ID;
  old_contact_ids: ID[];
  new_contact_ids: ID[];
  reasons: Reason[];
  created_at: ISODateTime;
}

export interface DisruptionEvent {
  id: ID;

  type:
    | "rain"
    | "station_outage"
    | "station_recovery";

  station_id: ID;
  capacity_factor: number | null;

  status: "pending" | "applied" | "failed";
  occurred_at: ISODateTime;
  operation_id: ID | null;
  reasons: Reason[];
}

export interface Transfer {
  id: ID;
  contact_id: ID;
  owner_org_id: ID;
  partner_station_id: ID;

  status:
    | "queued"
    | "encrypting"
    | "forwarding"
    | "delivered"
    | "verification_failed"
    | "failed";

  total_bytes: number;
  forwarded_bytes: number;

  ciphertext_sha256: string | null;
  expected_plaintext_sha256: string | null;
  owner_plaintext_sha256: string | null;

  integrity_status: "pending" | "verified" | "failed";
  owner_decryption_status: "pending" | "succeeded" | "failed";

  partner_key_access: "not_provisioned" | "unknown";
  reasons: Reason[];
}

export interface SecurityCheck {
  id: ID;

  test_case:
    | "expired_authorization"
    | "wrong_station"
    | "tampered_payload";

  status: "queued" | "running" | "completed" | "failed";

  passed: boolean | null;
  expected_outcome: string;
  observed_outcome: string | null;
  reasons: Reason[];
}

export interface SchedulerMetrics {
  requested_bytes: number;
  delivered_before_deadline_bytes: number;
  total_jobs: number;
  on_time_jobs: number;
  urgent_jobs: number;
  urgent_on_time_jobs: number;
  resource_conflicts: number;
  scheduling_duration_ms: number;
  bookings_changed: number;
}

export interface Evaluation {
  id: ID;
  scenario_id: ID;
  workload_id: ID;
  event_trace_id: ID;

  status: "queued" | "running" | "completed" | "failed";

  fifo: SchedulerMetrics | null;
  optimized: SchedulerMetrics | null;

  reasons: Reason[];
}

export interface Operation {
  id: ID;

  kind:
    | "schedule"
    | "disruption"
    | "simulation"
    | "transfer"
    | "security_check"
    | "evaluation";

  status: OperationStatus;
  resource_id: ID | null;

  submitted_at: ISODateTime;
  completed_at: ISODateTime | null;
  reasons: Reason[];
}

export interface AuditEntry {
  id: ID;
  actor_name: string;
  action: string;
  resource_type: string;
  resource_id: ID | null;
  outcome: "allowed" | "denied" | "succeeded" | "failed";
  message: string;

  timestamp: ISODateTime;
  clock_basis: "server" | "simulation";
}

export interface SimulatorState {
  connection_status: "connected" | "stale" | "disconnected";
  run_state: "running" | "paused" | "stopped";
  speed_multiplier: number;
  last_heartbeat_at: ISODateTime | null;
}

export interface Scenario {
  id: ID;
  name: string;
  seed: number;
  start_at: ISODateTime;
  end_at: ISODateTime;
  ready_for_evaluation: boolean;
}

export interface SnapshotMeta {
  contract_version: "orbitron.v1";
  mode: "simulation";

  state_revision: number;
  schedule_version: number;

  server_time: ISODateTime;
  simulation_time: ISODateTime;

  visible_start_at: ISODateTime;
  visible_end_at: ISODateTime;

  services: {
    scheduler: "ready" | "unavailable";
    security: "ready" | "unavailable";
  };
}

export interface Snapshot {
  meta: SnapshotMeta;

  user: User;
  organizations: Organization[];
  satellites: Satellite[];
  stations: Station[];
  jobs: Job[];
  opportunities: Opportunity[];
  contacts: Contact[];
  schedule_changes: ScheduleChange[];
  events: DisruptionEvent[];
  transfers: Transfer[];
  security_checks: SecurityCheck[];
  evaluations: Evaluation[];
  operations: Operation[];
  audit: AuditEntry[];

  simulator: SimulatorState;
  scenario: Scenario | null;
}

export interface ApiErrorDetail {
  field: string;
  message: string;
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    details: ApiErrorDetail[];
    request_id: string;
  };
}

export interface HealthResponse {
  service: string;
  contract_version: string;
  status: "ready" | "degraded";
}

// DTOs for requests
export interface LoginRequest {
  email: string;
  password: string;
}

export interface CreateJobRequest {
  satellite_id: ID;
  data_bytes: number;
  deadline_at: ISODateTime;
  priority: Priority;
  allow_split: boolean;
}

export interface RunScheduleRequest {
  algorithm: "optimized";
  expected_schedule_version: number;
}

export interface CreateDisruptionEventRequest {
  type: "rain" | "station_outage" | "station_recovery";
  station_id: ID;
  capacity_factor: number | null;
  expected_schedule_version: number;
}

export interface SimulationActionRequest {
  action: "pause" | "resume" | "step" | "reset";
  step_seconds?: number;
  seed?: number;
}

export interface CreateTransferRequest {
  contact_id: ID;
}

export interface RunSecurityCheckRequest {
  test_case: "expired_authorization" | "wrong_station" | "tampered_payload";
  contact_id: ID;
}

export interface RunEvaluationRequest {
  scenario_id: ID;
}
