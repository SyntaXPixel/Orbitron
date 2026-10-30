"""
Orbitron Contact Token Verification
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Union
import jwt

from security.contracts import (
    CONTRACT_VERSION,
    MAX_CONTEXT_AGE_SECONDS,
    MAX_TOKEN_LIFETIME_SECONDS,
    TOKEN_ALGORITHM,
    TOKEN_AUDIENCE,
    TOKEN_HEADER_TYP,
    TOKEN_ISSUER,
    make_reason,
    parse_iso,
    REASON_AUTHORIZATION_DENIED,
    REASON_AUTHORIZATION_REVOKED,
    REASON_CONTACT_ENDED,
    REASON_CONTACT_NOT_STARTED,
    REASON_CONTEXT_STALE,
    REASON_INVALID_ALGORITHM,
    REASON_INVALID_SIGNATURE,
    REASON_INVALID_TOKEN,
    REASON_SCOPE_MISMATCH,
    REASON_TOKEN_EXPIRED,
    REASON_WRONG_SCENARIO,
    REASON_WRONG_STATION,
)
from security.tokens.claims import validate_claim_types
from security.tokens.keys import (
    derive_public_key_fingerprint,
    load_public_key_pem,
)


def verify_contact_token(
    token: str,
    public_key: Union[bytes, str],
    expected_scope: Dict[str, Any],
    server_time: str,
    simulation_time: str,
) -> Dict[str, Any]:
    """
    Verify a contact authorization JWT against trusted public key and expected scope.

    Returns:
        dict: {
            "allowed": bool,
            "reasons": list,
            "claims": dict or None
        }
    """
    reasons: List[Dict[str, Any]] = []

    # 1. Structural check and size bounds
    if not isinstance(token, str) or len(token) > 8192 or token.count('.') != 2:
        return {
            "allowed": False,
            "reasons": [make_reason(REASON_INVALID_TOKEN, "Token is malformed or exceeds size limits")],
            "claims": None,
        }

    # 2. Header check
    try:
        header = jwt.get_unverified_header(token)
    except Exception as e:
        return {
            "allowed": False,
            "reasons": [make_reason(REASON_INVALID_TOKEN, f"Failed to parse token header: {e}")],
            "claims": None,
        }

    if header.get("typ") != TOKEN_HEADER_TYP:
        return {
            "allowed": False,
            "reasons": [make_reason(REASON_INVALID_TOKEN, f"Unsupported token header typ: '{header.get('typ')}' (expected '{TOKEN_HEADER_TYP}')")],
            "claims": None,
        }

    # 3. Explicit algorithm check (prevent algorithm confusion attacks)
    alg = header.get("alg")
    if alg != TOKEN_ALGORITHM:
        return {
            "allowed": False,
            "reasons": [make_reason(REASON_INVALID_ALGORITHM, f"Unsupported algorithm '{alg}', only '{TOKEN_ALGORITHM}' is permitted")],
            "claims": None,
        }

    # 4. Key ID verification
    try:
        pub_key_obj = load_public_key_pem(public_key)
    except Exception as e:
        return {
            "allowed": False,
            "reasons": [make_reason(REASON_INVALID_SIGNATURE, f"Trusted public key could not be loaded: {e}")],
            "claims": None,
        }

    expected_kid = derive_public_key_fingerprint(pub_key_obj)
    token_kid = header.get("kid")
    if token_kid and token_kid != expected_kid:
        return {
            "allowed": False,
            "reasons": [make_reason(REASON_INVALID_TOKEN, f"Key ID mismatch: token kid '{token_kid}' != trusted kid '{expected_kid}'")],
            "claims": None,
        }

    # 5, 6, 7. Cryptographic signature, Issuer, Audience verification
    try:
        claims = jwt.decode(
            token,
            pub_key_obj,
            algorithms=[TOKEN_ALGORITHM],
            issuer=TOKEN_ISSUER,
            audience=TOKEN_AUDIENCE,
            options={
                "verify_signature": True,
                "verify_iss": True,
                "verify_aud": True,
                "verify_exp": False,  # Time checks handled explicitly below using server_time
                "verify_nbf": False,
                "verify_iat": False,
                "require": ["iss", "aud", "sub", "jti", "iat", "nbf", "exp", "contract_version", "scope"],
            },
        )
    except jwt.InvalidSignatureError:
        return {
            "allowed": False,
            "reasons": [make_reason(REASON_INVALID_SIGNATURE, "Ed25519 signature verification failed")],
            "claims": None,
        }
    except jwt.InvalidIssuerError:
        return {
            "allowed": False,
            "reasons": [make_reason(REASON_INVALID_TOKEN, f"Issuer mismatch (expected '{TOKEN_ISSUER}')")],
            "claims": None,
        }
    except jwt.InvalidAudienceError:
        return {
            "allowed": False,
            "reasons": [make_reason(REASON_INVALID_TOKEN, f"Audience mismatch (expected '{TOKEN_AUDIENCE}')")],
            "claims": None,
        }
    except Exception as e:
        return {
            "allowed": False,
            "reasons": [make_reason(REASON_INVALID_TOKEN, f"Token decoding failed: {e}")],
            "claims": None,
        }

    # 8. Numeric types and claim structures
    valid_claims, err_msg = validate_claim_types(claims)
    if not valid_claims:
        return {
            "allowed": False,
            "reasons": [make_reason(REASON_INVALID_TOKEN, err_msg)],
            "claims": None,
        }

    # 9. Explicit Real-Time Verification using supplied server_time
    try:
        srv_dt = parse_iso(server_time)
    except Exception as e:
        return {
            "allowed": False,
            "reasons": [make_reason(REASON_INVALID_TOKEN, f"Invalid server_time provided: {e}")],
            "claims": None,
        }

    t_server = srv_dt.timestamp()
    iat = claims["iat"]
    nbf = claims["nbf"]
    exp = claims["exp"]

    if t_server < nbf:
        reasons.append(make_reason(
            REASON_INVALID_TOKEN,
            f"Token is not yet valid: nbf ({nbf}) is in future relative to server time ({t_server})"
        ))

    if t_server >= exp:
        reasons.append(make_reason(
            REASON_TOKEN_EXPIRED,
            f"Token expired at {exp} (server time {t_server})"
        ))

    if iat > t_server:
        reasons.append(make_reason(
            REASON_INVALID_TOKEN,
            f"Token iat ({iat}) is in future relative to server time ({t_server})"
        ))

    if exp <= iat:
        reasons.append(make_reason(
            REASON_INVALID_TOKEN,
            f"Invalid token lifetime: exp ({exp}) <= iat ({iat})"
        ))

    if exp - iat > MAX_TOKEN_LIFETIME_SECONDS:
        reasons.append(make_reason(
            REASON_INVALID_TOKEN,
            f"Token lifetime ({exp - iat}s) exceeds maximum allowed ({MAX_TOKEN_LIFETIME_SECONDS}s)"
        ))

    # 10. Scope matching against trusted expected_scope
    token_scope = claims.get("scope", {})
    expected_station = expected_scope.get("station_id")

    # Subject claim must match station
    if expected_station and claims.get("sub") != f"station:{expected_station}":
        reasons.append(make_reason(
            REASON_WRONG_STATION,
            f"Token subject '{claims.get('sub')}' does not match expected station 'station:{expected_station}'",
            resource_ids=[expected_station]
        ))

    if expected_station and token_scope.get("station_id") != expected_station:
        reasons.append(make_reason(
            REASON_WRONG_STATION,
            f"Token station_id '{token_scope.get('station_id')}' does not match expected station '{expected_station}'",
            resource_ids=[expected_station]
        ))

    expected_scenario = expected_scope.get("scenario_id")
    if expected_scenario and token_scope.get("scenario_id") != expected_scenario:
        reasons.append(make_reason(
            REASON_WRONG_SCENARIO,
            f"Scenario mismatch: token has '{token_scope.get('scenario_id')}', expected '{expected_scenario}'",
            resource_ids=[expected_scenario]
        ))

    for field in ["authorization_id", "satellite_id", "antenna_id", "contact_id", "owner_org_id", "allowed_action"]:
        expected_val = expected_scope.get(field)
        if expected_val is not None and token_scope.get(field) != expected_val:
            reasons.append(make_reason(
                REASON_SCOPE_MISMATCH,
                f"Scope mismatch for '{field}': token has '{token_scope.get(field)}', expected '{expected_val}'",
                resource_ids=[str(expected_val)]
            ))

    # Contact bounds and booking schedule version
    if expected_scope.get("contact_start_at") and token_scope.get("contact_start_at") != expected_scope.get("contact_start_at"):
        reasons.append(make_reason(REASON_SCOPE_MISMATCH, "contact_start_at changed"))
    if expected_scope.get("contact_end_at") and token_scope.get("contact_end_at") != expected_scope.get("contact_end_at"):
        reasons.append(make_reason(REASON_SCOPE_MISMATCH, "contact_end_at changed"))
    if expected_scope.get("schedule_version") is not None and token_scope.get("schedule_version") != expected_scope.get("schedule_version"):
        reasons.append(make_reason(REASON_SCOPE_MISMATCH, "schedule_version changed"))

    # 11. Authorization status check
    auth_status = expected_scope.get("authorization_status")
    if auth_status:
        if auth_status == "revoked":
            reasons.append(make_reason(REASON_AUTHORIZATION_REVOKED, "Authorization grant has been revoked"))
        elif auth_status != "allowed":
            reasons.append(make_reason(REASON_AUTHORIZATION_DENIED, f"Authorization status is '{auth_status}'"))

    # 12. Contact execution state
    contact_status = expected_scope.get("contact_status")
    if contact_status in ["cancelled", "failed"]:
        reasons.append(make_reason(REASON_AUTHORIZATION_DENIED, f"Contact status is terminal: '{contact_status}'"))

    # 13. Simulation-Time Verification
    try:
        sim_dt = parse_iso(simulation_time)
        c_start_dt = parse_iso(token_scope.get("contact_start_at"))
        c_end_dt = parse_iso(token_scope.get("contact_end_at"))

        if sim_dt < c_start_dt:
            reasons.append(make_reason(
                REASON_CONTACT_NOT_STARTED,
                f"Simulation time ({simulation_time}) is before contact start ({token_scope.get('contact_start_at')})"
            ))
        if sim_dt >= c_end_dt:
            reasons.append(make_reason(
                REASON_CONTACT_ENDED,
                f"Simulation time ({simulation_time}) is at or after contact end ({token_scope.get('contact_end_at')})"
            ))
    except Exception as e:
        reasons.append(make_reason(REASON_INVALID_TOKEN, f"Error validating simulation time: {e}"))

    # 14. Context Freshness Check
    observed_at_str = expected_scope.get("context_observed_at")
    if observed_at_str:
        try:
            obs_dt = parse_iso(observed_at_str)
            age = abs(t_server - obs_dt.timestamp())
            if age > MAX_CONTEXT_AGE_SECONDS:
                reasons.append(make_reason(
                    REASON_CONTEXT_STALE,
                    f"Trusted context observed_at age ({age:.2f}s) exceeds freshness limit ({MAX_CONTEXT_AGE_SECONDS}s)"
                ))
        except Exception as e:
            reasons.append(make_reason(REASON_CONTEXT_STALE, f"Invalid context_observed_at: {e}"))

    if reasons:
        return {
            "allowed": False,
            "reasons": reasons,
            "claims": None,
        }

    return {
        "allowed": True,
        "reasons": [],
        "claims": claims,
    }
