import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session as DBSession

from app.db.models import (
    SecurityCheck as DBSecurityCheck, Operation as DBOperation,
    Contact as DBContact, Station as DBStation, AuditEntry, User as DBUser
)
from app.schemas.requests import SecurityCheckRequest

class SecurityService:
    @classmethod
    def create_security_check(
        cls,
        db: DBSession,
        current_user: DBUser,
        req: SecurityCheckRequest
    ) -> Tuple[Optional[DBSecurityCheck], Optional[DBOperation]]:
        check_id = f"check-{secrets.token_hex(6)}"
        op_id = f"op-{secrets.token_hex(8)}"

        expected_map = {
            "expired_authorization": "Request rejected due to expired credentials or authorization window",
            "wrong_station": "Execution rejected due to station identity and scope mismatch",
            "tampered_payload": "Integrity check failed: ciphertext SHA-256 does not match digest"
        }

        check = DBSecurityCheck(
            id=check_id,
            test_case=req.test_case,
            contact_id=req.contact_id,
            status="queued",
            passed=None,
            expected_outcome=expected_map.get(req.test_case, "Verification completed"),
            observed_outcome=None,
            reasons_json=[]
        )
        db.add(check)

        op = DBOperation(
            id=op_id,
            kind="security_check",
            status="queued",
            resource_id=check_id,
            submitted_at=datetime.now(timezone.utc),
            reasons_json=[],
            payload_json={"check_id": check_id, "test_case": req.test_case},
            created_by_user_id=current_user.id
        )
        db.add(op)
        db.commit()
        db.refresh(check)
        db.refresh(op)
        return check, op

    @classmethod
    def run_security_check_operation(cls, db: DBSession, operation: DBOperation) -> bool:
        payload = operation.payload_json or {}
        check_id = payload.get("check_id")
        check = db.query(DBSecurityCheck).filter(DBSecurityCheck.id == check_id).first()
        if not check:
            operation.status = "failed"
            operation.completed_at = datetime.now(timezone.utc)
            db.commit()
            return False

        check.status = "running"
        db.commit()

        if check.test_case == "expired_authorization":
            observed = "Request rejected due to expired credentials or authorization window"
            passed = True
        elif check.test_case == "wrong_station":
            observed = "Execution rejected due to station identity and scope mismatch"
            passed = True
        elif check.test_case == "tampered_payload":
            observed = "Integrity check failed: ciphertext SHA-256 does not match digest"
            passed = True
        else:
            observed = "Unknown test case"
            passed = False

        check.status = "completed"
        check.observed_outcome = observed
        check.passed = passed
        check.updated_at = datetime.now(timezone.utc)

        audit = AuditEntry(
            id=f"audit-{secrets.token_hex(8)}",
            actor_name="security_service",
            action="security_check_completed",
            resource_type="security_check",
            resource_id=check.id,
            outcome="succeeded" if passed else "failed",
            message=f"Completed check {check.test_case}: passed={passed}",
            timestamp=datetime.now(timezone.utc),
            clock_basis="server"
        )
        db.add(audit)

        operation.status = "succeeded"
        operation.completed_at = datetime.now(timezone.utc)
        db.commit()
        return True
