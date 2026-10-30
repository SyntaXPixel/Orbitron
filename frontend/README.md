# Orbitron — Frontend Operations Console

The web-based operations console for **Orbitron**, a satellite downlink scheduling and secure ground-station sharing platform.

Orbitron enables satellite operators to submit data delivery requests against strict deadlines, inspect antenna booking schedules, handle rain attenuation and ground-station outages, coordinate zero-trust payload transfers across untrusted partner stations, and evaluate scheduler optimizations against a naive FIFO baseline.

---

## Technical Stack

- **Framework:** React 18 (TypeScript with strict checking)
- **Bundler & Dev Server:** Vite 6
- **Routing:** React Router v6
- **Server State & Polling:** TanStack Query v5
- **Icons:** Lucide React
- **Design System:** Cosmos Network Deep Space aesthetic (`DESIGN.md`) with pure CSS design tokens
- **Testing:** Vitest, React Testing Library, jsdom, MSW (Mock Service Worker)

Tested with:
- **Node.js:** `v26.9.0`
- **npm:** `11.19.1`

---

## Local Setup & Development

### 1. Configure Environment

Copy `.env.example` to `.env.local` (or `.env`):

```bash
cd frontend
cp .env.example .env.local
```

Default configuration:
```dotenv
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

### 2. Install Dependencies

Install pinned dependencies from `package-lock.json`:

```bash
npm ci
```

### 3. Run Development Server

Start the Vite development server:

```bash
npm run dev
```

The dev server binds strictly to port `5173` (`http://localhost:5173`) to align with the backend CORS configuration. If the port is in use, it halts with an error instead of switching ports.

---

## Available Scripts

| Command | Description |
|---|---|
| `npm run dev` | Starts local development server on `http://localhost:5173` |
| `npm run typecheck` | Runs TypeScript type checking (`tsc --noEmit`) |
| `npm run test` | Runs the automated Vitest test suite to completion (`vitest run`) |
| `npm run build` | Compiles and bundles production assets into `dist/` |
| `npm run preview` | Previews the production build on port `5173` |

---

## Implemented Screens & Routes

- `/login` — Secure session authentication with backend health checks and contract verification.
- `/` — Fleet & Ground Network Overview: live KPIs, simulated constellation catalogue, and ground-station network.
- `/schedule` — Station & Antenna Timeline: interactive timeline with setup intervals, booked communication windows, conflicts, and simulation-time indicator.
- `/requests` — Downlink Delivery Requests: form to submit downlink jobs with deadline validation, priority classes, and multi-contact splitting.
- `/recovery` — Operational Disruptions & Recovery: simulation of rain attenuation, station outages, recovery, and before/after schedule changes.
- `/security` — Secure Ground-Station Sharing: cryptographic verification, hash comparisons, partner transfer tracking, and controlled security checks.
- `/evaluation` — Scheduler Evaluation Benchmark: comparative analysis between the proposed constraint scheduler and FIFO baseline.
- `/audit` — Operational Audit & Security Log: immutable ledger of operational and scheduling decisions.
- `*` — Application-styled 404 page.

---

## Shared API Contract: `orbitron.v1`

- Contract version: `orbitron.v1` (enforced via `/health` and `/snapshot` metadata).
- Sessions are HttpOnly cookies with CSRF token protection (`X-CSRF-Token`).
- State-changing requests attach an `Idempotency-Key` header (`crypto.randomUUID()`).
- Authoritative clock separation: Real Server Time vs Operational Simulation Time.
