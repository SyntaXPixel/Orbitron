"""Exception hierarchy for the Orbitron simulation module."""

class SimulationError(Exception):
    """Base exception for all simulation module errors."""
    pass


class IntegrationDependencyError(SimulationError):
    """Raised when an external module interface (backend, scheduler, security) is missing or unavailable."""
    pass


class ContractValidationError(SimulationError):
    """Raised when data contracts or payload formats fail validation."""
    pass


class SimulationClockError(SimulationError):
    """Raised when clock operations are invalid (e.g., negative delta, step > 60s, catch-up runaway)."""
    pass


class ScenarioMismatchError(SimulationError):
    """Raised when local state does not match authoritative backend scenario generation."""
    pass


class SecurityVerificationError(SimulationError):
    """Raised when security authorization or cryptographic verification fails."""
    pass


class ConfigurationError(SimulationError):
    """Raised when required configuration or credentials are missing or invalid."""
    pass
