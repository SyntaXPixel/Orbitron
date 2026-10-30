import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session as DBSession

from app.db.session import SessionLocal
from app.db.models import Operation as DBOperation, ApplicationState
from app.services.scheduling_service import SchedulingService
from app.services.event_service import EventService
from app.services.simulation_service import SimulationService
from app.services.transfer_service import TransferService
from app.services.security_service import SecurityService
from app.services.evaluation_service import EvaluationService

logger = logging.getLogger("orbitron.worker")

class OperationsWorker:
    def __init__(self, poll_interval_seconds: float = 0.5, session_factory=None):
        self.poll_interval = poll_interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None
        self.session_factory = session_factory or SessionLocal

    def start(self):
        if not self._running:
            self._running = True
            self.reconcile_interrupted_operations()
            self._task = asyncio.create_task(self._worker_loop())
            logger.info("Operations worker started")

    async def stop(self):
        if self._running:
            self._running = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info("Operations worker stopped")

    def reconcile_interrupted_operations(self):
        db: DBSession = self.session_factory()
        try:
            interrupted = db.query(DBOperation).filter(DBOperation.status == "running").all()
            for op in interrupted:
                op.status = "failed"
                op.completed_at = datetime.now(timezone.utc)
                op.reasons_json = [{
                    "code": "INTERRUPTED_BY_RESTART",
                    "message": "Operation was interrupted by backend restart and failed safely.",
                    "resource_ids": [op.id]
                }]
            if interrupted:
                db.commit()
                logger.warning(f"Reconciled {len(interrupted)} interrupted operations.")
        finally:
            db.close()

    async def _worker_loop(self):
        while self._running:
            try:
                processed_any = self.process_next_operation()
                if not processed_any:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in operations worker loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)

    def process_next_operation(self) -> bool:
        db: DBSession = self.session_factory()
        try:
            # Claim next queued operation
            op = (
                db.query(DBOperation)
                .filter(DBOperation.status == "queued")
                .order_by(DBOperation.submitted_at.asc())
                .first()
            )
            if not op:
                return False

            op.status = "running"
            db.commit()
            db.refresh(op)

            # Process based on kind
            if op.kind == "schedule":
                SchedulingService.run_schedule_operation(db, op)
            elif op.kind == "disruption":
                EventService.run_disruption_operation(db, op)
            elif op.kind == "simulation":
                SimulationService.run_action_operation(db, op)
            elif op.kind == "transfer":
                TransferService.run_transfer_operation(db, op)
            elif op.kind == "security_check":
                SecurityService.run_security_check_operation(db, op)
            elif op.kind == "evaluation":
                EvaluationService.run_evaluation_operation(db, op)
            else:
                op.status = "failed"
                op.completed_at = datetime.now(timezone.utc)
                op.reasons_json = [{
                    "code": "UNKNOWN_KIND",
                    "message": f"Unknown operation kind {op.kind}",
                    "resource_ids": [op.id]
                }]
                db.commit()

            return True
        finally:
            db.close()

worker = OperationsWorker()
