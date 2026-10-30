"""Gateway server for handling encrypted sample relay."""

from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel

from simulation.contracts import PayloadAssociatedData, TransferProgressRecord
from simulation import security_adapter
from simulation.transport.backend_client import BackendClient

logger = logging.getLogger(__name__)


class GatewayRelayPayload(BaseModel):
    """JSON format payload for sample relay."""
    authorization: str
    scenario_id: str
    contact_id: str
    satellite_id: str
    station_id: str
    owner_org_id: str
    receiver_url: str
    envelope: Dict[str, Any]
    expected_plaintext_sha256: str


def create_gateway_app(
    station_id: str,
    buffer_dir: Path,
    backend_client: Optional[BackendClient] = None,
    public_verification_key: Optional[bytes] = None,
) -> FastAPI:
    """Create a FastAPI application representing a Station Gateway relay process."""
    app = FastAPI(title=f"Station Gateway {station_id}")
    buffer_dir.mkdir(parents=True, exist_ok=True)

    @app.get("/health")
    def health():
        return {"status": "ok", "station_id": station_id}

    @app.post("/relay/{transfer_id}")
    async def relay_sample(
        transfer_id: str,
        request: Request,
        x_contact_authorization: Optional[str] = Header(None),
        x_transfer_scenario_id: Optional[str] = Header(None),
        x_transfer_contact_id: Optional[str] = Header(None),
        x_transfer_satellite_id: Optional[str] = Header(None),
        x_transfer_station_id: Optional[str] = Header(None),
        x_transfer_owner_org_id: Optional[str] = Header(None),
        x_transfer_receiver_url: Optional[str] = Header(None),
        x_expected_plaintext_sha256: Optional[str] = Header(None),
        x_envelope_nonce_b64: Optional[str] = Header(None),
        x_envelope_version: Optional[str] = Header(None),
        x_envelope_algorithm: Optional[str] = Header(None),
    ):
        content_type = request.headers.get("content-type", "")

        # 1. Parse request format (either JSON body or binary body with headers)
        if "application/json" in content_type:
            body_dict = await request.json()
            payload = GatewayRelayPayload(**body_dict)
            auth_token = payload.authorization
            scen_id = payload.scenario_id
            contact_id = payload.contact_id
            satellite_id = payload.satellite_id
            target_station_id = payload.station_id
            owner_org_id = payload.owner_org_id
            receiver_url = payload.receiver_url
            envelope = payload.envelope
            expected_plaintext_sha256 = payload.expected_plaintext_sha256
            ciphertext_bytes = base64.b64decode(envelope["ciphertext_b64"])
        else:
            # Binary body format
            ciphertext_bytes = await request.body()
            auth_token = x_contact_authorization
            scen_id = x_transfer_scenario_id
            contact_id = x_transfer_contact_id
            satellite_id = x_transfer_satellite_id
            target_station_id = x_transfer_station_id
            owner_org_id = x_transfer_owner_org_id
            receiver_url = x_transfer_receiver_url
            expected_plaintext_sha256 = x_expected_plaintext_sha256
            envelope = {
                "version": x_envelope_version or "orbitron.payload.v1",
                "algorithm": x_envelope_algorithm or "AES-256-GCM",
                "nonce_b64": x_envelope_nonce_b64 or "",
                "ciphertext_b64": base64.b64encode(ciphertext_bytes).decode("ascii"),
            }

        # 2. Validation
        if not auth_token:
            raise HTTPException(status_code=401, detail="Missing contact authorization token.")

        if target_station_id and target_station_id != station_id:
            raise HTTPException(
                status_code=403,
                detail=f"Station mismatch: token/request intended for {target_station_id}, gateway is {station_id}."
            )

        # 3. Cryptographic token verification via security adapter
        if public_verification_key:
            try:
                expected_scope = {
                    "station_id": station_id,
                    "contact_id": contact_id,
                    "satellite_id": satellite_id,
                }
                security_adapter.verify_contact_token(
                    token=auth_token,
                    public_key=public_verification_key,
                    expected_scope=expected_scope,
                    server_time="",
                    simulation_time="",
                )
            except Exception as exc:
                raise HTTPException(status_code=403, detail=f"Token verification failed: {exc}")

        # 4. Buffer ciphertext bytes locally (Gateway only touches ciphertext)
        ciphertext_sha256 = hashlib.sha256(ciphertext_bytes).hexdigest()
        buffer_file = buffer_dir / f"{transfer_id}.bin"
        buffer_file.write_bytes(ciphertext_bytes)

        # 5. Forward protected envelope and ciphertext to owner receiver
        if not receiver_url:
            raise HTTPException(status_code=400, detail="Missing receiver URL for forwarding.")

        aad = PayloadAssociatedData(
            scenario_id=scen_id or "",
            transfer_id=transfer_id,
            contact_id=contact_id or "",
            satellite_id=satellite_id or "",
            station_id=station_id,
            owner_org_id=owner_org_id or "",
            expected_plaintext_sha256=expected_plaintext_sha256 or "",
        )

        import httpx
        try:
            forward_body = {
                "scenario_id": scen_id,
                "transfer_id": transfer_id,
                "envelope": envelope,
                "aad": aad.model_dump(),
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                fwd_resp = await client.post(f"{receiver_url.rstrip('/')}/receive/{transfer_id}", json=forward_body)
                if fwd_resp.status_code != 200:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Owner receiver rejected forwarded payload: {fwd_resp.status_code} {fwd_resp.text}"
                    )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Failed to forward to receiver: {exc}")

        # 6. Report gateway transfer progress to backend
        if backend_client and scen_id:
            try:
                progress_record = TransferProgressRecord(
                    event_id=f"prog-{transfer_id}-{station_id}",
                    scenario_id=scen_id,
                    transfer_id=transfer_id,
                    forwarded_bytes=len(ciphertext_bytes),
                    ciphertext_sha256=ciphertext_sha256,
                )
                backend_client.submit_transfer_progress(progress_record)
            except Exception as exc:
                logger.warning("Failed to report transfer progress to backend: %s", exc)

        return {
            "status": "relayed",
            "transfer_id": transfer_id,
            "forwarded_bytes": len(ciphertext_bytes),
            "ciphertext_sha256": ciphertext_sha256,
        }

    return app

