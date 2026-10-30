# Orbitron Frontend — Implementation Report

**Plan version:** 1.0  
**Contract version:** `orbitron.v1`  
**Working branch:** `agent/frontend`  
**Scope directory:** `frontend/`  

---

### Implemented screens:
1. **Login (`/login`)**: Secure session authentication, email/password form, live backend API status check, CSRF token handling, inline error feedback, and session expiration handling.
2. **Overview (`/`)**: Fleet & Ground Network Console displaying KPI cards (registered fleet, active contacts, pending jobs, approaching deadlines, blocked jobs, delivered data), simulated satellite fleet catalogue with position telemetry, ground-station catalogue, and expandable detail drawer.
3. **Schedule (`/schedule`)**: Multi-station antenna booking timeline grouped by ground station, setup intervals vs communication windows, simulation-time vertical marker, pass opportunity visualization, overlap conflict detection, filtering by satellite/station/status, and "Run Scheduler" mutation trigger.
4. **Requests (`/requests`)**: Job submission form with satellite selector (scoped to user organization permissions), canonical byte conversion (MB/GB with 1 MB = 1,000,000 bytes and 1 GB = 1,000,000,000 bytes), operational deadline validation against simulation time, priority classes (routine, high, emergency), and requests table with filtering and reason code explanations.
5. **Recovery (`/recovery`)**: Operational disruption controls (rain attenuation slider with capacity factor, station outage trigger, station recovery trigger), link to emergency requests, and before/after schedule change views (`New Assignment` vs `Unassigned` with decision reason codes).
6. **Security (`/security`)**: Zero-trust ground-station sharing dashboard, end-to-end encrypted payload transfer initiation, hash verification (SHA-256 ciphertext and plaintext checks), and demonstration security checks (`tampered_payload`, `expired_authorization`, `wrong_station`) with expected rejection verification.
7. **Evaluation (`/evaluation`)**: Head-to-head empirical comparison table between the proposed constraint scheduler and FIFO baseline across identical scenario workloads and disruption traces, with robust zero-baseline handling.
8. **Audit (`/audit`)**: Immutable operational audit ledger displaying actor names, actions, outcome badges, resource IDs, server/simulation clock basis, and text-safe message rendering with search and filtering.
9. **Not Found (`*`)**: Dedicated, application-styled 404 page with return-to-overview action.

---

### API endpoints integrated:
- `GET /health` — Service readiness and `orbitron.v1` contract version verification.
- `POST /auth/login` — Session creation with HttpOnly cookie and in-memory CSRF token capture.
- `GET /auth/session` — Session recovery and permission validation.
- `POST /auth/logout` — Session invalidation and state clearing.
- `GET /snapshot` — 2-second background polling while active, visible time range filtering, and state revision conflict prevention.
- `GET /operations/{operation_id}` — Tracking of 202 asynchronous operations (`queued`, `running`, `succeeded`, `failed`).
- `POST /jobs` — Authoritative downlink job creation with decimal byte normalization and deadline validation.
- `POST /schedule/runs` — Optimized schedule execution with `expected_schedule_version` and 409 stale-state conflict handling.
- `POST /events` — Rain attenuation, station outage, and recovery disruption injection.
- `POST /simulation/actions` — Fleet simulator controls (`pause`, `resume`, `step`, `reset`).
- `POST /transfers` — Secure payload transfer execution on eligible confirmed contacts.
- `POST /security/checks` — Demonstration security check execution with outcome verification.
- `POST /evaluations` — Evaluation runner against configured scenarios.

---

### Contract version:
`orbitron.v1`  
Enforced on application initialization and every operational snapshot. Mutations are disabled and integration banners displayed if an incompatible version is reported.

---

### Checks run and actual results:
1. **TypeScript Typecheck (`npm run typecheck`):**  
   - Passed with code 0 (`tsc --noEmit`). Strict null checks and unused locals/parameters verified.
2. **Automated Unit & Integration Tests (`npm run test`):**  
   - 9 test files passed, 31 tests passed out of 31:
     - `src/tests/utils.test.ts` (7 tests): byte formatting (1 MB = 1,000,000 B, 1 GB = 1,000,000,000 B), data rates (Mbps), duration, weather capacity factor, local datetime to UTC ISO string, approaching deadline calculation (30 simulation minutes threshold).
     - `src/tests/client.test.ts` (6 tests): CSRF token attachment, `Idempotency-Key` header generation, 409 stale schedule conflict handling, 422 validation detail parsing, `orbitron.v1` contract mismatch detection, network failure distinction, 202 operation tracking.
     - `src/tests/auth.test.ts` (4 tests): valid login with CSRF token capture, 401 invalid credentials rejection, logout token clearing, 401 session expiration handling.
     - `src/tests/requests.test.ts` (2 tests): exact payload structure and units, MB to bytes conversion.
     - `src/tests/timeline.test.tsx` (2 tests): timeline placement formula `(start - visible_start) / (visible_end - visible_start)`, viewport clipping, overlap conflict detection on shared antenna rows.
     - `src/tests/evaluation.test.tsx` (2 tests): zero baseline comparison handling without Infinity or NaN, empty evaluation state.
     - `src/tests/snapshot.test.tsx` (3 tests): empty collection messages, 120-satellite constellation scalability (F20 acceptance scenario), missing position telemetry handled as unavailable without assuming (0, 0).
     - `src/tests/security.test.tsx` (3 tests): transfer integrity failure evidence rendering, security check expected rejection verification, partner gateway key disclaimer.
     - `src/tests/recovery.test.tsx` (2 tests): disruption events (rain vs outage), before/after schedule revisions (`New Assignment` vs `Unassigned`).
3. **Production Build (`npm run build`):**  
   - Passed with code 0 (`tsc && vite build`). Bundle built in 658ms into `frontend/dist/`.

---

### Manual/browser verification:
- Dev server tested with Vite binding strictly to port `5173`.
- Responsive behavior verified: desktop sidebar + main view, tablet collapsible navigation, and mobile viewports down to 360px.
- Focus trap and Escape key dismiss behavior verified on modals (`ConfirmDialog`, `ContactDetailModal`, `DetailDrawer`).
- Polling behavior verified: background polling pauses when browser tab is hidden and refreshes immediately when tab regains focus.

---

### Known limitations:
- Initial MVP uses 2-second HTTP polling against `/snapshot` rather than WebSockets (per Section 4 & 19 of `plan.md`).
- Satellite catalogue and ground-station network are read-only in the frontend console; additions and status updates are driven by the simulator and backend ingestion.
- Drag-and-drop schedule editing is intentionally omitted in this version per MVP specification (Section 19).

---

### Backend dependencies still missing:
- Live backend service was not running locally during development (`http://localhost:8000/api/v1` returned connection refused). Full end-to-end integration requires starting the backend service, SQLite database, and simulator per backend instructions.
- All frontend integration endpoints, request payloads, response schemas, and error shapes conform strictly to `backend/plan.md` and `frontend/plan.md`.

---

### Exact local startup command:
```bash
cd frontend
npm ci
npm run dev
```
Dev server will be accessible at: `http://localhost:5173`
