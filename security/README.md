# Orbitron — Security Module

The **Security Module** provides cryptographic policy evaluation, short-lived scoped contact authorization tokens, and authenticated payload encryption/decryption for the Orbitron local ground-station sharing prototype.

---

## 1. Responsibilities and Architecture

Orbitron ground-station sharing requires strict separation of concerns across three security mechanisms:

| Mechanism | Purpose | Technology | Key Custody |
|---|---|---|---|
| **Browser / Service Identity** | Authenticate users and backend microservices | Session cookies / Bearer tokens / Argon2id | Backend Auth Service |
| **Contact Authorization** | Grant scoped partner receiving/forwarding permissions | Signed Ed25519 (EdDSA) JWTs (`orbitron-contact+jwt`) | Backend Issuer (private); Gateways/Receivers (public) |
| **Payload Protection** | Confidentiality and integrity of mission data through partner relays | Authenticated AES-256-GCM with canonical AAD | Satellite Owner only (never provisioned to partner gateway) |

### Key Principles
- **No Shared Secrets:** Partner gateways never receive the issuer signing private key, nor do they hold owner payload encryption/decryption keys.
- **Strict Scope Boundaries:** A contact token authorizes a single action (`receive_and_forward`) for a specific contact, satellite, station, antenna, scenario, and time interval.
- **Explicit Temporal Verification:** Token expiration is verified against explicit server time, while transmission execution is bound to simulation time within the contact window.
- **Tamper Evidence:** Modifying ciphertext or authenticated associated data (AAD) fails AES-GCM tag verification, returning zero plaintext.

---

## 2. Directory Structure

```text
security/
├── plan.md                     # Security implementation specification
├── README.md                   # Module documentation and integration guidance
├── IMPLEMENTATION_REPORT.md    # Detailed audit report and handover record
├── requirements.in             # Direct dependencies
├── requirements.lock           # Pinned dependencies
├── __init__.py                 # Package exports
├── api.py                      # Public API matching orbitron.v1 contract
├── contracts.py                # Shared constants, reason codes, and timestamp helpers
├── exceptions.py               # Exception hierarchy (PayloadIntegrityError, etc.)
├── policy/
│   ├── __init__.py
│   ├── contacts.py             # Contact sharing and consistency policy evaluation
│   └── scopes.py               # Scope structure and validation
├── tokens/
│   ├── __init__.py
│   ├── claims.py               # JWT claims schema and numeric validation
│   ├── issuer.py               # Just-in-time contact token issuance
│   ├── keys.py                 # Ed25519 key generation and PEM encoding
│   └── verifier.py             # Strict 15-step token verifier
├── payload/
│   ├── __init__.py
│   ├── associated_data.py      # Canonical AAD JSON encoder (sorted keys)
│   ├── encryption.py           # AES-256-GCM encrypt_payload and decrypt_payload
│   └── envelopes.py            # orbitron.payload.v1 envelope handling
├── identity/
│   ├── __init__.py
│   └── passwords.py            # Argon2id password hashing and verification
├── testing/
│   ├── __init__.py
│   ├── challenges.py           # Builders for expired_authorization, wrong_station, tampered_payload
│   └── evidence.py             # Audit-safe evidence record generators
├── cli/
│   ├── __init__.py
│   ├── init_keys.py            # Key generation CLI
│   └── self_check.py           # Local cryptographic self-check script
└── tests/
    ├── __init__.py
    ├── test_api.py
    ├── test_challenges.py
    ├── test_identity.py
    ├── test_payload.py
    ├── test_policy.py
    └── test_tokens.py
```

Generated local issuer keys are saved to `security/.runtime/issuer/` and ignored by Git.

---

## 3. Required Python API (`security.api`)

All functions conform to the Orbitron shared contract (`orbitron.v1`):

### 3.1 `capabilities() -> dict`
Reports module capability status:
```json
{
  "contract_version": "orbitron.v1",
  "contact_authorization": true,
  "token_verification": true,
  "payload_encryption": true,
  "security_checks": true
}
```

### 3.2 `evaluate_contact(context: dict) -> dict`
Evaluates trusted backend records for sharing policy compliance. Verifies ownership, station sharing flags, approved partner status, band compatibility, and resource usability.

### 3.3 `issue_contact_token(context: dict, private_key: bytes) -> dict`
Issues an Ed25519-signed JWT token near scheduled execution. Enforces the pre-start simulation issuance window (default 60 seconds). Returns `token`, `expires_at`, and `scope`.

### 3.4 `verify_contact_token(token: str, public_key: bytes, expected_scope: dict, server_time: str, simulation_time: str) -> dict`
Enforces strict 15-step verification:
1. Structural formatting and size limits.
2. Header type (`typ == "orbitron-contact+jwt"`).
3. Explicit algorithm check (`alg == "EdDSA"`).
4. Public key fingerprint (`kid`) match.
5. Ed25519 signature validity.
6. Issuer (`iss == "orbitron-local"`).
7. Audience (`aud == "orbitron-payload-relay"`).
8. Claims schema and numeric types (rejecting booleans).
9. Real-time validity using `server_time` (`nbf <= server_time < exp`, duration <= 600s).
10. Scope matching against trusted ground truth.
11. Authorization lifecycle status (`allowed` vs `revoked`).
12. Contact execution status (not cancelled or failed).
13. Simulation-time validity (`contact_start_at <= simulation_time < contact_end_at`).
14. Trusted context freshness (`abs(server_time - context_observed_at) <= 5.0s`).

### 3.5 `encrypt_payload(plaintext: bytes, key: bytes, associated_data: bytes) -> dict`
Encrypts plaintext using AES-256-GCM with a fresh 12-byte secure nonce. Returns an `orbitron.payload.v1` envelope containing `nonce_b64` and `ciphertext_b64`.

### 3.6 `decrypt_payload(envelope: dict, key: bytes, associated_data: bytes) -> bytes`
Verifies envelope format and performs authenticated decryption. Raises `PayloadIntegrityError` if ciphertext, nonce, tag, or associated data have been altered.

### 3.7 `canonical_payload_aad(fields: dict) -> bytes`
Constructs canonical UTF-8 JSON bytes with sorted keys for the 7 required fields:
`scenario_id`, `transfer_id`, `contact_id`, `satellite_id`, `station_id`, `owner_org_id`, and `expected_plaintext_sha256`.

### 3.8 `build_security_challenge(test_case: str, context: dict, private_key: bytes) -> dict`
Prepares negative test challenges (`expired_authorization`, `wrong_station`, `tampered_payload`) for controlled verification.

---

## 4. Local Commands

Run all commands from the repository root:

### Install Dependencies
```bash
python -m pip install -r security/requirements.lock
```

### Run Module Tests
```bash
python -m pytest security/tests -q
```

### Initialize Issuer Ed25519 Keys
```bash
python -m security.cli.init_keys --output-dir security/.runtime/issuer
```
To overwrite existing keys, add `--force`.

### Run Cryptographic Self-Check
```bash
python -m security.cli.self_check
```

---

## 5. Configuration Handover for Other Modules

The backend and simulation modules integrate with the security module using the following settings:

| Configuration Setting | Recommended Value | Notes |
|---|---|---|
| `AUTHORIZATION_PRIVATE_KEY_PATH` | `security/.runtime/issuer/private.pem` | Used by Backend to sign contact tokens |
| `AUTHORIZATION_PUBLIC_KEY_PATH` | `security/.runtime/issuer/public.pem` | Provisioned to Gateways and Receivers for verification |
| `TOKEN_ISSUER` | `orbitron-local` | Fixed issuer claim |
| `TOKEN_AUDIENCE` | `orbitron-payload-relay` | Fixed audience claim |
| `DEFAULT_TOKEN_LIFETIME` | `300` | Real-time seconds (5 minutes) |
| `MAX_TOKEN_LIFETIME` | `600` | Real-time seconds (10 minutes) |
| `PRE_START_ISSUANCE_INTERVAL` | `60` | Simulation seconds before contact start |
| `MAX_CONTEXT_AGE` | `5.0` | Real-time seconds freshness limit |
| `MAX_PLAINTEXT_BYTES` | `1048576` | 1 MiB per sample transfer |
| `MAX_AAD_BYTES` | `4096` | 4 KiB maximum associated data |

### Path Resolution
Relative paths are resolved relative to the repository root directory (`Path(__file__).resolve().parent.parent...`). Absolute paths are never hardcoded.
