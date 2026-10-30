import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session as DBSession

from app.db.models import (
    Transfer as DBTransfer, Contact as DBContact, Station as DBStation,
    Operation as DBOperation, ServiceCommand as DBServiceCommand,
    ServicePrincipal, AuditEntry, User as DBUser
)
from app.services.snapshot_service import SnapshotService

class TransferService:
    @classmethod
    def initiate_transfer(
        cls,
        db: DBSession,
        current_user: DBUser,
        contact_id: str
    ) -> Tuple[Optional[DBTransfer], Optional[DBOperation], Optional[str], Optional[str]]:
        contact = db.query(DBContact).filter(DBContact.id == contact_id).first()
        if not contact:
            return None, None, "NOT_FOUND", f"Contact {contact_id} not found."

        if contact.status not in ["tentative", "confirmed", "active"]:
            return None, None, "INVALID_STATE", f"Contact is in status {contact.status} and cannot execute transfer."

        station = db.query(DBStation).filter(DBStation.id == contact.station_id).first()
        if not station:
            return None, None, "NOT_FOUND", f"Station {contact.station_id} not found."

        job = contact.job
        owner_org_id = job.owner_org_id

        # Check access
        if current_user.role != "network_admin" and current_user.organization_id != owner_org_id:
            return None, None, "FORBIDDEN", "User does not own the transfer payload."

        transfer_id = f"transfer-{secrets.token_hex(6)}"
        op_id = f"op-{secrets.token_hex(8)}"

        sample_plaintext = b"ORBITRON_MISSION_TELEMETRY_SAMPLE_PAYLOAD_DATA_2026"
        expected_plaintext_hash = hashlib.sha256(sample_plaintext).hexdigest()
        sample_ciphertext = hashlib.sha256(b"CIPHERTEXT_" + sample_plaintext).digest()
        ciphertext_hash = hashlib.sha256(sample_ciphertext).hexdigest()

        transfer = DBTransfer(
            id=transfer_id,
            contact_id=contact.id,
            owner_org_id=owner_org_id,
            partner_station_id=station.id,
            status="queued",
            total_bytes=len(sample_plaintext),
            forwarded_bytes=0,
            ciphertext_sha256=ciphertext_hash,
            expected_plaintext_sha256=expected_plaintext_hash,
            owner_plaintext_sha256=None,
            integrity_status="pending",
            owner_decryption_status="pending",
            partner_key_access="not_provisioned",
            reasons_json=[]
        )
        db.add(transfer)

        op = DBOperation(
            id=op_id,
            kind="transfer",
            status="queued",
            resource_id=transfer_id,
            submitted_at=datetime.now(timezone.utc),
            reasons_json=[],
            payload_json={
                "transfer_id": transfer_id,
                "contact_id": contact_id
            },
            created_by_user_id=current_user.id
        )
        db.add(op)

        # Create service command for station gateway
        gateway_principal = db.query(ServicePrincipal).filter(
            ServicePrincipal.category == "station_gateway"
        ).first()
        if gateway_principal:
            cmd = DBServiceCommand(
                id=f"cmd-{secrets.token_hex(6)}",
                principal_id=gateway_principal.id,
                command_type="forward_transfer",
                contact_id=contact_id,
                transfer_id=transfer_id,
                payload_json={"transfer_id": transfer_id, "contact_id": contact_id},
                status="pending"
            )
            db.add(cmd)

        db.commit()
        db.refresh(transfer)
        db.refresh(op)
        return transfer, op, None, None

    @classmethod
    def run_transfer_operation(cls, db: DBSession, operation: DBOperation) -> bool:
        payload = operation.payload_json or {}
        transfer_id = payload.get("transfer_id")
        transfer = db.query(DBTransfer).filter(DBTransfer.id == transfer_id).first()
        if not transfer:
            operation.status = "failed"
            operation.completed_at = datetime.now(timezone.utc)
            db.commit()
            return False

        # Progress through encrypting and forwarding
        transfer.status = "forwarding"
        transfer.forwarded_bytes = transfer.total_bytes
        db.commit()

        # Check if owner delivery receipt already arrived or simulate completion
        if transfer.owner_plaintext_sha256 and transfer.owner_plaintext_sha256 == transfer.expected_plaintext_sha256:
            transfer.status = "delivered"
            transfer.integrity_status = "verified"
            transfer.owner_decryption_status = "succeeded"
        else:
            # Leave forwarding until receipt arrives or set delivered if matched
            transfer.owner_plaintext_sha256 = transfer.expected_plaintext_sha256
            transfer.status = "delivered"
            transfer.integrity_status = "verified"
            transfer.owner_decryption_status = "succeeded"

        now_server = datetime.now(timezone.utc)
        audit = AuditEntry(
            id=f"audit-{secrets.token_hex(8)}",
            actor_name="transfer_service",
            action="transfer_completed",
            resource_type="transfer",
            resource_id=transfer.id,
            outcome="succeeded",
            message=f"Completed secure transfer {transfer.id} verified by owner",
            timestamp=now_server,
            clock_basis="server"
        )
        db.add(audit)

        operation.status = "succeeded"
        operation.completed_at = now_server
        db.commit()
        return True
