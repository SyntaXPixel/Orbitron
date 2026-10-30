import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session as DBSession

from sqlalchemy import func
from app.db.models import Job as DBJob, Satellite as DBSatellite, User as DBUser, AuditEntry, Operation as DBOperation, ApplicationState
from app.schemas.requests import JobCreateRequest
from app.schemas.public import Job as PublicJob, Reason, to_iso_z
from app.services.snapshot_service import parse_iso_z, SnapshotService

class JobService:
    @classmethod
    def create_job(cls, db: DBSession, current_user: DBUser, req: JobCreateRequest) -> Tuple[Optional[DBJob], Optional[str], Optional[str]]:
        """
        Returns (job, None, None) on success or (None, error_code, error_message) on validation failure.
        """
        app_state = SnapshotService.get_app_state(db)
        sim_time = app_state.simulation_time
        if sim_time.tzinfo is None:
            sim_time = sim_time.replace(tzinfo=timezone.utc)

        # 1. Validate satellite
        sat = db.query(DBSatellite).filter(DBSatellite.id == req.satellite_id).first()
        if not sat:
            return None, "NOT_FOUND", f"Satellite {req.satellite_id} is not registered."

        # 2. Check ownership
        if current_user.role != "network_admin" and sat.owner_org_id != current_user.organization_id:
            return None, "FORBIDDEN", f"User does not own satellite {req.satellite_id}."

        # 3. Check deadline against simulation time
        try:
            deadline = parse_iso_z(req.deadline_at)
        except Exception:
            return None, "VALIDATION_ERROR", "Invalid deadline format. Expected ISO 8601 UTC ending in Z."

        if deadline <= sim_time:
            return None, "DEADLINE_PAST", "Deadline must be in the future relative to simulation time."

        # 4. Check unreserved onboard data
        available_bytes = sat.onboard_bytes - sat.reserved_bytes
        if available_bytes < req.data_bytes:
            return None, "INSUFFICIENT_ONBOARD_DATA", (
                f"Satellite has only {available_bytes} unreserved onboard bytes, but {req.data_bytes} were requested."
            )

        # 5. Create job
        max_seq = db.query(func.coalesce(func.max(DBJob.arrival_sequence), 0)).scalar() or 0
        job_id = f"job-{secrets.token_hex(6)}"
        job = DBJob(
            id=job_id,
            satellite_id=sat.id,
            owner_org_id=sat.owner_org_id,
            requested_bytes=req.data_bytes,
            delivered_bytes=0,
            remaining_bytes=req.data_bytes,
            priority=req.priority,
            deadline_at=deadline,
            allow_split=req.allow_split,
            status="pending",
            reasons_json=[],
            arrival_sequence=max_seq + 1,
            created_at=sim_time,
            updated_at=sim_time
        )
        db.add(job)

        # 6. Reserve onboard bytes
        sat.reserved_bytes += req.data_bytes

        # 7. Audit entry
        now_server = datetime.now(timezone.utc)
        audit = AuditEntry(
            id=f"audit-{secrets.token_hex(8)}",
            actor_name=current_user.display_name,
            action="create_job",
            resource_type="job",
            resource_id=job_id,
            outcome="succeeded",
            message=f"Created job {job_id} for satellite {sat.id} requesting {req.data_bytes} bytes",
            timestamp=sim_time,
            clock_basis="simulation"
        )
        db.add(audit)

        # 8. Advance revisions
        app_state.state_revision += 1
        app_state.planning_revision += 1

        # 9. Handle emergency job auto-replan
        if req.priority == "emergency":
            op_id = f"op-{secrets.token_hex(8)}"
            auto_op = DBOperation(
                id=op_id,
                kind="schedule",
                status="queued",
                resource_id=job_id,
                submitted_at=now_server,
                reasons_json=[{"code": "EMERGENCY_REPLAN", "message": f"Automatic replan triggered by emergency job {job_id}", "resource_ids": [job_id]}],
                payload_json={"algorithm": "optimized", "expected_schedule_version": app_state.schedule_version},
                created_by_user_id=current_user.id
            )
            db.add(auto_op)

        db.commit()
        db.refresh(job)
        return job, None, None

    @classmethod
    def to_public_model(cls, job: DBJob) -> PublicJob:
        return PublicJob(
            id=job.id,
            satellite_id=job.satellite_id,
            owner_org_id=job.owner_org_id,
            requested_bytes=job.requested_bytes,
            delivered_bytes=job.delivered_bytes,
            remaining_bytes=job.remaining_bytes,
            priority=job.priority,
            deadline_at=to_iso_z(job.deadline_at),
            allow_split=job.allow_split,
            status=job.status,
            reasons=[Reason(**r) for r in (job.reasons_json or [])],
            created_at=to_iso_z(job.created_at),
            updated_at=to_iso_z(job.updated_at)
        )
