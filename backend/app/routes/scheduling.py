import json
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.db.models import Operation as DBOperation
from app.schemas.requests import ScheduleRunRequest
from app.schemas.public import Operation as PublicOperation, to_iso_z, Reason
from app.adapters.scheduler import SchedulerAdapter
from app.services.idempotency import IdempotencyService, canonical_hash
from app.services.snapshot_service import SnapshotService
from app.routes.deps import get_current_user, OrbitronAPIException

router = APIRouter(prefix="/schedule", tags=["Scheduling"])

@router.post("/runs", response_model=PublicOperation, status_code=status.HTTP_202_ACCEPTED)
def create_schedule_run(
    req: ScheduleRunRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user=Depends(get_current_user),
    db: DBSession = Depends(get_db)
):
    app_state = SnapshotService.get_app_state(db)
    req_hash = canonical_hash(req.model_dump())

    # Idempotency check
    existing_rec, idem_err = IdempotencyService.check_idempotency(
        db=db,
        key=idempotency_key,
        principal=current_user.id,
        route="/schedule/runs",
        request_hash=req_hash,
        current_scenario_id=app_state.current_scenario_id or ""
    )

    if idem_err == "SCENARIO_CHANGED":
        raise OrbitronAPIException(
            status_code=status.HTTP_409_CONFLICT,
            code="SCENARIO_CHANGED",
            message="Idempotency key belongs to a previous scenario run."
        )
    elif idem_err == "PAYLOAD_MISMATCH":
        raise OrbitronAPIException(
            status_code=status.HTTP_409_CONFLICT,
            code="IDEMPOTENCY_CONFLICT",
            message="Idempotency key has already been used with a different request payload."
        )
    elif existing_rec:
        return json.loads(existing_rec.response_body)

    # Missing scheduler -> 503
    if not SchedulerAdapter.is_available():
        raise OrbitronAPIException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="SCHEDULER_UNAVAILABLE",
            message="The scheduling optimization service is currently unavailable."
        )

    # Version check
    if req.expected_schedule_version != app_state.schedule_version:
        raise OrbitronAPIException(
            status_code=status.HTTP_409_CONFLICT,
            code="STALE_SCHEDULE",
            message=f"Expected schedule version {req.expected_schedule_version} but current is {app_state.schedule_version}."
        )

    op_id = f"op-{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc)
    op = DBOperation(
        id=op_id,
        kind="schedule",
        status="queued",
        resource_id=None,
        submitted_at=now,
        reasons_json=[],
        payload_json={
            "algorithm": req.algorithm,
            "expected_schedule_version": req.expected_schedule_version
        },
        created_by_user_id=current_user.id
    )
    db.add(op)
    db.commit()
    db.refresh(op)

    public_op = PublicOperation(
        id=op.id,
        kind=op.kind,
        status=op.status,
        resource_id=op.resource_id,
        submitted_at=to_iso_z(op.submitted_at),
        completed_at=None,
        reasons=[]
    )

    IdempotencyService.record_response(
        db=db,
        key=idempotency_key,
        principal=current_user.id,
        route="/schedule/runs",
        request_hash=req_hash,
        scenario_id=app_state.current_scenario_id or "",
        status_code=202,
        response_body=public_op.model_dump_json(),
        resource_id=op.id
    )

    return public_op
