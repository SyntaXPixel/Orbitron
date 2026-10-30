"""Event representation and queue for offline evaluation replay."""

from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field

from simulation.model.progress import parse_utc


class ReplayEvent(BaseModel):
    """Event in a frozen evaluation scenario."""
    at: str
    type: str  # job_arrival, rain, station_outage, station_recovery
    payload: Dict[str, Any] = Field(default_factory=dict)

    @property
    def timestamp(self):
        return parse_utc(self.at)


class ReplayEventQueue:
    """Chronologically ordered queue of scenario events."""

    def __init__(self, events_data: List[Dict[str, Any]]):
        self.events: List[ReplayEvent] = [ReplayEvent(**e) for e in events_data]
        self.events.sort(key=lambda e: e.timestamp)

    def pop_until(self, horizon_dt) -> List[ReplayEvent]:
        """Pop all events up to horizon_dt."""
        due = []
        while self.events and self.events[0].timestamp <= horizon_dt:
            due.append(self.events.pop(0))
        return due

    def peek_next_time(self):
        return self.events[0].timestamp if self.events else None

