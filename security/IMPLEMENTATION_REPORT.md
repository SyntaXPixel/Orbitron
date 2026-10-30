# Orbitron — Security Module Implementation Report

**Module:** `security`  
**Plan Reference:** `security/plan.md` (Version 1.0)  
**Contract Version:** `orbitron.v1`  
**Branch:** `agent/SECURITY`  
**Date:** 2026-10-31  

---

## 1. Implemented Python Interfaces

All eight shared interfaces required by Section 6 of `security/plan.md` have been fully implemented in `security/api.py`:

1. `capabilities() -> dict`:
   - Returns full availability for `contact_authorization`, `token_verification`, `payload_encryption`, and `security_checks` under `contract_version: orbitron.v1`.
2. `evaluate_contact(context: dict) -> dict`:
   - Validates backend-constructed trusted records (job, satellite, station, antenna, contact, sharing relationship, action) and returns policy decisions with detailed reasons and scope.
3. `issue_contact_token(context: dict, private_key: bytes) -> dict`:
   - Evaluates policy, verifies confirmed contact state and simulation issuance timing, and signs an Ed25519 JWT grant.
4. `verify_contact_token(token: str, public_key: bytes, expected_scope: dict, server_time: str, simulation_time: str) -> dict`:
   - Strictly enforces the 15-step token verification specification without relying on untrusted header claims or clock leeway.
5. `encrypt_payload(plaintext: bytes, key: bytes, associated_data: bytes) -> dict`:
   - Performs AES-256-GCM encryption with cryptographically secure random nonces and returns an `orbitron.payload.v1` envelope.
6. `decrypt_payload(envelope: dict, key: bytes, associated_data: bytes) -> bytes`:
   - Strictly validates envelope structure and base64 encodings, executing authenticated decryption and raising `PayloadIntegrityError` on tag mismatch.
7. `canonical_payload_aad(fields: dict) -> bytes`:
   - Produces canonical UTF-8 JSON bytes with sorted keys for the required 7 transfer metadata fields.
8. `build_security_challenge(test_case: str, context: dict, private_key: bytes) -> dict`:
   - Prepares isolated test challenges for `expired_authorization`, `wrong_station`, and `tampered_payload`.

Additional identity support:
- `hash_password`, `verify_password`, `needs_rehash`: Argon2id helpers matching backend authentication requirements.

---

## 2. Authentication Compatibility

- **Browser Sessions:** Security module preserves existing backend session contracts (`orbitron_session`, HttpOnly, SameSite=Lax, CSRF token). The security module does not replace browser sessions with frontend-stored JWTs.
- **Service Principals:** Service bearer credentials (`simulator_controller`, `satellite`, `station_gateway`, `owner_receiver`) remain separate from contact authorization tokens.
- **Password Hashing:** Integrated Argon2id with standard parameters (time cost: 2 iterations, memory cost: 19 MiB, parallelism: 1), completely compatible with `backend/app/services/auth_service.py`.

---

## 3. Policy Rules

Contact policy enforcement (`security/policy/contacts.py`):
1. **Trusted Records Required:** Rejects arbitrary client assertions (e.g. `authenticated: true`, `role: network_admin`) without genuine backing records for job, satellite, station, antenna, and contact.
2. **Structural Consistency:** Enforces that contact belongs to job, job belongs to satellite, job owner matches satellite owner, antenna belongs to station, and contact station/antenna match.
3. **Band Compatibility:** Validates that the contact frequency band is supported by the selected antenna.
4. **Time Bounds:** Ensures `contact_start_at < contact_end_at`.
5. **Permitted Action:** Restricts permitted operations strictly to `receive_and_forward`.
6. **Usability Checks:** Requires satellite, station, and antenna operational status to be non-failed, non-offline, and usable. Contacts in `cancelled` or `failed` status are denied.
7. **Station Sharing Rules:**
   - Own-station requests (`job_owner == station_owner`) are permitted under normal operational rules.
   - Partner stations (`job_owner != station_owner`) strictly require `station.sharing_enabled == True` and an approved sharing relationship or partner permission for the job owner org.
   - Privileged roles (such as `network_admin`) do **not** bypass partner sharing policies.

---

## 4. Token Format and Algorithms

- **JWT Type Header:** `orbitron-contact+jwt`
- **Algorithm:** `EdDSA` using Ed25519 asymmetric cryptography. Token verifier strictly allowlists `EdDSA` and rejects all other algorithms (including symmetric `none` or `HS256`).
- **Key Identifier:** Deterministic 16-character hex fingerprint derived from SHA-256 of the canonical public key SubjectPublicKeyInfo PEM encoding.
- **Claims Schema:**
  - `iss`: `orbitron-local`
  - `aud`: `orbitron-payload-relay`
  - `sub`: `station:<station_id>`
  - `jti`: `authorization_id`
  - `iat`, `nbf`, `exp`: Integer UTC unix timestamps (booleans strictly rejected)
  - `contract_version`: `orbitron.v1`
  - `scope`: Complete resource scope dictionary

---

## 5. Clock and Expiry Rules

- **Dual-Clock Separation:**
  - **Wall-Clock Expiry:** Computed using real server time (`server_time`). Real-time token lifetime defaults to 300 seconds, with an enforced maximum of 600 seconds. Zero leeway is configured.
  - **Simulation Contact Window:** Evaluated against `simulation_time`. A token is only executable when `contact_start_at <= simulation_time < contact_end_at`.
- **Pre-Start Issuance Interval:** Tokens can only be issued within 60 simulation seconds before contact start or while the contact is active. Issuance before this pre-start window is rejected (`CONTACT_NOT_STARTED`).
- **Context Freshness:** The verifier checks that `abs(server_time - context_observed_at) <= 5.0 seconds`. Older contexts fail with `CONTEXT_STALE`.

---

## 6. Revocation Behaviour

- **State Re-validation:** Contact authorizations carry backend lifecycle state (`allowed`, `revoked`, `denied`, `expired`).
- If `expected_scope["authorization_status"] == "revoked"`, verification immediately fails with `AUTHORIZATION_REVOKED`.
- Scenario changes invalidate grants from earlier scenarios (`WRONG_SCENARIO`).
- Schedule changes to unrelated bookings do not invalidate unchanged contact authorizations, as checks bind to the contact's own `schedule_version`.

---

## 7. Payload Envelope

- **Envelope Schema (`orbitron.payload.v1`):**
  ```json
  {
    "version": "orbitron.payload.v1",
    "algorithm": "AES-256-GCM",
    "nonce_b64": "<12-byte nonce base64>",
    "ciphertext_b64": "<ciphertext + 16-byte tag base64>"
  }
  ```
- **Size Limits:** Maximum plaintext: 1,048,576 bytes (1 MiB); maximum associated data: 4,096 bytes.
- **Nonces:** Generated using cryptographically secure random bytes (`os.urandom(12)`). Predictable scenario seeds are never used.
- **Authentication Failure:** Modifying ciphertext, nonce, or canonical AAD triggers `PayloadIntegrityError`. Decryption returns no plaintext and does not write corrupted files.

---

## 8. Key Provisioning

- **Key Custody Separation:**
  - Issuer Ed25519 private key is held exclusively by the backend issuer.
  - Gateways and receivers receive only the trusted public key.
  - Partner gateways never receive owner AES payload keys.
- **CLI Initialization:** `python -m security.cli.init_keys --output-dir security/.runtime/issuer` generates `private.pem` (PKCS#8) and `public.pem` (SubjectPublicKeyInfo). Existing keys are preserved unless `--force` is specified.
- Keys are written to `security/.runtime/issuer/`, which is ignored by `.gitignore` to prevent secret commits.

---

## 9. Checks Run and Actual Results

### Automated Module Tests (`pytest security/tests -v`):
**45 of 45 tests passed (100%) in 0.77s**:
- `test_capabilities_contract`: Verified `orbitron.v1` capability declaration.
- `test_api_full_contact_and_payload_flow`: Verified end-to-end policy, token issuance, verification, AAD encoding, and encryption/decryption.
- `test_own_station_request_permitted`, `test_approved_partner_permitted`: Verified successful sharing policies.
- `test_unapproved_partner_denied`, `test_sharing_disabled_station_denied`, `test_privileged_role_does_not_bypass_sharing_policy`: Verified negative policy controls.
- `test_wrong_satellite_job_relationship_denied`, `test_job_owner_mismatch_denied`, `test_wrong_antenna_station_relationship_denied`: Verified structural consistency checks.
- `test_unsupported_action_denied`, `test_cancelled_contact_denied`, `test_unusable_resource_denied`, `test_untrusted_client_assertion_rejected`, `test_unsupported_band_denied`, `test_invalid_bounds_denied`: Verified boundary and integrity denials.
- `test_tampered_signature_rejected`, `test_wrong_algorithm_rejected`, `test_wrong_issuer_and_audience_rejected`: Verified token signature and header defense.
- `test_real_time_expiry_enforced`, `test_simulation_time_bounds_enforced`, `test_pre_start_issuance_timing_enforced`: Verified dual-clock temporal rules.
- `test_wrong_station_rejected`, `test_revoked_grant_rejected`, `test_stale_context_rejected`: Verified scope and context freshness.
- `test_encryption_decryption_roundtrip`, `test_invalid_key_length_rejected`, `test_tampered_ciphertext_fails_integrity`, `test_tampered_aad_fails_integrity`, `test_wrong_key_fails_integrity`, `test_malformed_envelope_rejected`: Verified AES-256-GCM tamper resistance.
- `test_plaintext_size_limit_enforced`, `test_canonical_aad_field_validation`, `test_unique_nonces_generated`: Verified cryptographic bounds and nonce freshness.
- `test_password_hash_and_verify`, `test_needs_rehash`, `test_empty_password_rejected`, `test_benchmark_argon2id`: Verified Argon2id password hashing.
- `test_expired_authorization_challenge`, `test_wrong_station_challenge`, `test_tampered_payload_challenge`, `test_unsupported_challenge_raises`, `test_sanitize_audit_context`, `test_build_evidence_record`: Verified controlled security challenges and evidence sanitization.

### CLI Self-Check (`python -m security.cli.self_check`):
- All 5 stages passed: capabilities, ephemeral key generation, policy/token lifecycle, payload encryption/decryption round-trip, and negative security checks.

---

## 10. Backend Integration Verified

- Tested direct adapter interaction:
  `from app.adapters.security import SecurityAdapter`
  `SecurityAdapter.is_available()` returns `True`.
  `SecurityAdapter.capabilities()` reports valid capability schema.
- Backend contract checks (`backend/tests/test_contracts.py`) confirm snapshot readiness reports `services.security = "ready"`.

---

## 11. Gateway / Receiver Integration Verified

- Gateway interface checks token verification using `verify_contact_token()` with configured station ID and verification public key.
- Receiver verifies owner payload decryption using `decrypt_payload()` with the canonical AAD generated via `canonical_payload_aad()`.
- Simulation test cases receive structured reasons on failure (`TOKEN_EXPIRED`, `WRONG_STATION`, `PAYLOAD_INTEGRITY_FAILED`).

---

## 12. Negative Scenarios Verified

- **Expired Authorization:** Correctly fails with `TOKEN_EXPIRED` when `server_time >= exp`.
- **Wrong Station:** Correctly fails with `WRONG_STATION` when token station does not match expected station scope.
- **Tampered Payload:** Authenticated AES-GCM decryption raises `PayloadIntegrityError` when any ciphertext byte is altered.
- **Corrupted AAD:** Any discrepancy between sender and receiver metadata causes decryption failure.
- **Stale Context:** Reject execution if context observation timestamp exceeds 5 seconds from current server time.

---

## 13. Known Limitations

- **Software Prototype:** Local process execution without hardware security modules (HSM) or secure enclaves.
- **Same-Host Simulation:** Clock synchronization relies on the local system clock for server time and coordinate time for simulation.

---

## 14. Exact Local Commands

```bash
# 1. Install pinned requirements
python -m pip install -r security/requirements.lock

# 2. Run unit and integration tests
python -m pytest security/tests -v

# 3. Initialize issuer keypair (writes to security/.runtime/issuer/)
python -m security.cli.init_keys --output-dir security/.runtime/issuer

# 4. Run standalone cryptographic self-check
python -m security.cli.self_check
```
