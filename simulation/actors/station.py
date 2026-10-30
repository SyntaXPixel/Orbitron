"""Station gateway actor."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from simulation.contracts import CommandAckRequest, StationHeartbeatRecord


class StationGatewayActor:
    """Represents a virtual ground station gateway process."""

    def __init__(
        self,
        station_id: str,
        owner_org_id: str,
        supported_bands: Optional[List[str]] = None,
        antennas: Optional[List[Dict[str, Any]]] = None,
    ):
        self.station_id: str = station_id
        self.owner_org_id: str = owner_org_id
        self.supported_bands: List[str] = supported_bands or ["S", "X", "Ka"]
        self.antennas: List[Dict[str, Any]] = antennas or []
        self.operational_status: str = "operational"
        self.admin_outage_override: bool = False
        self.sequence: int = 0
        self.confirmed_contacts: Dict[str, Dict[str, Any]] = {}

    def set_outage(self, is_outage: bool) -> None:
        """Set or clear administrative outage."""
        self.admin_outage_override = is_outage
        self.operational_status = "unavailable" if is_outage else "operational"

    def produce_heartbeat(self, scenario_id: str, observed_at: str, event_id: str) -> StationHeartbeatRecord:
        """Assemble current heartbeat record."""
        self.sequence += 1
        status = "unavailable" if self.admin_outage_override else self.operational_status
        return StationHeartbeatRecord(
            event_id=event_id,
            scenario_id=scenario_id,
            sequence=self.sequence,
            station_id=self.station_id,
            observed_at=observed_at,
            operational_status=status,
        )

    def handle_contact_offer(
        self,
        command_id: str,
        payload: Dict[str, Any],
        scenario_id: str,
        event_id: str,
    ) -> CommandAckRequest:
        """Evaluate a contact_offer command and return acknowledgement."""
        contact = payload.get("contact", {})
        contact_id = contact.get("id") or payload.get("contact_id")
        target_station_id = contact.get("station_id") or payload.get("station_id")

        reasons = []

        # 1. Verify destination station
        if target_station_id != self.station_id:
            reasons.append({
                "code": "STATION_MISMATCH",
                "message": f"Contact offered to {target_station_id}, but this gateway is {self.station_id}.",
            })
            return CommandAckRequest(
                event_id=event_id,
                scenario_id=scenario_id,
                status="failed",
                result={"accepted": False, "contact_id": contact_id},
                reasons=reasons,
            )

        # 2. Check operational availability
        if self.admin_outage_override or self.operational_status in ("unavailable", "offline"):
            reasons.append({
                "code": "STATION_UNAVAILABLE",
                "message": f"Station {self.station_id} is currently unavailable due to active outage.",
            })
            return CommandAckRequest(
                event_id=event_id,
                scenario_id=scenario_id,
                status="failed",
                result={"accepted": False, "contact_id": contact_id},
                reasons=reasons,
            )

        # 3. Check band compatibility if specified
        band = contact.get("band")
        if band and band not in self.supported_bands:
            reasons.append({
                "code": "BAND_INCOMPATIBLE",
                "message": f"Band {band} not supported by station {self.station_id} (supported: {self.supported_bands}).",
            })
            return CommandAckRequest(
                event_id=event_id,
                scenario_id=scenario_id,
                status="failed",
                result={"accepted": False, "contact_id": contact_id},
                reasons=reasons,
            )

        # Contact accepted
        if contact_id:
            self.confirmed_contacts[contact_id] = contact

        return CommandAckRequest(
            event_id=event_id,
            scenario_id=scenario_id,
            status="completed",
            result={"accepted": True, "contact_id": contact_id},
            reasons=[{"code": "ACCEPTED", "message": "Station operational and ready for contact."}],
        )

