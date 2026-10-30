"""
Orbitron Contact Policy Evaluation
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from security.contracts import (
    ACTION_RECEIVE_AND_FORWARD,
    DEFAULT_TOKEN_LIFETIME_SECONDS,
    make_reason,
    parse_iso,
    to_iso_z,
    REASON_AUTHORIZATION_DENIED,
    REASON_PARTNER_NOT_APPROVED,
    REASON_STATION_OFFLINE,
    REASON_UNUSABLE_RESOURCE,
    REASON_UNSUPPORTED_ACTION,
    REASON_BAND_NOT_SUPPORTED,
    REASON_INVALID_CONTACT_BOUNDS,
    REASON_SCOPE_MISMATCH,
    REASON_WRONG_STATION,
)
from security.policy.scopes import build_scope


def evaluate_contact_policy(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate contact authorization policy against backend-constructed trusted context.

    Returns:
        dict: {
            "allowed": bool,
            "reasons": list,
            "scope": dict or None,
            "expires_at": str or None
        }
    """
    reasons: List[Dict[str, Any]] = []

    if not isinstance(context, dict):
        return {
            "allowed": False,
            "reasons": [make_reason(REASON_AUTHORIZATION_DENIED, "Policy context must be a dictionary")],
            "scope": None,
            "expires_at": None
        }

    # Reject client-supplied trust assertions without real backing records
    required_entities = ["job", "satellite", "station", "antenna", "contact"]
    for entity in required_entities:
        val = context.get(entity)
        if not isinstance(val, dict) or not val.get("id"):
            reasons.append(make_reason(
                REASON_AUTHORIZATION_DENIED,
                f"Missing trusted record for '{entity}' in context",
                resource_ids=[entity]
            ))

    if reasons:
        return {
            "allowed": False,
            "reasons": reasons,
            "scope": None,
            "expires_at": None
        }

    job = context["job"]
    satellite = context["satellite"]
    station = context["station"]
    antenna = context["antenna"]
    contact = context["contact"]

    job_id = job.get("id")
    sat_id = satellite.get("id")
    station_id = station.get("id")
    antenna_id = antenna.get("id")
    contact_id = contact.get("id")

    # 1. Structural consistency
    if contact.get("job_id") != job_id:
        reasons.append(make_reason(
            REASON_SCOPE_MISMATCH,
            f"Contact job_id {contact.get('job_id')} does not match job id {job_id}",
            resource_ids=[contact_id, job_id]
        ))

    if job.get("satellite_id") != sat_id:
        reasons.append(make_reason(
            REASON_SCOPE_MISMATCH,
            f"Job satellite_id {job.get('satellite_id')} does not match satellite id {sat_id}",
            resource_ids=[job_id, sat_id]
        ))

    job_owner = job.get("owner_org_id")
    sat_owner = satellite.get("owner_org_id")
    if job_owner != sat_owner:
        reasons.append(make_reason(
            REASON_AUTHORIZATION_DENIED,
            f"Job owner {job_owner} does not match satellite owner {sat_owner}",
            resource_ids=[job_id, sat_id]
        ))

    if contact.get("satellite_id") != sat_id:
        reasons.append(make_reason(
            REASON_SCOPE_MISMATCH,
            f"Contact satellite_id {contact.get('satellite_id')} does not match satellite id {sat_id}",
            resource_ids=[contact_id, sat_id]
        ))

    if antenna.get("station_id") != station_id:
        reasons.append(make_reason(
            REASON_SCOPE_MISMATCH,
            f"Antenna station_id {antenna.get('station_id')} does not match station id {station_id}",
            resource_ids=[antenna_id, station_id]
        ))

    if contact.get("station_id") != station_id:
        reasons.append(make_reason(
            REASON_WRONG_STATION,
            f"Contact station_id {contact.get('station_id')} does not match station id {station_id}",
            resource_ids=[contact_id, station_id]
        ))

    if contact.get("antenna_id") != antenna_id:
        reasons.append(make_reason(
            REASON_SCOPE_MISMATCH,
            f"Contact antenna_id {contact.get('antenna_id')} does not match antenna id {antenna_id}",
            resource_ids=[contact_id, antenna_id]
        ))

    # 2. Band support
    contact_band = contact.get("band")
    supported_bands = antenna.get("supported_bands") or antenna.get("bands") or []
    if isinstance(supported_bands, str):
        supported_bands = [supported_bands]
    if contact_band and supported_bands and contact_band not in supported_bands:
        reasons.append(make_reason(
            REASON_BAND_NOT_SUPPORTED,
            f"Contact band '{contact_band}' is not supported by antenna '{antenna_id}' (supports: {supported_bands})",
            resource_ids=[antenna_id, contact_id]
        ))

    # 3. Contact time bounds
    start_str = contact.get("start_at") or contact.get("window_start_at")
    end_str = contact.get("end_at") or contact.get("window_end_at")
    start_dt = None
    end_dt = None
    if not start_str or not end_str:
        reasons.append(make_reason(
            REASON_INVALID_CONTACT_BOUNDS,
            "Contact missing start_at or end_at timestamp",
            resource_ids=[contact_id]
        ))
    else:
        try:
            start_dt = parse_iso(start_str)
            end_dt = parse_iso(end_str)
            if start_dt >= end_dt:
                reasons.append(make_reason(
                    REASON_INVALID_CONTACT_BOUNDS,
                    f"Contact start_at ({start_str}) must be strictly before end_at ({end_str})",
                    resource_ids=[contact_id]
                ))
        except Exception as e:
            reasons.append(make_reason(
                REASON_INVALID_CONTACT_BOUNDS,
                f"Invalid contact timestamps: {e}",
                resource_ids=[contact_id]
            ))

    # 4. Requested action
    requested_action = context.get("requested_action", ACTION_RECEIVE_AND_FORWARD)
    if requested_action != ACTION_RECEIVE_AND_FORWARD:
        reasons.append(make_reason(
            REASON_UNSUPPORTED_ACTION,
            f"Requested action '{requested_action}' is not supported; only '{ACTION_RECEIVE_AND_FORWARD}' is permitted",
            resource_ids=[contact_id]
        ))

    # 5. Resource usability
    sat_status = satellite.get("operational_status", "operational").lower()
    if sat_status in ["failed", "offline", "maintenance", "degraded_unusable"] or satellite.get("usable") is False:
        reasons.append(make_reason(
            REASON_UNUSABLE_RESOURCE,
            f"Satellite '{sat_id}' is not operational (status={sat_status})",
            resource_ids=[sat_id]
        ))

    station_status = station.get("operational_status", "operational").lower()
    if station_status in ["failed", "offline", "maintenance"] or station.get("usable") is False:
        reasons.append(make_reason(
            REASON_STATION_OFFLINE,
            f"Station '{station_id}' is not operational (status={station_status})",
            resource_ids=[station_id]
        ))

    antenna_status = antenna.get("operational_status", "operational").lower()
    if antenna_status in ["failed", "offline", "maintenance"] or antenna.get("usable") is False:
        reasons.append(make_reason(
            REASON_UNUSABLE_RESOURCE,
            f"Antenna '{antenna_id}' is not operational (status={antenna_status})",
            resource_ids=[antenna_id]
        ))

    contact_status = contact.get("status", "confirmed").lower()
    if contact_status in ["cancelled", "failed"]:
        reasons.append(make_reason(
            REASON_AUTHORIZATION_DENIED,
            f"Contact '{contact_id}' is in terminal/invalid status: {contact_status}",
            resource_ids=[contact_id]
        ))

    # 6. Sharing policy (Section 10)
    station_owner = station.get("owner_org_id")
    if job_owner != station_owner:
        # Partner station: station sharing must be enabled and partner must be approved
        sharing_enabled = station.get("sharing_enabled")
        if sharing_enabled is False:
            reasons.append(make_reason(
                REASON_PARTNER_NOT_APPROVED,
                f"Station '{station_id}' does not have station sharing enabled",
                resource_ids=[station_id]
            ))

        sharing_rel = context.get("sharing_relationship")
        partner_approved = False

        if isinstance(sharing_rel, dict):
            rel_status = sharing_rel.get("status", "").lower()
            rel_partner = sharing_rel.get("partner_org_id") or sharing_rel.get("org_id")
            rel_actions = sharing_rel.get("actions") or sharing_rel.get("allowed_actions") or [ACTION_RECEIVE_AND_FORWARD]
            if isinstance(rel_actions, str):
                rel_actions = [rel_actions]

            if rel_status in ["approved", "active"] and rel_partner == job_owner and ACTION_RECEIVE_AND_FORWARD in rel_actions:
                partner_approved = True
            else:
                reasons.append(make_reason(
                    REASON_PARTNER_NOT_APPROVED,
                    f"Sharing relationship for organization '{job_owner}' is not approved (status={rel_status})",
                    resource_ids=[station_id, job_owner]
                ))
        else:
            approved_partners = (
                station.get("approved_partner_org_ids") or
                station.get("approved_partners") or
                []
            )
            if job_owner in approved_partners:
                partner_approved = True
            else:
                reasons.append(make_reason(
                    REASON_PARTNER_NOT_APPROVED,
                    f"Organization '{job_owner}' is not an approved sharing partner for station '{station_id}'",
                    resource_ids=[station_id, job_owner]
                ))

    if reasons:
        return {
            "allowed": False,
            "reasons": reasons,
            "scope": None,
            "expires_at": None
        }

    # Policy allowed - construct scope and expiration
    scenario_id = context.get("scenario_id", "")
    authorization_id = context.get("authorization_id", "")
    schedule_version = contact.get("schedule_version", 1)

    scope = build_scope(
        scenario_id=scenario_id,
        authorization_id=authorization_id,
        satellite_id=sat_id,
        station_id=station_id,
        antenna_id=antenna_id,
        contact_id=contact_id,
        owner_org_id=job_owner,
        contact_start_at=to_iso_z(start_dt),
        contact_end_at=to_iso_z(end_dt),
        schedule_version=schedule_version,
        allowed_action=ACTION_RECEIVE_AND_FORWARD
    )

    # Expiry calculation: min(server_time + 300s, contact_end_at)
    srv_time_str = context.get("server_time")
    if srv_time_str:
        srv_dt = parse_iso(srv_time_str)
    else:
        srv_dt = datetime.now(timezone.utc)

    token_exp_dt = srv_dt + timedelta(seconds=DEFAULT_TOKEN_LIFETIME_SECONDS)
    # Expiry must not exceed contact_end_at if known
    if end_dt and end_dt < token_exp_dt:
        expires_at_dt = end_dt
    else:
        expires_at_dt = token_exp_dt

    return {
        "allowed": True,
        "reasons": [],
        "scope": scope,
        "expires_at": to_iso_z(expires_at_dt)
    }
