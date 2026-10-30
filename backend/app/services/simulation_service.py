import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session as DBSession

from app.db.models import (
    ApplicationState, ScenarioRun, Satellite as DBSatellite,
    Station as DBStation, Job as DBJob, Contact as DBContact,
    ScheduleChange as DBScheduleChange, DisruptionEvent as DBDisruptionEvent,
    Transfer as DBTransfer, SecurityCheck as DBSecurityCheck, Evaluation as DBEvaluation,
    Operation as DBOperation, AuditEntry as DBAuditEntry, User as DBUser
)
from app.schemas.requests import SimulationActionRequest
from app.services.snapshot_service import SnapshotService, to_iso_z

class SimulationService:
    @classmethod
    def apply_action(
        cls,
        db: DBSession,
        current_user: DBUser,
        req: SimulationActionRequest
    ) -> Tuple[Optional[DBOperation], Optional[str], Optional[str]]:
        if current_user.role != "network_admin":
            return None, "FORBIDDEN", "Only network administrators can control the simulation."

        app_state = SnapshotService.get_app_state(db)

        if req.action == "step" and app_state.simulation_run_state != "paused":
            return None, "INVALID_STATE", "Simulation step is only permitted when paused."

        op_id = f"op-{secrets.token_hex(8)}"
        op = DBOperation(
            id=op_id,
            kind="simulation",
            status="queued",
            resource_id=req.action,
            submitted_at=datetime.now(timezone.utc),
            reasons_json=[],
            payload_json={
                "action": req.action,
                "step_seconds": req.step_seconds,
                "seed": req.seed
            },
            created_by_user_id=current_user.id
        )
        db.add(op)
        db.commit()
        db.refresh(op)
        return op, None, None

    @classmethod
    def run_action_operation(cls, db: DBSession, operation: DBOperation) -> bool:
        app_state = SnapshotService.get_app_state(db)
        payload = operation.payload_json or {}
        action = payload.get("action")
        step_seconds = payload.get("step_seconds")
        seed = payload.get("seed")

        now_server = datetime.now(timezone.utc)
        sim_time = app_state.simulation_time
        if sim_time.tzinfo is None:
            sim_time = sim_time.replace(tzinfo=timezone.utc)

        if action == "pause":
            app_state.simulation_run_state = "paused"
            app_state.state_revision += 1

        elif action == "resume":
            app_state.simulation_run_state = "running"
            app_state.state_revision += 1

        elif action == "step":
            secs = step_seconds or 60
            app_state.simulation_time = sim_time + timedelta(seconds=secs)
            app_state.state_revision += 1

        elif action == "reset":
            # Cancel / fail any older pending operations
            old_ops = db.query(DBOperation).filter(
                DBOperation.id != operation.id,
                DBOperation.status.in_(["queued", "running"])
            ).all()
            for o in old_ops:
                o.status = "failed"
                o.completed_at = now_server
                o.reasons_json = [{"code": "SCENARIO_RESET", "message": "Operation cancelled due to scenario reset", "resource_ids": []}]

            # Create new scenario run
            scenario_seed = seed if seed is not None else 42
            new_sc_id = f"scenario-{secrets.token_hex(6)}"
            base_start = datetime(2026, 10, 31, 6, 0, 0, tzinfo=timezone.utc)
            base_end = base_start + timedelta(hours=24)

            # Mark old scenario runs inactive
            for sr in db.query(ScenarioRun).all():
                sr.is_active = False

            sc_run = ScenarioRun(
                id=new_sc_id,
                name=f"Orbitron Standard Scenario (Seed {scenario_seed})",
                seed=scenario_seed,
                start_at=base_start,
                end_at=base_end,
                ready_for_evaluation=True,
                is_active=True,
                created_at=now_server
            )
            db.add(sc_run)

            # Reset application state
            app_state.current_scenario_id = new_sc_id
            app_state.simulation_time = base_start
            app_state.simulation_run_state = "paused"
            app_state.state_revision = 1
            app_state.schedule_version = 0
            app_state.planning_revision = 0

            # Reset satellites
            for sat in db.query(DBSatellite).all():
                sat.onboard_bytes = 10_000_000_000
                sat.reserved_bytes = 0
                sat.operational_status = "available"
                sat.telemetry_status = "never_seen"
                sat.last_telemetry_at = None

            # Reset stations
            for st in db.query(DBStation).all():
                st.operational_status = "online"
                st.weather_capacity_factor = 1.0

            # Delete old operational records
            db.query(DBJob).delete()
            db.query(DBContact).delete()
            db.query(DBScheduleChange).delete()
            db.query(DBDisruptionEvent).delete()
            db.query(DBTransfer).delete()
            db.query(DBSecurityCheck).delete()
            db.query(DBEvaluation).delete()

        audit = DBAuditEntry(
            id=f"audit-{secrets.token_hex(8)}",
            actor_name="operator",
            action=f"simulation_{action}",
            resource_type="simulation",
            resource_id=action,
            outcome="succeeded",
            message=f"Executed simulation action {action}",
            timestamp=now_server,
            clock_basis="server"
        )
        db.add(audit)

        operation.status = "succeeded"
        operation.completed_at = now_server
        db.commit()
        return True
