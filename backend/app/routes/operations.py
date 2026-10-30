from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.db.models import Operation as DBOperation
from app.schemas.public import Operation as PublicOperation, Reason, to_iso_z
from app.routes.deps import get_current_user, OrbitronAPIException

router = APIRouter(prefix="/operations", tags=["Operations"])

@router.get("/{operation_id}", response_model=PublicOperation)
def get_operation(
    operation_id: str,
    current_user=Depends(get_current_user),
    db: DBSession = Depends(get_db)
):
    op = db.query(DBOperation).filter(DBOperation.id == operation_id).first()
    if not op:
        raise OrbitronAPIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Operation {operation_id} not found."
        )

    # Visibility check
    if current_user.role != "network_admin":
        if op.created_by_user_id and op.created_by_user_id != current_user.id:
            raise OrbitronAPIException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="FORBIDDEN",
                message="User is not authorized to inspect this operation."
            )

    return PublicOperation(
        id=op.id,
        kind=op.kind,
        status=op.status,
        resource_id=op.resource_id,
        submitted_at=to_iso_z(op.submitted_at),
        completed_at=to_iso_z(op.completed_at) if op.completed_at else None,
        reasons=[Reason(**r) for r in (op.reasons_json or [])]
    )
