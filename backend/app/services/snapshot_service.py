from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Set
from sqlalchemy.orm import Session as DBSession

from app.db.models import (
    User as DBUser, Organization as DBOrg, Satellite as DBSatellite,
    Station as DBStation, Antenna as DBAntenna, StationPartnerPermission as DBStationPartner,
    Job as DBJob, Opportunity as DBOpportunity, Contact as DBContact,
    ScheduleChange as DBScheduleChange, DisruptionEvent as DBDisruptionEvent,
    Transfer as DBTransfer, SecurityCheck as DBSecurityCheck, Evaluation as DBEvaluation,
    Operation as DBOperation, AuditEntry as DBAuditEntry, ApplicationState, ScenarioRun
)
from app.schemas.public import (
    Snapshot, SnapshotMeta, SnapshotServices, SimulatorState, Scenario as PublicScenario,
    User as PublicUser, Organization as PublicOrg, Satellite as PublicSatellite,
    Station as PublicStation, Antenna as PublicAntenna, Job as PublicJob,
    Opportunity as PublicOpportunity, Contact as PublicContact, ScheduleChange as PublicScheduleChange,
    DisruptionEvent as PublicDisruptionEvent, Transfer as PublicTransfer, SecurityCheck as PublicSecurityCheck,
    Evaluation as PublicEvaluation, Operation as PublicOperation, AuditEntry as PublicAuditEntry,
    Reason, Position as PublicPosition, SchedulerMetrics, to_iso_z
)
from app.adapters.scheduler import SchedulerAdapter
from app.adapters.security import SecurityAdapter

def parse_iso_z(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)

class SnapshotService:
    @classmethod
    def get_app_state(cls, db: DBSession) -> ApplicationState:
        state = db.query(ApplicationState).filter(ApplicationState.id == 1).first()
        if not state:
            now = datetime.now(timezone.utc)
            state = ApplicationState(
                id=1,
                contract_version="orbitron.v1",
                mode="simulation",
                state_revision=1,
                schedule_version=0,
                planning_revision=0,
                simulation_time=now,
                simulation_run_state="paused",
                simulation_speed_multiplier=1.0,
                updated_at=now
            )
            db.add(state)
            db.commit()
            db.refresh(state)
        return state

    @classmethod
    def assemble_snapshot(
        cls,
        db: DBSession,
        current_user: DBUser,
        from_at_str: Optional[str] = None,
        to_at_str: Optional[str] = None
    ) -> Snapshot:
        app_state = cls.get_app_state(db)
        server_now = datetime.now(timezone.utc)

        sim_time = app_state.simulation_time
        if sim_time.tzinfo is None:
            sim_time = sim_time.replace(tzinfo=timezone.utc)

        # Horizon calculation
        if from_at_str and to_at_str:
            vis_start = parse_iso_z(from_at_str)
            vis_end = parse_iso_z(to_at_str)
        else:
            vis_start = sim_time - timedelta(minutes=15)
            vis_end = sim_time + timedelta(hours=6)

        is_admin = current_user.role == "network_admin"
        user_org_id = current_user.organization_id

        # Query all organizations
        all_orgs = db.query(DBOrg).order_by(DBOrg.id).all()
        public_orgs = [PublicOrg(id=o.id, name=o.name) for o in all_orgs]

        # Query all stations
        all_stations = db.query(DBStation).order_by(DBStation.id).all()
        permitted_station_ids: Set[str] = set()
        public_stations: List[PublicStation] = []

        for st in all_stations:
            partners = [p.partner_org_id for p in st.partner_permissions]
            has_access = is_admin or (st.owner_org_id == user_org_id) or (st.sharing_enabled and user_org_id in partners)
            if has_access:
                permitted_station_ids.add(st.id)

            # Calculate station connection status based on server time
            conn_status = "disconnected"
            last_hb_iso = None
            if st.last_heartbeat_at:
                hb = st.last_heartbeat_at
                if hb.tzinfo is None:
                    hb = hb.replace(tzinfo=timezone.utc)
                last_hb_iso = to_iso_z(hb)
                diff_sec = (server_now - hb).total_seconds()
                if diff_sec <= 60:
                    conn_status = "connected"
                elif diff_sec <= 180:
                    conn_status = "stale"
                else:
                    conn_status = "disconnected"

            antennas = [
                PublicAntenna(
                    id=a.id,
                    name=a.name,
                    supported_bands=a.supported_bands_json or [],
                    max_rate_bps=a.max_rate_bps,
                    setup_seconds=a.setup_seconds,
                    status=a.status
                )
                for a in st.antennas
            ]

            if has_access or is_admin:
                public_stations.append(
                    PublicStation(
                        id=st.id,
                        name=st.name,
                        owner_org_id=st.owner_org_id,
                        latitude_deg=st.latitude_deg,
                        longitude_deg=st.longitude_deg,
                        min_elevation_deg=st.min_elevation_deg,
                        operational_status=st.operational_status,
                        connection_status=conn_status,
                        weather_capacity_factor=st.weather_capacity_factor,
                        sharing_enabled=st.sharing_enabled,
                        approved_partner_org_ids=partners,
                        antennas=antennas,
                        last_heartbeat_at=last_hb_iso
                    )
                )

        # Query Satellites
        all_sats = db.query(DBSatellite).order_by(DBSatellite.id).all()
        permitted_sat_ids: Set[str] = set()
        public_satellites: List[PublicSatellite] = []

        for sat in all_sats:
            has_sat_access = is_admin or (sat.owner_org_id == user_org_id)
            if has_sat_access:
                permitted_sat_ids.add(sat.id)

            # Calculate telemetry status using simulation time
            telem_status = "never_seen"
            last_telem_iso = None
            pos_obj = None

            if sat.last_telemetry_at:
                telem_time = sat.last_telemetry_at
                if telem_time.tzinfo is None:
                    telem_time = telem_time.replace(tzinfo=timezone.utc)
                last_telem_iso = to_iso_z(telem_time)
                diff = (sim_time - telem_time).total_seconds()
                if diff <= 300:
                    telem_status = "fresh"
                else:
                    telem_status = "stale"

            if sat.position_lat is not None and sat.position_lon is not None and sat.position_alt is not None and sat.position_observed_at:
                pos_obj = PublicPosition(
                    latitude_deg=sat.position_lat,
                    longitude_deg=sat.position_lon,
                    altitude_km=sat.position_alt,
                    observed_at=to_iso_z(sat.position_observed_at)
                )

            if has_sat_access or is_admin:
                public_satellites.append(
                    PublicSatellite(
                        id=sat.id,
                        name=sat.name,
                        owner_org_id=sat.owner_org_id,
                        supported_bands=sat.supported_bands_json or [],
                        max_downlink_rate_bps=sat.max_downlink_rate_bps,
                        max_parallel_contacts=sat.max_parallel_contacts,
                        onboard_bytes=sat.onboard_bytes,
                        operational_status=sat.operational_status,
                        telemetry_status=telem_status,
                        position=pos_obj,
                        last_telemetry_at=last_telem_iso,
                        source="simulated",
                        orbit_source=sat.orbit_source,
                        orbit_epoch_at=to_iso_z(sat.orbit_epoch_at)
                    )
                )

        # Query Jobs
        job_query = db.query(DBJob).order_by(DBJob.created_at)
        if not is_admin:
            job_query = job_query.filter(DBJob.owner_org_id == user_org_id)
        all_jobs = job_query.all()
        visible_job_ids = {j.id for j in all_jobs}

        public_jobs = [
            PublicJob(
                id=j.id,
                satellite_id=j.satellite_id,
                owner_org_id=j.owner_org_id,
                requested_bytes=j.requested_bytes,
                delivered_bytes=j.delivered_bytes,
                remaining_bytes=j.remaining_bytes,
                priority=j.priority,
                deadline_at=to_iso_z(j.deadline_at),
                allow_split=j.allow_split,
                status=j.status,
                reasons=[Reason(**r) for r in (j.reasons_json or [])],
                created_at=to_iso_z(j.created_at),
                updated_at=to_iso_z(j.updated_at)
            )
            for j in all_jobs
        ]

        # Query Opportunities (bounded by horizon & permitted satellites/stations)
        opp_query = db.query(DBOpportunity).filter(
            DBOpportunity.start_at <= vis_end,
            DBOpportunity.end_at >= vis_start
        ).order_by(DBOpportunity.start_at)
        all_opps = opp_query.all()

        public_opps = [
            PublicOpportunity(
                id=o.id,
                satellite_id=o.satellite_id,
                station_id=o.station_id,
                antenna_id=o.antenna_id,
                band=o.band,
                start_at=to_iso_z(o.start_at),
                end_at=to_iso_z(o.end_at),
                predicted_rate_bps=o.predicted_rate_bps
            )
            for o in all_opps
            if is_admin or (o.satellite_id in permitted_sat_ids and o.station_id in permitted_station_ids)
        ]

        # Query Contacts
        contact_query = db.query(DBContact).order_by(DBContact.start_at)
        all_contacts = contact_query.all()

        # Contacts directly visible: job is visible or station is permitted
        visible_contact_map: Dict[str, DBContact] = {}
        for c in all_contacts:
            has_c_access = is_admin or (c.job_id in visible_job_ids) or (c.station_id in permitted_station_ids)
            if has_c_access:
                # Horizon check: falls within horizon
                c_start = c.start_at if c.start_at.tzinfo else c.start_at.replace(tzinfo=timezone.utc)
                c_end = c.end_at if c.end_at.tzinfo else c.end_at.replace(tzinfo=timezone.utc)
                if c_start <= vis_end and c_end >= vis_start:
                    visible_contact_map[c.id] = c

        # Query Schedule Changes
        sc_query = db.query(DBScheduleChange).order_by(DBScheduleChange.created_at)
        all_sc = sc_query.all()
        public_sc: List[PublicScheduleChange] = []
        referenced_contact_ids: Set[str] = set()

        for sc in all_sc:
            if is_admin or (sc.job_id in visible_job_ids):
                public_sc.append(
                    PublicScheduleChange(
                        id=sc.id,
                        schedule_version=sc.schedule_version,
                        job_id=sc.job_id,
                        old_contact_ids=sc.old_contact_ids_json or [],
                        new_contact_ids=sc.new_contact_ids_json or [],
                        reasons=[Reason(**r) for r in (sc.reasons_json or [])],
                        created_at=to_iso_z(sc.created_at)
                    )
                )
                for cid in (sc.old_contact_ids_json or []) + (sc.new_contact_ids_json or []):
                    referenced_contact_ids.add(cid)

        # Include referenced contacts for closure
        for c in all_contacts:
            if c.id in referenced_contact_ids:
                has_c_access = is_admin or (c.job_id in visible_job_ids) or (c.station_id in permitted_station_ids)
                if has_c_access:
                    visible_contact_map[c.id] = c

        public_contacts = [
            PublicContact(
                id=c.id,
                job_id=c.job_id,
                satellite_id=c.satellite_id,
                station_id=c.station_id,
                antenna_id=c.antenna_id,
                opportunity_id=c.opportunity_id,
                band=c.band,
                window_start_at=to_iso_z(c.window_start_at),
                window_end_at=to_iso_z(c.window_end_at),
                setup_start_at=to_iso_z(c.setup_start_at),
                start_at=to_iso_z(c.start_at),
                end_at=to_iso_z(c.end_at),
                expected_rate_bps=c.expected_rate_bps,
                allocated_bytes=c.allocated_bytes,
                transferred_bytes=c.transferred_bytes,
                status=c.status,
                authorization_status=c.authorization_status,
                schedule_version=c.schedule_version,
                reasons=[Reason(**r) for r in (c.reasons_json or [])]
            )
            for c in visible_contact_map.values()
        ]

        # Query Events
        events_query = db.query(DBDisruptionEvent).order_by(DBDisruptionEvent.occurred_at).all()
        public_events = [
            PublicDisruptionEvent(
                id=e.id,
                type=e.type,
                station_id=e.station_id,
                capacity_factor=e.capacity_factor,
                status=e.status,
                occurred_at=to_iso_z(e.occurred_at),
                operation_id=e.operation_id,
                reasons=[Reason(**r) for r in (e.reasons_json or [])]
            )
            for e in events_query
            if is_admin or (e.station_id in permitted_station_ids)
        ]

        # Query Transfers
        transfers_query = db.query(DBTransfer).order_by(DBTransfer.created_at).all()
        public_transfers = [
            PublicTransfer(
                id=t.id,
                contact_id=t.contact_id,
                owner_org_id=t.owner_org_id,
                partner_station_id=t.partner_station_id,
                status=t.status,
                total_bytes=t.total_bytes,
                forwarded_bytes=t.forwarded_bytes,
                ciphertext_sha256=t.ciphertext_sha256,
                expected_plaintext_sha256=t.expected_plaintext_sha256,
                owner_plaintext_sha256=t.owner_plaintext_sha256,
                integrity_status=t.integrity_status,
                owner_decryption_status=t.owner_decryption_status,
                partner_key_access=t.partner_key_access,
                reasons=[Reason(**r) for r in (t.reasons_json or [])]
            )
            for t in transfers_query
            if is_admin or (t.owner_org_id == user_org_id or t.partner_station_id in permitted_station_ids)
        ]

        # Query Security Checks
        checks_query = db.query(DBSecurityCheck).order_by(DBSecurityCheck.created_at).all()
        public_checks = [
            PublicSecurityCheck(
                id=ck.id,
                test_case=ck.test_case,
                status=ck.status,
                passed=ck.passed,
                expected_outcome=ck.expected_outcome,
                observed_outcome=ck.observed_outcome,
                reasons=[Reason(**r) for r in (ck.reasons_json or [])]
            )
            for ck in checks_query
        ]

        # Query Evaluations
        evals_query = db.query(DBEvaluation).order_by(DBEvaluation.created_at).all()
        public_evals = [
            PublicEvaluation(
                id=ev.id,
                scenario_id=ev.scenario_id,
                workload_id=ev.workload_id,
                event_trace_id=ev.event_trace_id,
                status=ev.status,
                fifo=SchedulerMetrics(**ev.fifo_metrics_json) if ev.fifo_metrics_json else None,
                optimized=SchedulerMetrics(**ev.optimized_metrics_json) if ev.optimized_metrics_json else None,
                reasons=[Reason(**r) for r in (ev.reasons_json or [])]
            )
            for ev in evals_query
        ]

        # Query Operations
        ops_query = db.query(DBOperation).order_by(DBOperation.submitted_at).all()
        public_ops = [
            PublicOperation(
                id=op.id,
                kind=op.kind,
                status=op.status,
                resource_id=op.resource_id,
                submitted_at=to_iso_z(op.submitted_at),
                completed_at=to_iso_z(op.completed_at) if op.completed_at else None,
                reasons=[Reason(**r) for r in (op.reasons_json or [])]
            )
            for op in ops_query
            if is_admin or (op.created_by_user_id == current_user.id or op.kind in ["simulation", "schedule", "disruption"])
        ]

        # Query Audit Entries
        audit_query = db.query(DBAuditEntry).order_by(DBAuditEntry.timestamp.desc()).limit(100).all()
        public_audit = [
            PublicAuditEntry(
                id=a.id,
                actor_name=a.actor_name,
                action=a.action,
                resource_type=a.resource_type,
                resource_id=a.resource_id,
                outcome=a.outcome,
                message=a.message,
                timestamp=to_iso_z(a.timestamp),
                clock_basis=a.clock_basis
            )
            for a in audit_query
        ]

        # Query Simulator State
        sim_controller = db.query(DBUser).filter(DBUser.role == "network_admin").first()
        sim_conn = "connected" if app_state.simulation_run_state != "stopped" else "disconnected"
        sim_state = SimulatorState(
            connection_status=sim_conn,
            run_state=app_state.simulation_run_state,
            speed_multiplier=app_state.simulation_speed_multiplier,
            last_heartbeat_at=to_iso_z(server_now)
        )

        # Scenario
        sc_obj = None
        if app_state.current_scenario_id:
            db_sc = db.query(ScenarioRun).filter(ScenarioRun.id == app_state.current_scenario_id).first()
            if db_sc:
                sc_obj = PublicScenario(
                    id=db_sc.id,
                    name=db_sc.name,
                    seed=db_sc.seed,
                    start_at=to_iso_z(db_sc.start_at),
                    end_at=to_iso_z(db_sc.end_at),
                    ready_for_evaluation=db_sc.ready_for_evaluation
                )

        meta = SnapshotMeta(
            contract_version="orbitron.v1",
            mode="simulation",
            state_revision=app_state.state_revision,
            schedule_version=app_state.schedule_version,
            server_time=to_iso_z(server_now),
            simulation_time=to_iso_z(sim_time),
            visible_start_at=to_iso_z(vis_start),
            visible_end_at=to_iso_z(vis_end),
            services=SnapshotServices(
                scheduler="ready" if SchedulerAdapter.is_available() else "unavailable",
                security="ready" if SecurityAdapter.is_available() else "unavailable"
            )
        )

        return Snapshot(
            meta=meta,
            user=PublicUser(
                id=current_user.id,
                display_name=current_user.display_name,
                email=current_user.email,
                organization_id=current_user.organization_id,
                role=current_user.role
            ),
            organizations=public_orgs,
            satellites=public_satellites,
            stations=public_stations,
            jobs=public_jobs,
            opportunities=public_opps,
            contacts=public_contacts,
            schedule_changes=public_sc,
            events=public_events,
            transfers=public_transfers,
            security_checks=public_checks,
            evaluations=public_evals,
            operations=public_ops,
            audit=public_audit,
            simulator=sim_state,
            scenario=sc_obj
        )
