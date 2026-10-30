"""
Orbitron Security Evidence and Audit Helpers
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from security.contracts import to_iso_z


def sanitize_audit_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce safe audit metadata by stripping secrets, keys, and passwords.
    Never returns private keys, passwords, raw session tokens, or owner plaintext.
    """
    safe: Dict[str, Any] = {}
    forbidden_keys = {"password", "private_key", "plaintext", "key", "token", "password_hash", "session_token"}

    for k, v in context.items():
        if k.lower() in forbidden_keys:
            continue
        if isinstance(v, dict):
            safe[k] = sanitize_audit_context(v)
        elif isinstance(v, (str, int, float, bool, list)):
            safe[k] = v
    return safe


def build_evidence_record(
    check_id: str,
    test_case: str,
    passed: bool,
    expected_outcome: str,
    observed_outcome: str,
    reasons: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Construct an audit-safe SecurityCheck record matching the Orbitron contract."""
    return {
        "id": check_id,
        "test_case": test_case,
        "status": "completed",
        "passed": bool(passed),
        "expected_outcome": expected_outcome,
        "observed_outcome": observed_outcome,
        "reasons": reasons or [],
        "timestamp": to_iso_z(datetime.now(timezone.utc)),
    }
