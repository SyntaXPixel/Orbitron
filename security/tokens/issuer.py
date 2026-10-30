"""
Orbitron Contact Token Issuance
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Union
import jwt

from security.contracts import (
    DEFAULT_PRE_START_INTERVAL_SECONDS,
    DEFAULT_TOKEN_LIFETIME_SECONDS,
    MAX_TOKEN_LIFETIME_SECONDS,
    TOKEN_ALGORITHM,
    TOKEN_HEADER_TYP,
    make_reason,
    parse_iso,
    to_iso_z,
    REASON_CONTACT_NOT_STARTED,
    REASON_CONTACT_ENDED,
    REASON_AUTHORIZATION_DENIED,
)
from security.exceptions import PolicyDeniedError, SecurityConfigurationError
from security.policy.contacts import evaluate_contact_policy
from security.tokens.claims import construct_claims
from security.tokens.keys import (
    derive_public_key_fingerprint,
    load_private_key_pem,
)


def issue_contact_token(
    context: Dict[str, Any],
    private_key: Union[bytes, str],
) -> Dict[str, Any]:
    """
    Issue a signed Ed25519 contact JWT.

    Args:
        context: Trusted policy context assembled by backend.
        private_key: Ed25519 PKCS#8 PEM bytes or string.

    Returns:
        dict: {
            "token": str,
            "expires_at": str,
            "scope": dict
        }

    Raises:
        PolicyDeniedError: If policy evaluation fails or contact is not in executable state.
        SecurityConfigurationError: If private key is invalid.
    """
    # 1. Evaluate policy
    policy_res = evaluate_contact_policy(context)
    if not policy_res.get("allowed"):
        reasons = policy_res.get("reasons", [])
        raise PolicyDeniedError("Contact policy denied authorization", reasons=reasons)

    scope = policy_res["scope"]
    contact = context.get("contact", {})

    # 2. Verify contact confirmation and status
    contact_status = contact.get("status", "confirmed").lower()
    if contact_status not in ["confirmed", "active"]:
        reason = make_reason(
            REASON_AUTHORIZATION_DENIED,
            f"Cannot issue authorization token for contact in '{contact_status}' status",
            resource_ids=[contact.get("id", "")]
        )
        raise PolicyDeniedError("Contact is not confirmed or active", reasons=[reason])

    # 3. Verify simulation issuance timing
    sim_time_str = context.get("simulation_time")
    if sim_time_str:
        sim_dt = parse_iso(sim_time_str)
        contact_start_dt = parse_iso(scope["contact_start_at"])
        contact_end_dt = parse_iso(scope["contact_end_at"])
        pre_start_window = timedelta(seconds=DEFAULT_PRE_START_INTERVAL_SECONDS)

        if sim_dt < (contact_start_dt - pre_start_window):
            reason = make_reason(
                REASON_CONTACT_NOT_STARTED,
                f"Issuance rejected: simulation time ({sim_time_str}) is earlier than pre-start interval ({DEFAULT_PRE_START_INTERVAL_SECONDS}s before start)",
                resource_ids=[contact.get("id", "")]
            )
            raise PolicyDeniedError("Simulation time is outside issuance window", reasons=[reason])

        if sim_dt >= contact_end_dt:
            reason = make_reason(
                REASON_CONTACT_ENDED,
                f"Issuance rejected: contact ended at {scope['contact_end_at']} (sim time {sim_time_str})",
                resource_ids=[contact.get("id", "")]
            )
            raise PolicyDeniedError("Contact has already ended in simulation", reasons=[reason])

    # 4. Resolve clock and compute wall-clock lifetime
    server_time_str = context.get("server_time")
    if server_time_str:
        srv_dt = parse_iso(server_time_str)
    else:
        srv_dt = datetime.now(timezone.utc)

    iat = int(srv_dt.timestamp())
    nbf = iat
    lifetime = min(DEFAULT_TOKEN_LIFETIME_SECONDS, MAX_TOKEN_LIFETIME_SECONDS)
    exp = iat + lifetime
    expires_at_iso = to_iso_z(datetime.fromtimestamp(exp, tz=timezone.utc))

    # 5. Load private key and derive kid
    priv_key_obj = load_private_key_pem(private_key)
    pub_key_obj = priv_key_obj.public_key()
    kid = derive_public_key_fingerprint(pub_key_obj)

    # 6. Construct claims
    claims = construct_claims(scope, iat=iat, nbf=nbf, exp=exp)

    # 7. Sign JWT using EdDSA
    headers = {
        "typ": TOKEN_HEADER_TYP,
        "alg": TOKEN_ALGORITHM,
        "kid": kid,
    }

    token = jwt.encode(
        claims,
        priv_key_obj,
        algorithm=TOKEN_ALGORITHM,
        headers=headers,
    )

    return {
        "token": token,
        "expires_at": expires_at_iso,
        "scope": scope,
    }
