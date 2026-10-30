"""Contact progress calculation and transmission accounting.

Implements integer-microsecond fractional credit tracking and ensures
downlink progress strictly obeys visibility, setup, authorization and capacity constraints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel


def parse_utc(dt_str: str) -> datetime:
    """Parse ISO8601 UTC timestamp ending in Z."""
    clean = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(clean).astimezone(timezone.utc)


class ContactExecutionState(BaseModel):
    """Tracks state and progress of an active contact."""
    contact_id: str
    job_id: str
    satellite_id: str
    station_id: str
    antenna_id: str
    setup_start_at: str
    start_at: str
    end_at: str
    allocated_bytes: int
    expected_rate_bps: int
    cumulative_transferred_bytes: int = 0
    credit_microbits: int = 0  # Microseconds * bps / 8,000,000 credit
    is_completed: bool = False


class ContactProgressTracker:
    """Evaluates and records simulated mission-data transmission for contacts."""

    def __init__(self, contact_data: Dict[str, Any]):
        self.contact_id: str = contact_data["id"]
        self.job_id: str = contact_data["job_id"]
        self.satellite_id: str = contact_data["satellite_id"]
        self.station_id: str = contact_data["station_id"]
        self.antenna_id: str = contact_data.get("antenna_id", "")
        self.setup_start_at: datetime = parse_utc(contact_data.get("setup_start_at", contact_data["start_at"]))
        self.start_at: datetime = parse_utc(contact_data["start_at"])
        self.end_at: datetime = parse_utc(contact_data["end_at"])
        self.allocated_bytes: int = contact_data.get("allocated_bytes", 0)
        self.expected_rate_bps: int = contact_data.get("expected_rate_bps", 100_000_000)

        self.cumulative_transferred_bytes: int = contact_data.get("transferred_bytes", 0)
        self.credit_microbits: int = 0
        self.is_final: bool = False

    def calculate_tick_progress(
        self,
        tick_start: datetime,
        tick_end: datetime,
        contact_status: str,
        has_allowed_authorization: bool,
        station_is_operational: bool,
        satellite_is_operational: bool,
        weather_capacity_factor: float = 1.0,
        satellite_rate_bps: Optional[int] = None,
        antenna_rate_bps: Optional[int] = None,
        job_remaining_bytes: Optional[int] = None,
    ) -> tuple[int, bool]:
        """Calculate bytes transferred during [tick_start, tick_end).

        Returns:
            (new_transferred_bytes, is_final)
        """
        if self.is_final or self.cumulative_transferred_bytes >= self.allocated_bytes:
            self.is_final = True
            return 0, True

        # Validation checks
        if contact_status not in ("confirmed", "active"):
            return 0, False

        if not has_allowed_authorization:
            return 0, False

        if not station_is_operational or not satellite_is_operational:
            return 0, False

        # Transmission cannot occur before contact start (e.g. during antenna setup)
        eligible_start = max(tick_start, self.start_at)
        eligible_end = min(tick_end, self.end_at)

        if eligible_end <= eligible_start:
            # If past contact window, mark final
            if tick_end >= self.end_at:
                self.is_final = True
                return 0, True
            return 0, False

        # Calculate effective transmission rate
        effective_rate_bps = self.expected_rate_bps
        if satellite_rate_bps is not None:
            effective_rate_bps = min(effective_rate_bps, satellite_rate_bps)
        if antenna_rate_bps is not None:
            effective_rate_bps = min(effective_rate_bps, antenna_rate_bps)

        # Apply weather factor exactly once
        capacity_factor = max(0.0, min(1.0, weather_capacity_factor))
        effective_rate_bps = int(effective_rate_bps * capacity_factor)

        if effective_rate_bps <= 0:
            if tick_end >= self.end_at:
                self.is_final = True
                return 0, True
            return 0, False

        # Calculate elapsed microseconds in the eligible window
        elapsed_microseconds = int((eligible_end - eligible_start).total_seconds() * 1_000_000)

        # Microsecond fractional credit: rate_bps * microseconds
        # 1 byte = 8 bits -> 8,000,000 microbits
        self.credit_microbits += effective_rate_bps * elapsed_microseconds
        new_bytes = self.credit_microbits // 8_000_000
        self.credit_microbits = self.credit_microbits % 8_000_000

        # Bound by remaining allocation for this contact
        remaining_contact_bytes = self.allocated_bytes - self.cumulative_transferred_bytes
        new_bytes = min(new_bytes, remaining_contact_bytes)

        # Bound by remaining unserved job data if provided
        if job_remaining_bytes is not None:
            new_bytes = min(new_bytes, max(0, job_remaining_bytes))

        self.cumulative_transferred_bytes += new_bytes

        # Check for completion
        if self.cumulative_transferred_bytes >= self.allocated_bytes or tick_end >= self.end_at:
            self.is_final = True

        return new_bytes, self.is_final
