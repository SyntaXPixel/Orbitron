"""Custom exceptions for the Orbitron scheduler and orbital prediction module."""

from __future__ import annotations


class SchedulerError(Exception):
    """Base exception for all scheduler and orbital prediction errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SchedulerInputError(SchedulerError):
    """Raised when problem inputs, horizon, or parameters are invalid or contradictory."""
    pass


class OrbitalDataError(SchedulerError):
    """Raised when orbital definitions, TLE data, epochs, or coordinates are invalid."""
    pass


class ValidationError(SchedulerError):
    """Raised when independent validation finds constraint violations in a proposed schedule."""
    pass


class SchedulerUnavailableError(SchedulerError):
    """Raised when required scheduling capabilities or solvers cannot run."""
    pass
