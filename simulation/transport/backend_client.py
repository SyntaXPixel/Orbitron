"""HTTP client for backend service and ingestion endpoints."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional
import httpx

from simulation.contracts import (
    AtomicTickRequest,
    CommandAckRequest,
    ContactProgressRecord,
    DeliveryReceiptRecord,
    JobCreateRequest,
    StationHeartbeatRecord,
    TelemetryRecord,
    TransferProgressRecord,
)
from simulation.exceptions import ContractValidationError, SimulationError

logger = logging.getLogger(__name__)


class BackendClient:
    """Client for interacting with Orbitron backend ingestion and service APIs."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/api/v1",
        default_token: Optional[str] = None,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ):
        self.base_url: str = base_url.rstrip("/")
        self.default_token: Optional[str] = default_token
        self.timeout_seconds: float = timeout_seconds
        self.max_retries: int = max_retries
        self.backoff_factor: float = backoff_factor
        self._client: httpx.Client = httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BackendClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _headers(
        self,
        token: Optional[str] = None,
        scenario_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        auth_token = token or self.default_token
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        if scenario_id:
            headers["X-Orbitron-Scenario-ID"] = scenario_id
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _request_with_retry(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        scenario_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        headers = self._headers(token=token, scenario_id=scenario_id, idempotency_key=idempotency_key)

        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._client.request(
                    method=method,
                    url=url,
                    json=json_body,
                    headers=headers,
                )

                # Do not retry 4xx errors (client errors)
                if 400 <= response.status_code < 500:
                    return response

                # Retry 5xx server errors
                if response.status_code >= 500:
                    if attempt >= self.max_retries:
                        return response
                    sleep_time = self.backoff_factor * (2 ** (attempt - 1))
                    time.sleep(sleep_time)
                    continue

                return response

            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    raise SimulationError(f"Backend network request failed after {attempt} attempts: {exc}") from exc
                sleep_time = self.backoff_factor * (2 ** (attempt - 1))
                time.sleep(sleep_time)

    def get_service_work(self, token: Optional[str] = None) -> Dict[str, Any]:
        """Fetch scoped service work and pending commands."""
        resp = self._request_with_retry("GET", "/service/work", token=token)
        if resp.status_code != 200:
            raise SimulationError(f"Failed to fetch /service/work: status {resp.status_code}, {resp.text}")
        return resp.json()

    def submit_tick(self, tick: AtomicTickRequest, token: Optional[str] = None) -> httpx.Response:
        """Submit atomic simulation tick."""
        return self._request_with_retry(
            "POST",
            "/ingest/ticks",
            json_body=tick.model_dump(),
            token=token,
            scenario_id=tick.scenario_id,
        )

    def submit_telemetry(self, telemetry: TelemetryRecord, token: Optional[str] = None) -> httpx.Response:
        return self._request_with_retry(
            "POST",
            "/ingest/telemetry",
            json_body=telemetry.model_dump(),
            token=token,
            scenario_id=telemetry.scenario_id,
        )

    def submit_station_heartbeat(self, heartbeat: StationHeartbeatRecord, token: Optional[str] = None) -> httpx.Response:
        return self._request_with_retry(
            "POST",
            "/ingest/station-heartbeats",
            json_body=heartbeat.model_dump(),
            token=token,
            scenario_id=heartbeat.scenario_id,
        )

    def submit_contact_progress(self, progress: ContactProgressRecord, token: Optional[str] = None) -> httpx.Response:
        return self._request_with_retry(
            "POST",
            "/ingest/contact-progress",
            json_body=progress.model_dump(),
            token=token,
            scenario_id=progress.scenario_id,
        )

    def submit_transfer_progress(self, progress: TransferProgressRecord, token: Optional[str] = None) -> httpx.Response:
        return self._request_with_retry(
            "POST",
            "/ingest/transfer-progress",
            json_body=progress.model_dump(),
            token=token,
            scenario_id=progress.scenario_id,
        )

    def submit_delivery_receipt(self, receipt: DeliveryReceiptRecord, token: Optional[str] = None) -> httpx.Response:
        return self._request_with_retry(
            "POST",
            "/ingest/delivery-receipts",
            json_body=receipt.model_dump(),
            token=token,
            scenario_id=receipt.scenario_id,
        )

    def acknowledge_command(self, command_id: str, ack: CommandAckRequest, token: Optional[str] = None) -> httpx.Response:
        return self._request_with_retry(
            "POST",
            f"/service/commands/{command_id}/ack",
            json_body=ack.model_dump(),
            token=token,
            scenario_id=ack.scenario_id,
        )

    def create_job(
        self,
        job: JobCreateRequest,
        scenario_id: str,
        idempotency_key: str,
        token: Optional[str] = None,
    ) -> httpx.Response:
        return self._request_with_retry(
            "POST",
            "/jobs",
            json_body=job.model_dump(),
            token=token,
            scenario_id=scenario_id,
            idempotency_key=idempotency_key,
        )
