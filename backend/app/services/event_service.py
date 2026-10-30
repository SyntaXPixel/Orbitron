import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session as DBSession

from app.db.models import (
    DisruptionEvent as DBDisruptionEvent, Station as DBStation,
    Contact as DBContact, Job as DBJob, ApplicationState, AuditEntry,
    Operation as DBOperation, User as DBUser
)
from app.schemas.requests import DisruptionEventRequest
from app.services.snapshot_service import SnapshotService

class EventService:
    @classmethod
    def apply_event(
        cls,
        db: DBSession,
        current_user: DBUser,
        req: DisruptionEventRequest
    ) -> Tuple[Optional[DBDisruptionEvent], Optional[DBOperation], Optional[str], Optional[str]]:
        """
        Returns (event, operation, None, None) or (None, None, error_code, error_message).
        """
        app_state = SnapshotService.get_app_state(db)
        sim_time = app_state.simulation_time
        if sim_time.tzinfo is None:
            sim_time = sim_time.replace(tzinfo=timezone.utc)

        # 1. Permission check
        if current_user.role != "network_admin":
            return None, None, "FORBIDDEN", "Only network administrators can inject disruption events."

        # 2. Check schedule version
        if req.expected_schedule_version != app_state.schedule_version:
            return None, None, "STALE_SCHEDULE", (
                f"Expected schedule version {req.expected_schedule_version} but current is {app_state.schedule_version}"
            )

        # 3. Check station
        st = db.query(DBStation).filter(DBStation.id == req.station_id).first()
        if not st:
            return None, None, "NOT_FOUND", f"Station {req.station_id} not found."

        # 4. Create disruption event record
        event_id = f"event-{secrets.token_hex(6)}"
        op_id = f"op-{secrets.token_hex(8)}"

        event = DBDisruptionEvent(
            id=event_id,
            type=req.type,
            station_id=req.station_id,
            capacity_factor=req.capacity_factor,
            status="pending",
            occurred_at=sim_time,
            operation_id=op_id,
            reasons_json=[]
        )
        db.add(event)

        op = DBOperation(
            id=op_id,
            kind="disruption",
            status="queued",
            resource_id=event_id,
            submitted_at=datetime.now(timezone.utc),
            reasons_json=[],
            payload_json={
                "event_id": event_id,
                "type": req.type,
                "station_id": req.station_id,
                "capacity_factor": req.capacity_factor,
                "expected_schedule_version": req.expected_schedule_version
            },
            created_by_user_id=current_user.id
        )
        db.add(op)
        db.commit()
        db.refresh(event)
        db.refresh(op)

        return event, op, None, None

    @classmethod
    def run_disruption_operation(cls, db: DBSession, operation: DBOperation) -> bool:
        app_state = SnapshotService.get_app_state(db)
        sim_time = app_state.simulation_time
        if sim_time.tzinfo is None:
            sim_time = sim_time.replace(tzinfo=timezone.utc)

        payload = operation.payload_json or {}
        event_id = payload.get("event_id")
        event_type = payload.get("type")
        station_id = payload.get("station_id")
        capacity_factor = payload.get("capacity_factor")

        event = db.query(DBDisruptionEvent).filter(DBDisruptionEvent.id == event_id).first()
        st = db.query(DBStation).filter(DBStation.id == station_id).first()
        if not event or not st:
            operation.status = "failed"
            operation.completed_at = datetime.now(timezone.utc)
            operation.reasons_json = [{"code": "NOT_FOUND", "message": "Event or station not found", "resource_ids": []}]
            db.commit()
            return False

        affected_contacts = db.query(DBContact).filter(
            DBContact.station_id == station_id,
            DBContact.status.in_(["tentative", "confirmed", "active"])
        ).all()

        if event_type == "rain":
            st.weather_capacity_factor = float(capacity_factor) if capacity_factor is not None else 1.0
            for c in affected_contacts:
                if c.status in ["tentative", "confirmed"]:
                    duration = (c.end_at - c.start_at).total_seconds()
                    max_bytes = int(duration * (c.expected_rate_bps * st.weather_capacity_factor) / 8)
                    if c.allocated_bytes > max_bytes:
                        c.reasons_json = [{"code": "WEATHER_DEGRADED", "message": f"Rain reduced capacity factor to {st.weather_capacity_factor}", "resource_ids": [c.id]}]

        elif event_type == "station_outage":
            st.operational_status = "offline"
            for c in affected_contacts:
                if c.status in ["tentative", "confirmed"]:
                    c.status = "failed"
                    c.reasons_json = [{"code": "STATION_OFFLINE", "message": "Station is offline due to outage", "resource_ids": [c.id]}]
                    # Revert job to pending
                    job = db.query(DBJob).filter(DBJob.id == c.job_id).first()
                    if job and job.status != "completed":
                        job.status = "pending"
                        job.reasons_json = [{"code": "STATION_OFFLINE", "message": f"Contact cancelled due to station outage on {st.id}", "resource_ids": [job.id]}]

        elif event_type == "station_recovery":
            st.operational_status = "online"
            st.weather_capacity_factor = 1.0

        event.status = "applied"
        app_state.state_revision += 1
        app_state.planning_revision += 1

        # Enqueue recovery schedule run
        recovery_op_id = f"op-{secrets.token_hex(8)}"
        recovery_op = DBOperation(
            id=recovery_op_id,
            kind="schedule",
            status="queued",
            resource_id=st.id,
            submitted_at=datetime.now(timezone.utc),
            reasons_json=[{"code": "RECOVERY_REPLAN", "message": f"Automatic replan after {event_type} on {st.id}", "resource_ids": [st.id]}],
            payload_json={"algorithm": "optimized", "expected_schedule_version": app_state.schedule_version},
            created_by_user_id=operation.created_by_user_id
        )
        db.add(recovery_op)

        audit = AuditEntry(
            id=f"audit-{secrets.token_hex(8)}",
            actor_name="operator",
            action="disruption_applied",
            resource_type="disruption_event",
            resource_id=event.id,
            outcome="succeeded",
            message=f"Applied disruption {event_type} on station {st.id}",
            timestamp=sim_time,
            clock_basis="simulation"
        )
        db.add(audit)

        operation.status = "succeeded"
        operation.completed_at = datetime.now(timezone.utc)
        db.commit()
        return True
