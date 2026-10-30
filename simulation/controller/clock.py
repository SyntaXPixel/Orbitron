"""Authoritative simulation clock and monotonic wall-clock pacing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time
from typing import Optional
from simulation.exceptions import SimulationClockError


def parse_utc(iso_str: str) -> datetime:
    clean = iso_str.replace("Z", "+00:00")
    return datetime.fromisoformat(clean).astimezone(timezone.utc)


def format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SimulationClock:
    """Manages simulation time progression, paced by monotonic wall clock."""

    def __init__(
        self,
        initial_simulation_time: str,
        speed_multiplier: float = 1.0,
        default_tick_seconds: float = 1.0,
        max_tick_seconds: float = 60.0,
    ):
        self.simulation_time: datetime = parse_utc(initial_simulation_time)
        self.speed_multiplier: float = max(0.1, speed_multiplier)
        self.default_tick_seconds: float = default_tick_seconds
        self.max_tick_seconds: float = max_tick_seconds

        self.is_paused: bool = True
        self.is_stepping: bool = False
        self.step_remaining_seconds: float = 0.0

        self._last_wall_time: Optional[float] = None
        self._lag_seconds: float = 0.0

    def sync_authoritative_time(self, authoritative_iso: str) -> None:
        """Update local simulation time from backend authoritative state."""
        auth_dt = parse_utc(authoritative_iso)
        self.simulation_time = auth_dt

    def pause(self) -> None:
        """Pause operational advancement. Wall clock continues."""
        self.is_paused = True
        self.is_stepping = False
        self.step_remaining_seconds = 0.0
        self._last_wall_time = None

    def resume(self) -> None:
        """Resume operational advancement from accepted backend time."""
        self.is_paused = False
        self.is_stepping = False
        self.step_remaining_seconds = 0.0
        self._last_wall_time = time.monotonic()

    def start_step(self, step_seconds: float = 60.0) -> None:
        """Begin manual step for bounded duration while remaining paused."""
        if step_seconds <= 0 or step_seconds > self.max_tick_seconds:
            raise SimulationClockError(
                f"Step size must be between 1 and {self.max_tick_seconds} seconds (requested {step_seconds}s)."
            )
        self.is_paused = False
        self.is_stepping = True
        self.step_remaining_seconds = step_seconds
        self._last_wall_time = time.monotonic()

    def calculate_next_tick(self) -> tuple[str, str, float]:
        """Determine (previous_simulation_time_iso, next_simulation_time_iso, elapsed_seconds).

        Returns:
            (prev_iso, next_iso, elapsed_seconds)
            If paused and not stepping, elapsed_seconds is 0.0 and prev_iso == next_iso.
        """
        prev_iso = format_utc(self.simulation_time)

        if self.is_paused and not self.is_stepping:
            return prev_iso, prev_iso, 0.0

        now_wall = time.monotonic()
        if self._last_wall_time is None:
            self._last_wall_time = now_wall

        wall_delta = now_wall - self._last_wall_time
        self._last_wall_time = now_wall

        if self.is_stepping:
            # Advance bounded step chunk (up to default_tick_seconds or remaining step)
            advance_sec = min(self.default_tick_seconds, self.step_remaining_seconds)
            self.step_remaining_seconds -= advance_sec
            if self.step_remaining_seconds <= 0:
                self.is_stepping = False
                self.is_paused = True
        else:
            # Discrete tick advancement paced by tick_seconds
            paced_delta = wall_delta * self.speed_multiplier
            advance_sec = max(self.default_tick_seconds, min(paced_delta, self.max_tick_seconds))

        next_dt = self.simulation_time + timedelta(seconds=advance_sec)
        next_iso = format_utc(next_dt)

        return prev_iso, next_iso, advance_sec

    def commit_advance(self, next_simulation_time_iso: str) -> None:
        """Commit time advancement after backend confirmation."""
        next_dt = parse_utc(next_simulation_time_iso)
        if next_dt < self.simulation_time:
            raise SimulationClockError("Cannot regress simulation clock.")
        self.simulation_time = next_dt
