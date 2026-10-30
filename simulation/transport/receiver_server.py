"""Receiver server for handling owner sample decryption and verification."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from simulation.actors.owner import OwnerReceiverActor
from simulation.contracts import DeliveryReceiptRecord, PayloadAssociatedData
from simulation.transport.backend_client import BackendClient

logger = logging.getLogger(__name__)


class ReceiverPayload(BaseModel):
    """Payload received by owner receiver."""
    scenario_id: str
    transfer_id: str
    envelope: Dict[str, Any]
    aad: Dict[str, Any]


def create_receiver_app(
    owner_org_id: str,
    payload_key: bytes,
    verified_dir: Path,
    backend_client: Optional[BackendClient] = None,
) -> FastAPI:
    """Create a FastAPI application representing an Owner Receiver process."""
    app = FastAPI(title=f"Owner Receiver {owner_org_id}")
    actor = OwnerReceiverActor(
        owner_org_id=owner_org_id,
        payload_key=payload_key,
        verified_storage_dir=verified_dir,
    )

    @app.get("/health")
    def health():
        return {"status": "ok", "owner_org_id": owner_org_id}

    @app.post("/receive/{transfer_id}")
    def receive_sample(transfer_id: str, payload: ReceiverPayload):
        aad = PayloadAssociatedData(**payload.aad)
        event_id = f"rcpt-{transfer_id}-{owner_org_id}"

        # Decrypt, verify hash and persist only upon verification
        receipt: DeliveryReceiptRecord = actor.receive_and_verify(
            transfer_id=transfer_id,
            envelope=payload.envelope,
            aad=aad,
            scenario_id=payload.scenario_id,
            event_id=event_id,
        )

        # Submit delivery receipt to backend
        if backend_client:
            try:
                backend_client.submit_delivery_receipt(receipt)
            except Exception as exc:
                logger.warning("Failed to submit delivery receipt to backend: %s", exc)

        if receipt.owner_decryption_status == "failed":
            raise HTTPException(
                status_code=400,
                detail=f"Authenticated decryption failed (integrity: {receipt.integrity_status})"
            )

        if receipt.integrity_status != "verified":
            raise HTTPException(
                status_code=400,
                detail=f"Plaintext SHA256 mismatch (status: {receipt.integrity_status})"
            )

        return receipt.model_dump()

    return app
