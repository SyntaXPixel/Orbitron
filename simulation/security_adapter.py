"""Security module adapter for the simulation module.

Delegates encryption, decryption, token verification, and canonical AAD encoding
to the security module (security.api).
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional
from simulation.exceptions import IntegrationDependencyError

logger = logging.getLogger(__name__)

# Handlers can be injected for testing or fallback
_encrypt_handler: Optional[Callable[[bytes, bytes, bytes], Dict[str, Any]]] = None
_decrypt_handler: Optional[Callable[[Dict[str, Any], bytes, bytes], bytes]] = None
_verify_token_handler: Optional[Callable[[str, bytes, Dict[str, Any], str, str], Dict[str, Any]]] = None
_canonical_aad_handler: Optional[Callable[[Dict[str, Any]], bytes]] = None


def set_security_handlers(
    encrypt_handler: Optional[Callable[[bytes, bytes, bytes], Dict[str, Any]]] = None,
    decrypt_handler: Optional[Callable[[Dict[str, Any], bytes, bytes], bytes]] = None,
    verify_token_handler: Optional[Callable[[str, bytes, Dict[str, Any], str, str], Dict[str, Any]]] = None,
    canonical_aad_handler: Optional[Callable[[Dict[str, Any]], bytes]] = None,
) -> None:
    """Set custom security handlers (used for testing or dependency injection)."""
    global _encrypt_handler, _decrypt_handler, _verify_token_handler, _canonical_aad_handler
    _encrypt_handler = encrypt_handler
    _decrypt_handler = decrypt_handler
    _verify_token_handler = verify_token_handler
    _canonical_aad_handler = canonical_aad_handler


def is_security_available() -> bool:
    """Check if the security module or custom handlers are available."""
    if _encrypt_handler is not None and _decrypt_handler is not None and _verify_token_handler is not None:
        return True
    try:
        import security.api as sec_api
        return hasattr(sec_api, "encrypt_payload") and hasattr(sec_api, "decrypt_payload") and hasattr(sec_api, "verify_contact_token")
    except ImportError:
        return False


def encrypt_payload(plaintext: bytes, key: bytes, associated_data: bytes) -> Dict[str, Any]:
    """Encrypt payload using AES-256-GCM via the security module."""
    if _encrypt_handler is not None:
        return _encrypt_handler(plaintext, key, associated_data)
    try:
        from security.api import encrypt_payload as sec_encrypt
        return sec_encrypt(plaintext, key, associated_data)
    except (ImportError, AttributeError) as exc:
        raise IntegrationDependencyError("Security module security.api.encrypt_payload is not available.") from exc


def decrypt_payload(envelope: Dict[str, Any], key: bytes, associated_data: bytes) -> bytes:
    """Decrypt payload using AES-256-GCM via the security module."""
    if _decrypt_handler is not None:
        return _decrypt_handler(envelope, key, associated_data)
    try:
        from security.api import decrypt_payload as sec_decrypt
        return sec_decrypt(envelope, key, associated_data)
    except (ImportError, AttributeError) as exc:
        raise IntegrationDependencyError("Security module security.api.decrypt_payload is not available.") from exc


def verify_contact_token(
    token: str,
    public_key: bytes,
    expected_scope: Dict[str, Any],
    server_time: str,
    simulation_time: str,
) -> Dict[str, Any]:
    """Verify contact token via the security module."""
    if _verify_token_handler is not None:
        return _verify_token_handler(token, public_key, expected_scope, server_time, simulation_time)
    try:
        from security.api import verify_contact_token as sec_verify
        return sec_verify(token, public_key, expected_scope, server_time, simulation_time)
    except (ImportError, AttributeError) as exc:
        raise IntegrationDependencyError("Security module security.api.verify_contact_token is not available.") from exc


def canonical_payload_aad(fields: Dict[str, Any]) -> bytes:
    """Encode canonical UTF-8 JSON associated data."""
    if _canonical_aad_handler is not None:
        return _canonical_aad_handler(fields)
    try:
        from security.api import canonical_payload_aad as sec_aad
        return sec_aad(fields)
    except (ImportError, AttributeError):
        # Fallback to standard canonical JSON encoding
        import json
        return json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
