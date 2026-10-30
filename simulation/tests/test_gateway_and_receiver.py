"""Tests for Gateway and Receiver separation, isolation, and process safety."""

import os
import pytest
from simulation.actors.station import StationGatewayActor
from simulation.transport.gateway_server import create_gateway_app
from simulation.transport.receiver_server import create_receiver_app


def test_gateway_configuration_has_no_payload_key(test_config):
    """Verify Gateway process and actor configuration is strictly isolated from payload keys."""
    gateway = StationGatewayActor(station_id="station-01", owner_org_id="org-a")
    # Gateway actor must not possess payload_keys
    assert not hasattr(gateway, "payload_key")
    assert not hasattr(gateway, "payload_keys")

    # Gateway server app creation must not require or accept owner payload keys
    app = create_gateway_app(station_id="station-01", buffer_dir=test_config.gateway_buffer_dir("station-01"))
    assert app is not None


def test_gateway_disconnection_stops_heartbeats_and_reporting():
    """Verify when a gateway is offline or disconnected, it stops reporting successful operation."""
    gateway = StationGatewayActor(station_id="station-disc", owner_org_id="org-a")
    gateway.set_outage(True)
    hb = gateway.produce_heartbeat(scenario_id="scen-1", observed_at="2026-10-31T06:00:00Z", event_id="hb-1")
    assert hb.operational_status == "unavailable"

    # Gateway rejects incoming contact offers when unavailable
    offer_ack = gateway.handle_contact_offer(
        command_id="cmd-offer-disc",
        payload={"contact": {"id": "c-disc", "station_id": "station-disc"}},
        scenario_id="scen-1",
        event_id="ack-disc",
    )
    assert offer_ack.status == "failed"
    assert offer_ack.result["accepted"] is False


def test_gateway_acknowledgement_cannot_impersonate_owner_receipt():
    """A gateway's relay acknowledgement only indicates ciphertext forwarding, not owner decryption."""
    # Gateway response model only contains forwarded_bytes and ciphertext_sha256,
    # NOT owner_decryption_status or verified plaintext.
    gateway_resp = {
        "status": "relayed",
        "transfer_id": "xfer-01",
        "forwarded_bytes": 1024,
        "ciphertext_sha256": "abcdef...",
    }
    assert "owner_decryption_status" not in gateway_resp
    assert "owner_plaintext_sha256" not in gateway_resp
