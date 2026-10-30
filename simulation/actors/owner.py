"""Owner receiver actor."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional
from simulation.contracts import DeliveryReceiptRecord, PayloadAssociatedData
from simulation import security_adapter


class OwnerReceiverActor:
    """Represents an organization's owner receiver process.

    Possesses payload decryption keys and performs authenticated decryption and verification.
    """

    def __init__(
        self,
        owner_org_id: str,
        payload_key: bytes,
        verified_storage_dir: Optional[Path] = None,
    ):
        self.owner_org_id: str = owner_org_id
        self.payload_key: bytes = payload_key
        self.verified_storage_dir: Optional[Path] = verified_storage_dir

    def receive_and_verify(
        self,
        transfer_id: str,
        envelope: Dict[str, Any],
        aad: PayloadAssociatedData,
        scenario_id: str,
        event_id: str,
    ) -> DeliveryReceiptRecord:
        """Decrypt forwarded ciphertext and verify integrity."""
        aad_bytes = aad.to_canonical_bytes()

        try:
            recovered_plaintext = security_adapter.decrypt_payload(
                envelope=envelope,
                key=self.payload_key,
                associated_data=aad_bytes,
            )
        except Exception:
            # Decryption failed (tampered ciphertext, invalid key, or invalid AAD tag)
            return DeliveryReceiptRecord(
                event_id=event_id,
                scenario_id=scenario_id,
                transfer_id=transfer_id,
                owner_plaintext_sha256="",
                integrity_status="corrupted",
                owner_decryption_status="failed",
            )

        recovered_sha256 = hashlib.sha256(recovered_plaintext).hexdigest()

        if recovered_sha256 != aad.expected_plaintext_sha256:
            return DeliveryReceiptRecord(
                event_id=event_id,
                scenario_id=scenario_id,
                transfer_id=transfer_id,
                owner_plaintext_sha256=recovered_sha256,
                integrity_status="mismatch",
                owner_decryption_status="success",
            )

        # Integrity verified - persist verified output safely
        if self.verified_storage_dir:
            self.verified_storage_dir.mkdir(parents=True, exist_ok=True)
            output_file = self.verified_storage_dir / f"{transfer_id}.bin"
            output_file.write_bytes(recovered_plaintext)

        return DeliveryReceiptRecord(
            event_id=event_id,
            scenario_id=scenario_id,
            transfer_id=transfer_id,
            owner_plaintext_sha256=recovered_sha256,
            integrity_status="verified",
            owner_decryption_status="success",
        )

