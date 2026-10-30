"""
Tests for Contact Policy Evaluation
"""

import pytest
from datetime import datetime, timezone, timedelta
from security.policy.contacts import evaluate_contact_policy
from security.contracts import to_iso_z, parse_iso


@pytest.fixture
def base_context():
    base_time = datetime(2026, 10, 31, 10, 0, 0, tzinfo=timezone.utc)
    srv_time_str = to_iso_z(base_time)
    sim_time_str = to_iso_z(base_time + timedelta(minutes=10))

    return {
        "scenario_id": "scen-pol-01",
        "authorization_id": "auth-pol-01",
        "server_time": srv_time_str,
        "simulation_time": sim_time_str,
        "principal": {
            "id": "user-001",
            "role": "operator",
            "org_id": "org-alpha",
        },
        "satellite": {
            "id": "sat-a-001",
            "owner_org_id": "org-alpha",
            "operational_status": "operational",
            "usable": True,
        },
        "station": {
            "id": "gs-a-001",
            "owner_org_id": "org-alpha",
            "operational_status": "operational",
            "usable": True,
            "sharing_enabled": True,
        },
        "antenna": {
            "id": "ant-a-001",
            "station_id": "gs-a-001",
            "supported_bands": ["X", "S"],
            "operational_status": "operational",
            "usable": True,
        },
        "job": {
            "id": "job-a-001",
            "satellite_id": "sat-a-001",
            "owner_org_id": "org-alpha",
            "status": "scheduled",
        },
        "contact": {
            "id": "contact-a-001",
            "job_id": "job-a-001",
            "satellite_id": "sat-a-001",
            "station_id": "gs-a-001",
            "antenna_id": "ant-a-001",
            "band": "X",
            "start_at": to_iso_z(base_time + timedelta(minutes=5)),
            "end_at": to_iso_z(base_time + timedelta(minutes=25)),
            "status": "confirmed",
            "schedule_version": 1,
        },
        "requested_action": "receive_and_forward",
    }


def test_own_station_request_permitted(base_context):
    result = evaluate_contact_policy(base_context)
    assert result["allowed"] is True
    assert result["reasons"] == []
    assert result["scope"] is not None
    assert result["scope"]["station_id"] == "gs-a-001"
    assert result["scope"]["allowed_action"] == "receive_and_forward"
    assert result["expires_at"] is not None


def test_approved_partner_permitted(base_context):
    # Station owned by org-beta, sharing with org-alpha approved
    base_context["station"]["id"] = "gs-b-001"
    base_context["station"]["owner_org_id"] = "org-beta"
    base_context["antenna"]["station_id"] = "gs-b-001"
    base_context["contact"]["station_id"] = "gs-b-001"
    base_context["station"]["sharing_enabled"] = True
    base_context["sharing_relationship"] = {
        "partner_org_id": "org-alpha",
        "station_id": "gs-b-001",
        "status": "approved",
        "actions": ["receive_and_forward"],
    }

    result = evaluate_contact_policy(base_context)
    assert result["allowed"] is True
    assert result["scope"]["owner_org_id"] == "org-alpha"
    assert result["scope"]["station_id"] == "gs-b-001"


def test_unapproved_partner_denied(base_context):
    base_context["station"]["id"] = "gs-b-001"
    base_context["station"]["owner_org_id"] = "org-beta"
    base_context["antenna"]["station_id"] = "gs-b-001"
    base_context["contact"]["station_id"] = "gs-b-001"
    base_context["station"]["sharing_enabled"] = True
    base_context["sharing_relationship"] = {
        "partner_org_id": "org-gamma",  # Different partner
        "station_id": "gs-b-001",
        "status": "approved",
    }

    result = evaluate_contact_policy(base_context)
    assert result["allowed"] is False
    assert any(r["code"] == "PARTNER_NOT_APPROVED" for r in result["reasons"])
    assert result["scope"] is None


def test_sharing_disabled_station_denied(base_context):
    base_context["station"]["id"] = "gs-b-001"
    base_context["station"]["owner_org_id"] = "org-beta"
    base_context["antenna"]["station_id"] = "gs-b-001"
    base_context["contact"]["station_id"] = "gs-b-001"
    base_context["station"]["sharing_enabled"] = False
    base_context["sharing_relationship"] = {
        "partner_org_id": "org-alpha",
        "station_id": "gs-b-001",
        "status": "approved",
    }

    result = evaluate_contact_policy(base_context)
    assert result["allowed"] is False
    assert any(r["code"] == "PARTNER_NOT_APPROVED" for r in result["reasons"])


def test_privileged_role_does_not_bypass_sharing_policy(base_context):
    # Network administrator cannot bypass partner sharing policy
    base_context["principal"]["role"] = "network_admin"
    base_context["station"]["id"] = "gs-b-001"
    base_context["station"]["owner_org_id"] = "org-beta"
    base_context["antenna"]["station_id"] = "gs-b-001"
    base_context["contact"]["station_id"] = "gs-b-001"
    base_context["station"]["sharing_enabled"] = False  # Sharing disabled

    result = evaluate_contact_policy(base_context)
    assert result["allowed"] is False
    assert any(r["code"] == "PARTNER_NOT_APPROVED" for r in result["reasons"])


def test_wrong_satellite_job_relationship_denied(base_context):
    base_context["job"]["satellite_id"] = "sat-wrong"
    result = evaluate_contact_policy(base_context)
    assert result["allowed"] is False
    assert any(r["code"] == "SCOPE_MISMATCH" for r in result["reasons"])


def test_job_owner_mismatch_denied(base_context):
    base_context["job"]["owner_org_id"] = "org-attacker"
    result = evaluate_contact_policy(base_context)
    assert result["allowed"] is False
    assert any(r["code"] == "AUTHORIZATION_DENIED" for r in result["reasons"])


def test_wrong_antenna_station_relationship_denied(base_context):
    base_context["antenna"]["station_id"] = "gs-other"
    result = evaluate_contact_policy(base_context)
    assert result["allowed"] is False
    assert any(r["code"] == "SCOPE_MISMATCH" for r in result["reasons"])


def test_unsupported_action_denied(base_context):
    base_context["requested_action"] = "satellite_telecommand"
    result = evaluate_contact_policy(base_context)
    assert result["allowed"] is False
    assert any(r["code"] == "UNSUPPORTED_ACTION" for r in result["reasons"])


def test_cancelled_contact_denied(base_context):
    base_context["contact"]["status"] = "cancelled"
    result = evaluate_contact_policy(base_context)
    assert result["allowed"] is False
    assert any(r["code"] == "AUTHORIZATION_DENIED" for r in result["reasons"])


def test_unusable_resource_denied(base_context):
    base_context["satellite"]["operational_status"] = "failed"
    result = evaluate_contact_policy(base_context)
    assert result["allowed"] is False
    assert any(r["code"] == "UNUSABLE_RESOURCE" for r in result["reasons"])

    base_context["satellite"]["operational_status"] = "operational"
    base_context["station"]["operational_status"] = "offline"
    result2 = evaluate_contact_policy(base_context)
    assert result2["allowed"] is False
    assert any(r["code"] == "STATION_OFFLINE" for r in result2["reasons"])


def test_untrusted_client_assertion_rejected():
    fake_context = {
        "authenticated": True,
        "role": "network_admin",
        "partner_approved": True,
    }
    result = evaluate_contact_policy(fake_context)
    assert result["allowed"] is False
    assert any(r["code"] == "AUTHORIZATION_DENIED" for r in result["reasons"])


def test_unsupported_band_denied(base_context):
    base_context["contact"]["band"] = "Ka"  # Antenna supports only X, S
    result = evaluate_contact_policy(base_context)
    assert result["allowed"] is False
    assert any(r["code"] == "BAND_NOT_SUPPORTED" for r in result["reasons"])


def test_invalid_bounds_denied(base_context):
    base_context["contact"]["start_at"] = "2026-10-31T10:30:00Z"
    base_context["contact"]["end_at"] = "2026-10-31T10:15:00Z"  # end before start
    result = evaluate_contact_policy(base_context)
    assert result["allowed"] is False
    assert any(r["code"] == "INVALID_CONTACT_BOUNDS" for r in result["reasons"])
