"""
JWT Claims Definition and Validation for Orbitron Contact Tokens
"""

from typing import Dict, Any, Tuple
from security.contracts import (
    CONTRACT_VERSION,
    TOKEN_AUDIENCE,
    TOKEN_ISSUER,
)
from security.policy.scopes import validate_scope

REQUIRED_CLAIMS = ("iss", "aud", "sub", "jti", "iat", "nbf", "exp", "contract_version", "scope")


def construct_claims(
    scope: Dict[str, Any],
    iat: int,
    nbf: int,
    exp: int,
) -> Dict[str, Any]:
    """Build the required JWT claims payload."""
    station_id = scope.get("station_id", "")
    authorization_id = scope.get("authorization_id", "")

    return {
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "sub": f"station:{station_id}",
        "jti": authorization_id,
        "iat": int(iat),
        "nbf": int(nbf),
        "exp": int(exp),
        "contract_version": CONTRACT_VERSION,
        "scope": dict(scope),
    }


def validate_claim_types(claims: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate that required claims are present and have expected types."""
    if not isinstance(claims, dict):
        return False, "Claims must be a dictionary"

    for claim in REQUIRED_CLAIMS:
        if claim not in claims:
            return False, f"Missing required claim: {claim}"

    # Strict numeric validation: reject booleans masquerading as integers
    for num_claim in ["iat", "nbf", "exp"]:
        val = claims[num_claim]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return False, f"Claim '{num_claim}' must be an integer, not {type(val).__name__}"

    if claims["iss"] != TOKEN_ISSUER:
        return False, f"Issuer mismatch: expected {TOKEN_ISSUER}, got {claims['iss']}"

    if claims["aud"] != TOKEN_AUDIENCE:
        return False, f"Audience mismatch: expected {TOKEN_AUDIENCE}, got {claims['aud']}"

    if claims["contract_version"] != CONTRACT_VERSION:
        return False, f"Contract version mismatch: expected {CONTRACT_VERSION}, got {claims['contract_version']}"

    if not validate_scope(claims.get("scope", {})):
        return False, "Scope claim is missing or invalid"

    return True, ""
