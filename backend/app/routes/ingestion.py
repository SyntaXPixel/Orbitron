from typing import Dict, Any, List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as DBSession

from app.db.session import get_db
from app.db.models import ServiceCommand as DBServiceCommand, Contact as DBContact
from app.schemas.ingestion import (
    CatalogIngestRequest, TelemetryIngestRequest, StationHeartbeatRequest,
    ContactProgressRequest, TickIngestRequest, CommandAckRequest,
    TransferProgressRequest, DeliveryReceiptRequest
)
from app.schemas.public import to_iso_z
from app.services.ingestion_service import IngestionService
from app.routes.deps import get_service_principal, OrbitronAPIException

router = APIRouter(tags=["Service Ingestion"])

@router.post("/ingest/catalog", status_code=status.HTTP_200_OK)
def ingest_catalog(
    req: CatalogIngestRequest,
    principal_tuple=Depends(get_service_principal),
    db: DBSession = Depends(get_db)
):
    principal, _ = principal_tuple
    ok, err_code, err_msg = IngestionService.ingest_catalog(db, principal, req)
    if not ok:
        if err_code == "FORBIDDEN":
            raise OrbitronAPIException(status_code=status.HTTP_403_FORBIDDEN, code=err_code, message=err_msg)
        elif err_code in ["SCENARIO_CHANGED", "EVENT_PAYLOAD_MISMATCH"]:
            raise OrbitronAPIException(status_code=status.HTTP_409_CONFLICT, code=err_code, message=err_msg)
        else:
            raise OrbitronAPIException(status_code=status.HTTP_400_BAD_REQUEST, code=err_code or "ERROR", message=err_msg or "Failed")
    return {"status": "accepted"}

@router.post("/ingest/telemetry", status_code=status.HTTP_200_OK)
def ingest_telemetry(
    req: TelemetryIngestRequest,
    principal_tuple=Depends(get_service_principal),
    db: DBSession = Depends(get_db)
):
    principal, _ = principal_tuple
    ok, err_code, err_msg = IngestionService.ingest_telemetry(db, principal, req)
    if not ok:
        if err_code == "FORBIDDEN":
            raise OrbitronAPIException(status_code=status.HTTP_403_FORBIDDEN, code=err_code, message=err_msg)
        elif err_code in ["SCENARIO_CHANGED", "EVENT_PAYLOAD_MISMATCH"]:
            raise OrbitronAPIException(status_code=status.HTTP_409_CONFLICT, code=err_code, message=err_msg)
        elif err_code == "NOT_FOUND":
            raise OrbitronAPIException(status_code=status.HTTP_404_NOT_FOUND, code=err_code, message=err_msg)
        else:
            raise OrbitronAPIException(status_code=status.HTTP_400_BAD_REQUEST, code=err_code or "ERROR", message=err_msg or "Failed")
    return {"status": "accepted"}

@router.post("/ingest/station-heartbeats", status_code=status.HTTP_200_OK)
def ingest_station_heartbeat(
    req: StationHeartbeatRequest,
    principal_tuple=Depends(get_service_principal),
    db: DBSession = Depends(get_db)
):
    principal, _ = principal_tuple
    ok, err_code, err_msg = IngestionService.ingest_station_heartbeat(db, principal, req)
    if not ok:
        if err_code == "FORBIDDEN":
            raise OrbitronAPIException(status_code=status.HTTP_403_FORBIDDEN, code=err_code, message=err_msg)
        elif err_code in ["SCENARIO_CHANGED", "EVENT_PAYLOAD_MISMATCH"]:
            raise OrbitronAPIException(status_code=status.HTTP_409_CONFLICT, code=err_code, message=err_msg)
        elif err_code == "NOT_FOUND":
            raise OrbitronAPIException(status_code=status.HTTP_404_NOT_FOUND, code=err_code, message=err_msg)
        else:
            raise OrbitronAPIException(status_code=status.HTTP_400_BAD_REQUEST, code=err_code or "ERROR", message=err_msg or "Failed")
    return {"status": "accepted"}

@router.post("/ingest/contact-progress", status_code=status.HTTP_200_OK)
def ingest_contact_progress(
    req: ContactProgressRequest,
    principal_tuple=Depends(get_service_principal),
    db: DBSession = Depends(get_db)
):
    principal, _ = principal_tuple
    ok, err_code, err_msg = IngestionService.ingest_contact_progress(db, principal, req)
    if not ok:
        if err_code == "FORBIDDEN":
            raise OrbitronAPIException(status_code=status.HTTP_403_FORBIDDEN, code=err_code, message=err_msg)
        elif err_code in ["SCENARIO_CHANGED", "EVENT_PAYLOAD_MISMATCH"]:
            raise OrbitronAPIException(status_code=status.HTTP_409_CONFLICT, code=err_code, message=err_msg)
        elif err_code == "NOT_FOUND":
            raise OrbitronAPIException(status_code=status.HTTP_404_NOT_FOUND, code=err_code, message=err_msg)
        else:
            raise OrbitronAPIException(status_code=status.HTTP_400_BAD_REQUEST, code=err_code or "ERROR", message=err_msg or "Failed")
    return {"status": "accepted"}

@router.post("/ingest/ticks", status_code=status.HTTP_200_OK)
def ingest_ticks(
    req: TickIngestRequest,
    principal_tuple=Depends(get_service_principal),
    db: DBSession = Depends(get_db)
):
    principal, _ = principal_tuple
    ok, err_code, err_msg = IngestionService.ingest_ticks(db, principal, req)
    if not ok:
        if err_code == "FORBIDDEN":
            raise OrbitronAPIException(status_code=status.HTTP_403_FORBIDDEN, code=err_code, message=err_msg)
        elif err_code in ["SCENARIO_CHANGED", "EVENT_PAYLOAD_MISMATCH"]:
            raise OrbitronAPIException(status_code=status.HTTP_409_CONFLICT, code=err_code, message=err_msg)
        elif err_code == "SIMULATION_PAUSED":
            raise OrbitronAPIException(status_code=status.HTTP_409_CONFLICT, code=err_code, message=err_msg)
        else:
            raise OrbitronAPIException(status_code=status.HTTP_400_BAD_REQUEST, code=err_code or "ERROR", message=err_msg or "Failed")
    return {"status": "accepted"}

@router.get("/service/work")
def get_service_work(
    principal_tuple=Depends(get_service_principal),
    db: DBSession = Depends(get_db)
):
    principal, _ = principal_tuple
    commands = (
        db.query(DBServiceCommand)
        .filter(DBServiceCommand.principal_id == principal.id, DBServiceCommand.status == "pending")
        .all()
    )

    permitted_station_ids = (principal.permitted_resources_json or {}).get("station_ids", [])
    relevant_contacts = []
    if principal.category == "station_gateway" and permitted_station_ids:
        contacts = (
            db.query(DBContact)
            .filter(DBContact.station_id.in_(permitted_station_ids), DBContact.status.in_(["tentative", "confirmed", "active"]))
            .all()
        )
        relevant_contacts = [
            {
                "id": c.id,
                "satellite_id": c.satellite_id,
                "station_id": c.station_id,
                "antenna_id": c.antenna_id,
                "start_at": to_iso_z(c.start_at),
                "end_at": to_iso_z(c.end_at),
                "expected_rate_bps": c.expected_rate_bps,
                "status": c.status,
                "schedule_version": c.schedule_version
            }
            for c in contacts
        ]

    return {
        "principal_id": principal.id,
        "category": principal.category,
        "pending_commands": [
            {
                "id": cmd.id,
                "command_type": cmd.command_type,
                "contact_id": cmd.contact_id,
                "transfer_id": cmd.transfer_id,
                "payload": cmd.payload_json,
                "status": cmd.status
            }
            for cmd in commands
        ],
        "assigned_contacts": relevant_contacts
    }

@router.post("/service/commands/{command_id}/ack", status_code=status.HTTP_200_OK)
def acknowledge_command(
    command_id: str,
    req: CommandAckRequest,
    principal_tuple=Depends(get_service_principal),
    db: DBSession = Depends(get_db)
):
    principal, _ = principal_tuple
    cmd = db.query(DBServiceCommand).filter(DBServiceCommand.id == command_id).first()
    if not cmd:
        raise OrbitronAPIException(status_code=status.HTTP_404_NOT_FOUND, code="NOT_FOUND", message=f"Command {command_id} not found")

    if cmd.principal_id != principal.id and principal.category != "simulator_controller":
        raise OrbitronAPIException(status_code=status.HTTP_403_FORBIDDEN, code="FORBIDDEN", message="Principal not authorized to acknowledge this command")

    cmd.status = req.status
    cmd.result_json = req.result
    cmd.reasons_json = req.reasons

    # If contact confirmation command
    if cmd.command_type == "confirm_contact" and cmd.contact_id and req.status == "completed":
        contact = db.query(DBContact).filter(DBContact.id == cmd.contact_id).first()
        if contact and contact.status == "tentative":
            contact.status = "confirmed"

    db.commit()
    return {"status": "acknowledged"}

@router.post("/ingest/transfer-progress", status_code=status.HTTP_200_OK)
def ingest_transfer_progress(
    req: TransferProgressRequest,
    principal_tuple=Depends(get_service_principal),
    db: DBSession = Depends(get_db)
):
    principal, _ = principal_tuple
    ok, err_code, err_msg = IngestionService.ingest_transfer_progress(db, principal, req)
    if not ok:
        if err_code in ["SCENARIO_CHANGED", "EVENT_PAYLOAD_MISMATCH"]:
            raise OrbitronAPIException(status_code=status.HTTP_409_CONFLICT, code=err_code, message=err_msg)
        elif err_code == "NOT_FOUND":
            raise OrbitronAPIException(status_code=status.HTTP_404_NOT_FOUND, code=err_code, message=err_msg)
        else:
            raise OrbitronAPIException(status_code=status.HTTP_400_BAD_REQUEST, code=err_code or "ERROR", message=err_msg or "Failed")
    return {"status": "accepted"}

@router.post("/ingest/delivery-receipts", status_code=status.HTTP_200_OK)
def ingest_delivery_receipt(
    req: DeliveryReceiptRequest,
    principal_tuple=Depends(get_service_principal),
    db: DBSession = Depends(get_db)
):
    principal, _ = principal_tuple
    ok, err_code, err_msg = IngestionService.ingest_delivery_receipt(db, principal, req)
    if not ok:
        if err_code == "FORBIDDEN":
            raise OrbitronAPIException(status_code=status.HTTP_403_FORBIDDEN, code=err_code, message=err_msg)
        elif err_code in ["SCENARIO_CHANGED", "EVENT_PAYLOAD_MISMATCH"]:
            raise OrbitronAPIException(status_code=status.HTTP_409_CONFLICT, code=err_code, message=err_msg)
        elif err_code == "NOT_FOUND":
            raise OrbitronAPIException(status_code=status.HTTP_404_NOT_FOUND, code=err_code, message=err_msg)
        else:
            raise OrbitronAPIException(status_code=status.HTTP_400_BAD_REQUEST, code=err_code or "ERROR", message=err_msg or "Failed")
    return {"status": "accepted"}
