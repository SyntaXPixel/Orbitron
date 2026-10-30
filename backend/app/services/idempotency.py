import hashlib
import json
import secrets
from typing import Optional, Tuple, Any
from sqlalchemy.orm import Session as DBSession
from app.db.models import IdempotencyRecord

def canonical_hash(data: Any) -> str:
    if isinstance(data, (dict, list)):
        serialized = json.dumps(data, sort_keys=True, separators=(',', ':'))
    elif isinstance(data, bytes):
        serialized = data.decode("utf-8", errors="replace")
    elif data is None:
        serialized = ""
    else:
        serialized = str(data)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

class IdempotencyService:
    @classmethod
    def check_idempotency(
        cls,
        db: DBSession,
        key: str,
        principal: str,
        route: str,
        request_hash: str,
        current_scenario_id: str,
    ) -> Tuple[Optional[IdempotencyRecord], Optional[str]]:
        """
        Returns:
            (record, None) if identical match found.
            (None, error_code) if conflict or error.
            (None, None) if new request.
        """
        rec = (
            db.query(IdempotencyRecord)
            .filter(
                IdempotencyRecord.key == key,
                IdempotencyRecord.principal == principal,
                IdempotencyRecord.route == route
            )
            .first()
        )
        if not rec:
            return None, None

        if rec.scenario_id != current_scenario_id:
            return None, "SCENARIO_CHANGED"

        if rec.request_hash != request_hash:
            return None, "PAYLOAD_MISMATCH"

        return rec, None

    @classmethod
    def record_response(
        cls,
        db: DBSession,
        key: str,
        principal: str,
        route: str,
        request_hash: str,
        scenario_id: str,
        status_code: int,
        response_body: str,
        resource_id: Optional[str] = None
    ) -> IdempotencyRecord:
        rec = IdempotencyRecord(
            id=f"idem-{secrets.token_hex(8)}",
            key=key,
            principal=principal,
            route=route,
            request_hash=request_hash,
            scenario_id=scenario_id,
            status_code=status_code,
            response_body=response_body,
            resource_id=resource_id
        )
        db.add(rec)
        db.commit()
        return rec
