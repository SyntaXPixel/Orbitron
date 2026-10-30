"""Disruptions, weather, and fault tracking."""

from __future__ import annotations

from typing import Dict, Optional
from pydantic import BaseModel, Field


class SatelliteFaultState(BaseModel):
    """Tracks operational faults for a single satellite."""
    comms_fault: bool = False
    instrument_fault: bool = False
    offline: bool = False


class StationDisruptionState(BaseModel):
    """Tracks weather and outage disruptions for a ground station."""
    rain_capacity_factor: float = 1.0
    admin_outage_override: bool = False
    is_operational: bool = True


class FaultsManager:
    """Maintains active operational faults and disruption overrides."""

    def __init__(self):
        self.satellite_faults: Dict[str, SatelliteFaultState] = {}
        self.station_disruptions: Dict[str, StationDisruptionState] = {}

    def get_satellite_fault(self, satellite_id: str) -> SatelliteFaultState:
        if satellite_id not in self.satellite_faults:
            self.satellite_faults[satellite_id] = SatelliteFaultState()
        return self.satellite_faults[satellite_id]

    def get_station_disruption(self, station_id: str) -> StationDisruptionState:
        if station_id not in self.station_disruptions:
            self.station_disruptions[station_id] = StationDisruptionState()
        return self.station_disruptions[station_id]

    def apply_rain(self, station_id: str, capacity_factor: float) -> None:
        disruption = self.get_station_disruption(station_id)
        disruption.rain_capacity_factor = max(0.0, min(1.0, capacity_factor))

    def apply_station_outage(self, station_id: str) -> None:
        disruption = self.get_station_disruption(station_id)
        disruption.admin_outage_override = True
        disruption.is_operational = False

    def apply_station_recovery(self, station_id: str) -> None:
        disruption = self.get_station_disruption(station_id)
        disruption.admin_outage_override = False
        disruption.is_operational = True
        disruption.rain_capacity_factor = 1.0

    def apply_satellite_fault(self, satellite_id: str, comms_fault: bool = False, instrument_fault: bool = False) -> None:
        state = self.get_satellite_fault(satellite_id)
        state.comms_fault = comms_fault
        state.instrument_fault = instrument_fault
