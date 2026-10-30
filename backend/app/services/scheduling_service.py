import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set
from sqlalchemy.orm import Session as DBSession

from app.db.models import (
    Job as DBJob, Satellite as DBSatellite, Station as DBStation,
    Antenna as DBAntenna, Opportunity as DBOpportunity, Contact as DBContact,
    ScheduleChange as DBScheduleChange, ApplicationState, AuditEntry,
    Operation as DBOperation, StationPartnerPermission as DBStationPartner,
    ServicePrincipal, ServiceCommand as DBServiceCommand
)
from app.adapters.scheduler import SchedulerAdapter
from app.schemas.public import to_iso_z
from app.services.snapshot_service import parse_iso_z, SnapshotService

class SchedulingService:
    @classmethod
    def run_schedule_operation(
        cls,
        db: DBSession,
        operation: DBOperation
    ) -> bool:
        """
        Executes a queued schedule operation.
        Returns True if successful, False if failed.
        """
        app_state = SnapshotService.get_app_state(db)
        sim_time = app_state.simulation_time
        if sim_time.tzinfo is None:
            sim_time = sim_time.replace(tzinfo=timezone.utc)

        if not SchedulerAdapter.is_available():
            operation.status = "failed"
            operation.completed_at = datetime.now(timezone.utc)
            operation.reasons_json = [{
                "code": "SCHEDULER_UNAVAILABLE",
                "message": "Scheduler module is not available or could not be loaded.",
                "resource_ids": []
            }]
            db.commit()
            return False

        payload = operation.payload_json or {}
        algorithm = payload.get("algorithm", "optimized")
        expected_version = payload.get("expected_schedule_version")

        if expected_version is not None and expected_version != app_state.schedule_version:
            operation.status = "failed"
            operation.completed_at = datetime.now(timezone.utc)
            operation.reasons_json = [{
                "code": "STALE_SCHEDULE",
                "message": f"Expected schedule version {expected_version} but current is {app_state.schedule_version}",
                "resource_ids": []
            }]
            db.commit()
            return False

        # 1. Build problem
        horizon_start = sim_time
        horizon_end = sim_time + timedelta(hours=12)

        jobs = db.query(DBJob).filter(DBJob.status.in_(["pending", "scheduled", "blocked"])).all()
        satellites = db.query(DBSatellite).all()
        stations = db.query(DBStation).all()
        opportunities = db.query(DBOpportunity).filter(
            DBOpportunity.start_at <= horizon_end,
            DBOpportunity.end_at >= horizon_start
        ).all()
        existing_contacts = db.query(DBContact).filter(
            DBContact.status.in_(["tentative", "confirmed", "active"])
        ).all()

        sharing_map: Dict[str, List[str]] = {}
        for st in stations:
            sharing_map[st.id] = [p.partner_org_id for p in st.partner_permissions]

        problem = {
            "contract_version": "orbitron.v1",
            "simulation_time": to_iso_z(sim_time),
            "schedule_version": app_state.schedule_version,
            "planning_revision": app_state.planning_revision,
            "horizon": {
                "from_at": to_iso_z(horizon_start),
                "to_at": to_iso_z(horizon_end)
            },
            "jobs": [
                {
                    "id": j.id,
                    "satellite_id": j.satellite_id,
                    "owner_org_id": j.owner_org_id,
                    "remaining_bytes": j.remaining_bytes,
                    "priority": j.priority,
                    "deadline_at": to_iso_z(j.deadline_at),
                    "allow_split": j.allow_split,
                    "arrival_sequence": j.arrival_sequence
                }
                for j in jobs
            ],
            "satellites": [
                {
                    "id": s.id,
                    "owner_org_id": s.owner_org_id,
                    "supported_bands": s.supported_bands_json or [],
                    "max_downlink_rate_bps": s.max_downlink_rate_bps,
                    "max_parallel_contacts": s.max_parallel_contacts,
                    "operational_status": s.operational_status
                }
                for s in satellites
            ],
            "stations": [
                {
                    "id": st.id,
                    "owner_org_id": st.owner_org_id,
                    "operational_status": st.operational_status,
                    "weather_capacity_factor": st.weather_capacity_factor,
                    "sharing_enabled": st.sharing_enabled,
                    "approved_partner_org_ids": sharing_map.get(st.id, []),
                    "antennas": [
                        {
                            "id": a.id,
                            "supported_bands": a.supported_bands_json or [],
                            "max_rate_bps": a.max_rate_bps,
                            "setup_seconds": a.setup_seconds,
                            "status": a.status
                        }
                        for a in st.antennas
                    ]
                }
                for st in stations
            ],
            "opportunities": [
                {
                    "id": o.id,
                    "satellite_id": o.satellite_id,
                    "station_id": o.station_id,
                    "antenna_id": o.antenna_id,
                    "band": o.band,
                    "start_at": to_iso_z(o.start_at),
                    "end_at": to_iso_z(o.end_at),
                    "predicted_rate_bps": o.predicted_rate_bps
                }
                for o in opportunities
            ],
            "existing_contacts": [
                {
                    "id": c.id,
                    "job_id": c.job_id,
                    "satellite_id": c.satellite_id,
                    "station_id": c.station_id,
                    "antenna_id": c.antenna_id,
                    "start_at": to_iso_z(c.start_at),
                    "end_at": to_iso_z(c.end_at),
                    "status": c.status
                }
                for c in existing_contacts
            ],
            "policy": {
                "protect_active_contacts": True,
                "allow_active_preemption": False
            }
        }

        # 2. Call scheduler adapter outside write transaction
        try:
            result = SchedulerAdapter.solve_schedule(problem=problem, algorithm=algorithm, time_limit_seconds=5)
        except Exception as e:
            operation.status = "failed"
            operation.completed_at = datetime.now(timezone.utc)
            operation.reasons_json = [{
                "code": "SCHEDULER_ERROR",
                "message": f"Scheduler returned error: {str(e)}",
                "resource_ids": []
            }]
            db.commit()
            return False

        if not isinstance(result, dict) or result.get("status") not in ["feasible", "infeasible"]:
            operation.status = "failed"
            operation.completed_at = datetime.now(timezone.utc)
            operation.reasons_json = [{
                "code": "SCHEDULER_UNAVAILABLE",
                "message": f"Scheduler returned invalid status: {result.get('status') if isinstance(result, dict) else 'none'}",
                "resource_ids": []
            }]
            db.commit()
            return False

        # 3. Independent backend validation
        validation_errors = cls._validate_assignments(
            db=db,
            assignments=result.get("assignments", []),
            sim_time=sim_time,
            existing_contacts=existing_contacts
        )

        if validation_errors:
            operation.status = "failed"
            operation.completed_at = datetime.now(timezone.utc)
            operation.reasons_json = validation_errors
            db.commit()
            return False

        # 4. Commit valid schedule
        cls._commit_schedule_assignments(
            db=db,
            assignments=result.get("assignments", []),
            unassigned_jobs=result.get("unassigned_jobs", []),
            app_state=app_state,
            sim_time=sim_time,
            operation_id=operation.id
        )

        operation.status = "succeeded"
        operation.completed_at = datetime.now(timezone.utc)
        operation.reasons_json = []
        db.commit()
        return True

    @classmethod
    def _validate_assignments(
        cls,
        db: DBSession,
        assignments: List[Dict[str, Any]],
        sim_time: datetime,
        existing_contacts: List[DBContact]
    ) -> List[Dict[str, Any]]:
        errors: List[Dict[str, Any]] = []

        jobs_by_id = {j.id: j for j in db.query(DBJob).all()}
        sats_by_id = {s.id: s for s in db.query(DBSatellite).all()}
        stations_by_id = {st.id: st for st in db.query(DBStation).all()}
        antennas_by_id = {a.id: a for a in db.query(DBAntenna).all()}
        opps_by_id = {o.id: o for o in db.query(DBOpportunity).all()}

        antenna_intervals: Dict[str, List[Tuple[datetime, datetime]]] = {}
        sat_contact_intervals: Dict[str, List[Tuple[datetime, datetime]]] = {}

        # Add active existing contacts into antenna and sat intervals to ensure protection
        for ec in existing_contacts:
            if ec.status == "active":
                st = ec.setup_start_at if ec.setup_start_at.tzinfo else ec.setup_start_at.replace(tzinfo=timezone.utc)
                et = ec.end_at if ec.end_at.tzinfo else ec.end_at.replace(tzinfo=timezone.utc)
                antenna_intervals.setdefault(ec.antenna_id, []).append((st, et))
                sat_contact_intervals.setdefault(ec.satellite_id, []).append((st, et))

        for asgn in assignments:
            job_id = asgn.get("job_id")
            sat_id = asgn.get("satellite_id")
            station_id = asgn.get("station_id")
            antenna_id = asgn.get("antenna_id")
            opp_id = asgn.get("opportunity_id")
            band = asgn.get("band")

            # Validate existence
            if job_id not in jobs_by_id:
                errors.append({"code": "INVALID_JOB", "message": f"Job {job_id} not found", "resource_ids": [job_id or ""]})
                continue
            if sat_id not in sats_by_id:
                errors.append({"code": "INVALID_SATELLITE", "message": f"Satellite {sat_id} not found", "resource_ids": [sat_id or ""]})
                continue
            if station_id not in stations_by_id:
                errors.append({"code": "INVALID_STATION", "message": f"Station {station_id} not found", "resource_ids": [station_id or ""]})
                continue
            if antenna_id not in antennas_by_id:
                errors.append({"code": "INVALID_ANTENNA", "message": f"Antenna {antenna_id} not found", "resource_ids": [antenna_id or ""]})
                continue
            if opp_id not in opps_by_id:
                errors.append({"code": "INVALID_OPPORTUNITY", "message": f"Opportunity {opp_id} not found", "resource_ids": [opp_id or ""]})
                continue

            job = jobs_by_id[job_id]
            sat = sats_by_id[sat_id]
            st = stations_by_id[station_id]
            ant = antennas_by_id[antenna_id]
            opp = opps_by_id[opp_id]

            # Station and antenna health
            if st.operational_status == "offline":
                errors.append({"code": "STATION_OFFLINE", "message": f"Station {station_id} is offline", "resource_ids": [station_id]})
            if ant.status != "available":
                errors.append({"code": "ANTENNA_BUSY", "message": f"Antenna {antenna_id} is {ant.status}", "resource_ids": [antenna_id]})

            # Band compatibility
            if band not in (ant.supported_bands_json or []):
                errors.append({"code": "BAND_MISMATCH", "message": f"Antenna does not support band {band}", "resource_ids": [antenna_id]})
            if band not in (sat.supported_bands_json or []):
                errors.append({"code": "BAND_MISMATCH", "message": f"Satellite does not support band {band}", "resource_ids": [sat_id]})

            # Opportunity match
            if opp.satellite_id != sat_id or opp.station_id != station_id or opp.antenna_id != antenna_id:
                errors.append({"code": "OPPORTUNITY_MISMATCH", "message": f"Opportunity {opp_id} does not match resource parameters", "resource_ids": [opp_id]})

            # Timing parsing
            try:
                setup_start = parse_iso_z(asgn["setup_start_at"])
                start_at = parse_iso_z(asgn["start_at"])
                end_at = parse_iso_z(asgn["end_at"])
            except Exception:
                errors.append({"code": "INVALID_TIMESTAMPS", "message": "Invalid timestamp format", "resource_ids": [job_id]})
                continue

            # Start time in future relative to simulation time
            if start_at < sim_time:
                errors.append({"code": "STALE_TIME", "message": "Proposed start is in the simulation past", "resource_ids": [job_id]})

            # Inside opportunity window
            opp_start = opp.start_at if opp.start_at.tzinfo else opp.start_at.replace(tzinfo=timezone.utc)
            opp_end = opp.end_at if opp.end_at.tzinfo else opp.end_at.replace(tzinfo=timezone.utc)
            if start_at < opp_start or end_at > opp_end:
                errors.append({"code": "OUTSIDE_WINDOW", "message": "Communication outside opportunity window", "resource_ids": [job_id, opp_id]})

            # Setup interval respected
            if setup_start + timedelta(seconds=ant.setup_seconds) > start_at:
                errors.append({"code": "SETUP_CONFLICT", "message": f"Setup time of {ant.setup_seconds}s not respected", "resource_ids": [antenna_id]})

            # Deadline respected
            job_deadline = job.deadline_at if job.deadline_at.tzinfo else job.deadline_at.replace(tzinfo=timezone.utc)
            if end_at > job_deadline:
                errors.append({"code": "DEADLINE_UNREACHABLE", "message": "Contact ends after job deadline", "resource_ids": [job_id]})

            # Sharing permissions
            if sat.owner_org_id != st.owner_org_id:
                partners = [p.partner_org_id for p in st.partner_permissions]
                if not st.sharing_enabled or sat.owner_org_id not in partners:
                    errors.append({"code": "PARTNER_NOT_APPROVED", "message": f"Station sharing not approved for org {sat.owner_org_id}", "resource_ids": [station_id, sat_id]})

            # Data volume and rate
            allocated_bytes = asgn.get("allocated_bytes", 0)
            expected_rate = asgn.get("expected_rate_bps", 0)
            if allocated_bytes > job.remaining_bytes:
                errors.append({"code": "INSUFFICIENT_CAPACITY", "message": "Allocated bytes exceed job remaining work", "resource_ids": [job_id]})
            
            contact_duration = (end_at - start_at).total_seconds()
            effective_factor = st.weather_capacity_factor if st.weather_capacity_factor is not None else 1.0
            max_possible_bytes = int(contact_duration * (expected_rate * effective_factor) / 8)
            if allocated_bytes > max_possible_bytes:
                errors.append({"code": "RATE_MISMATCH", "message": f"Duration and rate cannot support {allocated_bytes} bytes (max: {max_possible_bytes})", "resource_ids": [job_id]})

            # Antenna overlap
            for (prev_st, prev_et) in antenna_intervals.get(antenna_id, []):
                if max(setup_start, prev_st) < min(end_at, prev_et):
                    errors.append({"code": "ANTENNA_BUSY", "message": f"Overlap detected on antenna {antenna_id}", "resource_ids": [antenna_id]})
            antenna_intervals.setdefault(antenna_id, []).append((setup_start, end_at))

            # Satellite concurrency
            sat_intervals = sat_contact_intervals.setdefault(sat_id, [])
            overlap_count = 0
            for (prev_st, prev_et) in sat_intervals:
                if max(start_at, prev_st) < min(end_at, prev_et):
                    overlap_count += 1
            if overlap_count >= sat.max_parallel_contacts:
                errors.append({"code": "CONCURRENCY_LIMIT_EXCEEDED", "message": f"Satellite {sat_id} max parallel contacts ({sat.max_parallel_contacts}) exceeded", "resource_ids": [sat_id]})
            sat_intervals.append((start_at, end_at))

        return errors

    @classmethod
    def _commit_schedule_assignments(
        cls,
        db: DBSession,
        assignments: List[Dict[str, Any]],
        unassigned_jobs: List[Dict[str, Any]],
        app_state: ApplicationState,
        sim_time: datetime,
        operation_id: str
    ):
        new_version = app_state.schedule_version + 1
        app_state.schedule_version = new_version
        app_state.state_revision += 1

        # Track old contacts to remove (only tentative/confirmed; active are protected)
        affected_jobs = {a["job_id"] for a in assignments} | {u["job_id"] for u in unassigned_jobs}

        # Clear existing non-active contacts for affected jobs
        for job_id in affected_jobs:
            old_contacts = (
                db.query(DBContact)
                .filter(DBContact.job_id == job_id, DBContact.status.in_(["tentative", "confirmed"]))
                .all()
            )
            old_contact_ids = [c.id for c in old_contacts]
            new_contact_ids: List[str] = []

            # Find assignments for this job
            job_asgns = [a for a in assignments if a["job_id"] == job_id]
            for asgn in job_asgns:
                cid = f"contact-{secrets.token_hex(6)}"
                new_contact_ids.append(cid)
                opp = db.query(DBOpportunity).filter(DBOpportunity.id == asgn["opportunity_id"]).first()
                window_start = opp.start_at if opp else parse_iso_z(asgn["start_at"])
                window_end = opp.end_at if opp else parse_iso_z(asgn["end_at"])

                c_obj = DBContact(
                    id=cid,
                    job_id=job_id,
                    satellite_id=asgn["satellite_id"],
                    station_id=asgn["station_id"],
                    antenna_id=asgn["antenna_id"],
                    opportunity_id=asgn["opportunity_id"],
                    band=asgn["band"],
                    window_start_at=window_start,
                    window_end_at=window_end,
                    setup_start_at=parse_iso_z(asgn["setup_start_at"]),
                    start_at=parse_iso_z(asgn["start_at"]),
                    end_at=parse_iso_z(asgn["end_at"]),
                    expected_rate_bps=asgn.get("expected_rate_bps", 100_000_000),
                    allocated_bytes=asgn.get("allocated_bytes", 0),
                    transferred_bytes=0,
                    status="tentative",
                    authorization_status="pending",
                    schedule_version=new_version,
                    reasons_json=asgn.get("reasons", []),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db.add(c_obj)

                # Create scoped service command for the station gateway
                gateways = db.query(ServicePrincipal).filter(ServicePrincipal.category == "station_gateway").all()
                for gw in gateways:
                    st_ids = (gw.permitted_resources_json or {}).get("station_ids", [])
                    if asgn["station_id"] in st_ids:
                        cmd = DBServiceCommand(
                            id=f"cmd-{secrets.token_hex(6)}",
                            principal_id=gw.id,
                            command_type="confirm_contact",
                            contact_id=cid,
                            payload_json={"schedule_version": new_version, "contact_id": cid},
                            status="pending"
                        )
                        db.add(cmd)

            # Record schedule change
            sc = DBScheduleChange(
                id=f"sc-{secrets.token_hex(6)}",
                schedule_version=new_version,
                job_id=job_id,
                old_contact_ids_json=old_contact_ids,
                new_contact_ids_json=new_contact_ids,
                reasons_json=[{"code": "SCHEDULE_OPTIMIZED", "message": "Assignments committed by scheduler", "resource_ids": [job_id]}],
                created_at=sim_time
            )
            db.add(sc)

            # Delete the superseded tentative/confirmed contacts
            for oc in old_contacts:
                db.delete(oc)

            # Update job status
            db_job = db.query(DBJob).filter(DBJob.id == job_id).first()
            if db_job:
                if job_asgns:
                    db_job.status = "scheduled"
                    db_job.reasons_json = []
                else:
                    unassigned_info = next((u for u in unassigned_jobs if u["job_id"] == job_id), None)
                    reasons = unassigned_info.get("reasons", []) if unassigned_info else []
                    db_job.status = "blocked" if reasons else "pending"
                    db_job.reasons_json = reasons
                db_job.updated_at = sim_time

        # Audit entry
        audit = AuditEntry(
            id=f"audit-{secrets.token_hex(8)}",
            actor_name="scheduler",
            action="solve_schedule",
            resource_type="schedule",
            resource_id=f"v{new_version}",
            outcome="succeeded",
            message=f"Committed schedule version {new_version} with {len(assignments)} assignments",
            timestamp=sim_time,
            clock_basis="simulation"
        )
        db.add(audit)
