import json
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.schemas.requests import SecurityCheckRequest
from app.schemas.public import Operation as PublicOperation, to_iso_z
from app.services.security_service import SecurityService
from app.services.idempotency import IdempotencyService, canonical_hash
from app.services.snapshot_service import SnapshotService
from app.routes.deps import get_current_user, OrbitronAPIException

router = APIRouter(prefix="/security", tags=["Security Checks"])

@router.post("/checks", response_model=PublicOperation, status_code=status.HTTP_202_ACCEPTED)
def create_security_check(
    req: SecurityCheckRequest,
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
        route="/security/checks",
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

    check, op = SecurityService.create_security_check(db, current_user, req)

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
        route="/security/checks",
        request_hash=req_hash,
        scenario_id=app_state.current_scenario_id or "",
        status_code=202,
        response_body=public_op.model_dump_json(),
        resource_id=op.id
    )

    return public_op
