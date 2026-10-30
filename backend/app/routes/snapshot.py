from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.schemas.public import Snapshot
from app.services.snapshot_service import SnapshotService, parse_iso_z
from app.routes.deps import get_current_user, OrbitronAPIException

router = APIRouter(tags=["Snapshot"])

@router.get("/snapshot", response_model=Snapshot)
def get_snapshot(
    from_at: Optional[str] = Query(None, alias="from"),
    to_at: Optional[str] = Query(None, alias="to"),
    current_user=Depends(get_current_user),
    db: DBSession = Depends(get_db)
):
    # Validate paired from and to parameters
    if (from_at is None and to_at is not None) or (from_at is not None and to_at is None):
        raise OrbitronAPIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_RANGE",
            message="Both 'from' and 'to' query parameters must be supplied together, or both omitted."
        )

    if from_at and to_at:
        try:
            start_dt = parse_iso_z(from_at)
            end_dt = parse_iso_z(to_at)
        except Exception:
            raise OrbitronAPIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_TIMESTAMP",
                message="Timestamps must be ISO 8601 UTC strings ending in 'Z'."
            )

        if end_dt <= start_dt:
            raise OrbitronAPIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_RANGE",
                message="'to' timestamp must be strictly greater than 'from' timestamp."
            )

        horizon_hours = (end_dt - start_dt).total_seconds() / 3600.0
        if horizon_hours > 24.0:
            raise OrbitronAPIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="RANGE_TOO_LARGE",
                message="Requested snapshot horizon cannot exceed 24 hours."
            )

    return SnapshotService.assemble_snapshot(
        db=db,
        current_user=current_user,
        from_at_str=from_at,
        to_at_str=to_at
    )
