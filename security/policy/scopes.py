"""
Orbitron Contact Authorization Scope Definitions and Helpers
"""

from typing import Dict, Any, Optional
from security.contracts import ACTION_RECEIVE_AND_FORWARD

REQUIRED_SCOPE_FIELDS = (
    "scenario_id",
    "authorization_id",
    "satellite_id",
    "station_id",
    "antenna_id",
    "contact_id",
    "owner_org_id",
    "allowed_action",
    "contact_start_at",
    "contact_end_at",
    "schedule_version",
)


def build_scope(
    scenario_id: str,
    authorization_id: str,
    satellite_id: str,
    station_id: str,
    antenna_id: str,
    contact_id: str,
    owner_org_id: str,
    contact_start_at: str,
    contact_end_at: str,
    schedule_version: int = 1,
    allowed_action: str = ACTION_RECEIVE_AND_FORWARD,
) -> Dict[str, Any]:
    """Construct a canonical scope dictionary."""
    return {
        "scenario_id": str(scenario_id),
        "authorization_id": str(authorization_id),
        "satellite_id": str(satellite_id),
        "station_id": str(station_id),
        "antenna_id": str(antenna_id),
        "contact_id": str(contact_id),
        "owner_org_id": str(owner_org_id),
        "allowed_action": str(allowed_action),
        "contact_start_at": str(contact_start_at),
        "contact_end_at": str(contact_end_at),
        "schedule_version": int(schedule_version),
    }


def validate_scope(scope: Dict[str, Any]) -> bool:
    """Validate that all required scope fields are present and valid."""
    if not isinstance(scope, dict):
        return False
    for field in REQUIRED_SCOPE_FIELDS:
        if field not in scope or scope[field] is None:
            return False
    if scope["allowed_action"] != ACTION_RECEIVE_AND_FORWARD:
        return False
    return True
