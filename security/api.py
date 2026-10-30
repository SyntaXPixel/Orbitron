"""
Orbitron Security Public API Module
Exposes shared interfaces adhering to contract 'orbitron.v1'
"""

from typing import Dict, Any, Union

from security.contracts import CONTRACT_VERSION
from security.policy.contacts import evaluate_contact_policy
from security.tokens.issuer import issue_contact_token as _issue_token
from security.tokens.verifier import verify_contact_token as _verify_token
from security.payload.encryption import (
    encrypt_payload as _encrypt_payload,
    decrypt_payload as _decrypt_payload,
)
from security.payload.associated_data import canonical_payload_aad as _canonical_aad
from security.testing.challenges import build_security_challenge as _build_challenge
from security.identity.passwords import (
    hash_password as _hash_password,
    verify_password as _verify_password,
    needs_rehash as _needs_rehash,
)


def capabilities() -> Dict[str, Any]:
    """
    Report security module availability and supported capabilities.
    Report true only for fully implemented, usable controls.
    """
    return {
        "contract_version": CONTRACT_VERSION,
        "contact_authorization": True,
        "token_verification": True,
        "payload_encryption": True,
        "security_checks": True,
    }


def evaluate_contact(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate contact authorization policy against backend-constructed trusted records.

    Args:
        context: Dictionary containing job, satellite, station, antenna, contact,
                 optional sharing_relationship, requested_action, simulation_time, server_time.

    Returns:
        dict: {"allowed": bool, "reasons": list, "scope": dict or None, "expires_at": str or None}
    """
    return evaluate_contact_policy(context)


def issue_contact_token(
    context: Dict[str, Any],
    private_key: Union[bytes, str],
) -> Dict[str, Any]:
    """
    Issue an Ed25519-signed contact authorization JWT.

    Args:
        context: Trusted policy context.
        private_key: Ed25519 PKCS#8 PEM private key.

    Returns:
        dict: {"token": str, "expires_at": str, "scope": dict}
    """
    return _issue_token(context=context, private_key=private_key)


def verify_contact_token(
    token: str,
    public_key: Union[bytes, str],
    expected_scope: Dict[str, Any],
    server_time: str,
    simulation_time: str,
) -> Dict[str, Any]:
    """
    Verify a contact authorization JWT against configured trusted public key and expected scope.

    Args:
        token: Signed JWT string.
        public_key: Ed25519 SubjectPublicKeyInfo PEM public key.
        expected_scope: Ground-truth expected resource scope and runtime state.
        server_time: Explicit server clock timestamp (ISO 8601 string).
        simulation_time: Explicit simulation clock timestamp (ISO 8601 string).

    Returns:
        dict: {"allowed": bool, "reasons": list, "claims": dict or None}
    """
    return _verify_token(
        token=token,
        public_key=public_key,
        expected_scope=expected_scope,
        server_time=server_time,
        simulation_time=simulation_time,
    )


def encrypt_payload(
    plaintext: bytes,
    key: bytes,
    associated_data: bytes,
) -> Dict[str, str]:
    """
    Encrypt payload bytes using AES-256-GCM.

    Args:
        plaintext: Raw data bytes (<= 1 MiB).
        key: 32-byte AES-256 key.
        associated_data: Canonical associated data bytes (<= 4 KiB).

    Returns:
        dict: Standard payload envelope with nonce_b64 and ciphertext_b64.
    """
    return _encrypt_payload(
        plaintext=plaintext,
        key=key,
        associated_data=associated_data,
    )


def decrypt_payload(
    envelope: Dict[str, Any],
    key: bytes,
    associated_data: bytes,
) -> bytes:
    """
    Decrypt and verify an AES-256-GCM payload envelope.

    Args:
        envelope: Standard payload envelope dict.
        key: 32-byte AES-256 key.
        associated_data: Canonical associated data bytes.

    Returns:
        bytes: Recovered verified plaintext.
    """
    return _decrypt_payload(
        envelope=envelope,
        key=key,
        associated_data=associated_data,
    )


def canonical_payload_aad(fields: Dict[str, Any]) -> bytes:
    """
    Encode canonical associated data for payload transfer authentication.

    Args:
        fields: Dict with scenario_id, transfer_id, contact_id, satellite_id,
                station_id, owner_org_id, expected_plaintext_sha256.

    Returns:
        bytes: Compact JSON encoded as UTF-8.
    """
    return _canonical_aad(fields=fields)


def build_security_challenge(
    test_case: str,
    context: Dict[str, Any],
    private_key: Union[bytes, str],
) -> Dict[str, Any]:
    """
    Prepare an isolated negative security challenge for controlled testing.

    Args:
        test_case: 'expired_authorization', 'wrong_station', or 'tampered_payload'.
        context: Context dictionary.
        private_key: Issuer Ed25519 private key.

    Returns:
        dict: Test payload and expected outcome description.
    """
    return _build_challenge(
        test_case=test_case,
        context=context,
        private_key=private_key,
    )


# Optional identity helpers for backend auth integration
hash_password = _hash_password
verify_password = _verify_password
needs_rehash = _needs_rehash
