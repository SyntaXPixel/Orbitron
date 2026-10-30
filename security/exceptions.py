"""
Orbitron Security Module Exceptions
"""

class SecurityError(Exception):
    """Base exception for all security module errors."""
    pass


class SecurityConfigurationError(SecurityError):
    """Raised when cryptographic or environment configuration is invalid."""
    pass


class PolicyDeniedError(SecurityError):
    """Raised when contact policy evaluation denies authorization."""
    def __init__(self, message: str, reasons: list = None):
        super().__init__(message)
        self.reasons = reasons or []


class TokenValidationError(SecurityError):
    """Raised when token validation or verification fails."""
    def __init__(self, message: str, reasons: list = None):
        super().__init__(message)
        self.reasons = reasons or []


class TokenExpiredError(TokenValidationError):
    """Raised when a token has expired."""
    pass


class InvalidSignatureError(TokenValidationError):
    """Raised when a cryptographic signature fails verification."""
    pass


class EnvelopeValidationError(SecurityError):
    """Raised when an encrypted payload envelope is malformed or invalid."""
    pass


class PayloadIntegrityError(SecurityError):
    """Raised when authenticated payload decryption fails verification."""
    pass
