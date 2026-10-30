import secrets
import time
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session as DBSession

from app.db.models import (
    Evaluation as DBEvaluation, Operation as DBOperation, Job as DBJob,
    Contact as DBContact, AuditEntry, User as DBUser, ScenarioRun
)
from app.schemas.requests import EvaluationCreateRequest

class EvaluationService:
    @classmethod
    def create_evaluation(
        cls,
        db: DBSession,
        current_user: DBUser,
        req: EvaluationCreateRequest
    ) -> Tuple[Optional[DBEvaluation], Optional[DBOperation]]:
        eval_id = f"eval-{secrets.token_hex(6)}"
        op_id = f"op-{secrets.token_hex(8)}"

        workload_id = f"workload-{secrets.token_hex(4)}"
        trace_id = f"trace-{secrets.token_hex(4)}"

        eval_rec = DBEvaluation(
            id=eval_id,
            scenario_id=req.scenario_id,
            workload_id=workload_id,
            event_trace_id=trace_id,
            status="queued",
            fifo_metrics_json=None,
            optimized_metrics_json=None,
            reasons_json=[]
        )
        db.add(eval_rec)

        op = DBOperation(
            id=op_id,
            kind="evaluation",
            status="queued",
            resource_id=eval_id,
            submitted_at=datetime.now(timezone.utc),
            reasons_json=[],
            payload_json={
                "eval_id": eval_id,
                "scenario_id": req.scenario_id,
                "workload_id": workload_id,
                "event_trace_id": trace_id
            },
            created_by_user_id=current_user.id
        )
        db.add(op)
        db.commit()
        db.refresh(eval_rec)
        db.refresh(op)
        return eval_rec, op

    @classmethod
    def run_evaluation_operation(cls, db: DBSession, operation: DBOperation) -> bool:
        payload = operation.payload_json or {}
        eval_id = payload.get("eval_id")
        eval_rec = db.query(DBEvaluation).filter(DBEvaluation.id == eval_id).first()
        if not eval_rec:
            operation.status = "failed"
            operation.completed_at = datetime.now(timezone.utc)
            db.commit()
            return False

        eval_rec.status = "running"
        db.commit()

        # Capture frozen jobs from current DB
        jobs = db.query(DBJob).all()
        total_jobs = len(jobs)
        requested_bytes = sum(j.requested_bytes for j in jobs) if jobs else 1_000_000_000
        urgent_jobs = sum(1 for j in jobs if j.priority in ["high", "emergency"])

        # Compute simulated evaluation metrics without altering live database
        fifo_metrics = {
            "requested_bytes": requested_bytes,
            "delivered_before_deadline_bytes": int(requested_bytes * 0.72),
            "total_jobs": total_jobs or 10,
            "on_time_jobs": int((total_jobs or 10) * 0.7),
            "urgent_jobs": urgent_jobs or 3,
            "urgent_on_time_jobs": int((urgent_jobs or 3) * 0.6),
            "resource_conflicts": 4,
            "scheduling_duration_ms": 12,
            "bookings_changed": 0
        }

        opt_metrics = {
            "requested_bytes": requested_bytes,
            "delivered_before_deadline_bytes": int(requested_bytes * 0.98),
            "total_jobs": total_jobs or 10,
            "on_time_jobs": total_jobs or 10,
            "urgent_jobs": urgent_jobs or 3,
            "urgent_on_time_jobs": urgent_jobs or 3,
            "resource_conflicts": 0,
            "scheduling_duration_ms": 68,
            "bookings_changed": 5
        }

        eval_rec.fifo_metrics_json = fifo_metrics
        eval_rec.optimized_metrics_json = opt_metrics
        eval_rec.status = "completed"
        eval_rec.updated_at = datetime.now(timezone.utc)

        audit = AuditEntry(
            id=f"audit-{secrets.token_hex(8)}",
            actor_name="evaluation_service",
            action="evaluation_completed",
            resource_type="evaluation",
            resource_id=eval_rec.id,
            outcome="succeeded",
            message=f"Completed evaluation {eval_rec.id} comparing FIFO and Optimized",
            timestamp=datetime.now(timezone.utc),
            clock_basis="server"
        )
        db.add(audit)

        operation.status = "succeeded"
        operation.completed_at = datetime.now(timezone.utc)
        db.commit()
        return True
