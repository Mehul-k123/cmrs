# CMRS: Cash Management & Reconciliation System

Tracks loan-repayment cash through its full lifecycle, and makes every difference along the way visible and accountable:

```
Expected (EMI due) → Collected (agent) → Branch Received (verified) → Bank Deposited → Settled
```

- **Agents** record repayments (partial allowed, unique receipt numbers, duplicate protection), see their daily collections and submit cash to the branch.
- **Branch managers** count the cash, compare expected against actual, approve or reject, record discrepancies and create bank deposits.
- **Finance** reconciles deposits against the bank statement (settled, mismatched, failed or delayed) and reviews the audit trail.
- **Dashboards** show expected, collected, cash with agents, received at branches, deposited, settled, outstanding and discrepancies, filterable by date, branch, agent and status.
- **UPI repayments** go through a mock payment gateway with signed webhooks and land in the same ledger and reconciliation views.

| | |
|---|---|
| Live app | https://cmrs-web.onrender.com |
| API docs (Swagger) | https://cmrs-api-8eng.onrender.com/api/docs/ |
| Business rules & assumptions | [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) |
| Database schema | [docs/SCHEMA.md](docs/SCHEMA.md) |
| API reference | [docs/API.md](docs/API.md) |
| Video outline | [docs/VIDEO_SCRIPT.md](docs/VIDEO_SCRIPT.md) |

## Test credentials

All demo users share the password **`Demo@1234`**. The login page also has one-click buttons for them.

| Role | Username | Scope |
|---|---|---|
| Admin | `admin` | Everything; also Django admin at `/admin/` |
| Finance | `finance` | All branches: settlement, audit log |
| Branch Manager | `bm.mumbai` | Mumbai Central |
| Branch Manager | `bm.pune` | Pune Camp |
| Collection Agent | `agent.ravi`, `agent.priya` | Mumbai customers |
| Collection Agent | `agent.arjun`, `agent.sneha` | Pune customers |

The seed data covers every scenario: a fully settled batch, a cash **shortage** followed by a **bank mismatch**, a **rejected** and then resubmitted batch whose deposit is **delayed**, an **excess** count whose deposit **failed**, a reversed entry, cash still with agents or pending verification, and UPI payments (settled, captured, failed).

## Architecture

```
┌──────────────────────────┐   HTTPS / JSON + JWT    ┌───────────────────────────────────────────┐
│ React 18 + TypeScript    │ ──────────────────────▶ │ Django 5 + DRF                            │
│ Vite, TanStack Query,    │                         │  views (thin: auth, scoping, validation)  │
│ Tailwind, Recharts       │ ◀────────────────────── │  services.py (business rules,             │
│ role-based nav & guards  │   {code,message,details}│   transactions + SELECT … FOR UPDATE)     │
└──────────────────────────┘                         │  audit log · structured logs · OpenAPI    │
                                                     └───────────────┬───────────────────────────┘
        Mock UPI gateway ──HMAC-signed webhook──▶ /api/payments/webhook/   │ psycopg 3
                                                     ┌───────────────▼───────────────┐
                                                     │ PostgreSQL 16 (NUMERIC(14,2)) │
                                                     └───────────────────────────────┘
```

**Backend apps** (`backend/apps/`):

| App | Responsibility |
|---|---|
| `core` | Branch, AuditLog, `MoneyField`, Decimal helpers, RBAC + row scoping, error envelope, reference sequences, `seed_demo` |
| `accounts` | Custom User (role, branch), JWT login/refresh/logout |
| `loans` | Customers, loans, repayment schedule generation, outstanding |
| `cash` | Collections & allocation, cash submissions, branch verification, discrepancies, reversals |
| `deposits` | Bank deposits, settlement / failure, delayed-settlement flag (`flag_delayed_settlements`) |
| `payments` | Mock gateway, payment intents, idempotent signed webhooks |
| `dashboard` | Aggregated KPIs, lifecycle, trend, branch/agent breakdowns |

### Key engineering decisions

- **Money is never a float.** `NUMERIC(14,2)` columns, `Decimal` arithmetic with explicit rounding, strings over the wire. The UI previews differences in integer paise; totals always come from the server.
- **Business rules live in a service layer**, not views or serializers. Each operation is one DB transaction that locks the rows it changes, so concurrent double-approvals or double-collections are impossible.
- **Append-only financial history.** No update or delete endpoints for collections. Reconciled rows are locked at the model level; corrections are explicit, audited reversals.
- **Two duplicate guards.** A required `Idempotency-Key` stops technical duplicates (retries, double clicks). A 10-minute same-loan/same-amount check catches human duplicates but allows a confirmed genuine second payment.
- **Defence in depth for RBAC.** Permission classes per action, plus row scoping on every queryset (out-of-scope records return 404).
- **Optional tech, used only where it pays off:** TypeScript (typed money-as-string contracts), Docker Compose (one-command setup), Pytest (52 tests over the business cases), Swagger (API docs), GitHub Actions CI, structured logging with request ids. **Not used:** Redis/Celery. The only background need (flagging delayed settlements) is a single daily management command, and "delayed" is also computed live in queries.

## Running locally

### Option A: Docker (one command)

```bash
docker compose up --build
```

- App: http://localhost:8080 (nginx serves the SPA and proxies `/api`)
- API docs: http://localhost:8000/api/docs/
- The database is migrated and demo data seeded automatically on first boot.

### Option B: without Docker

Prerequisites: Python 3.12, Node 18+, PostgreSQL 14+.

```bash
# Database (any Postgres works; this matches the default DATABASE_URL)
docker run -d --name cmrs-db -e POSTGRES_USER=cmrs -e POSTGRES_PASSWORD=cmrs -e POSTGRES_DB=cmrs \
  -p 5433:5432 postgres:16

# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # then set DJANGO_DEBUG=true for local dev
python manage.py migrate
python manage.py seed_demo      # --reset to wipe and reseed
python manage.py runserver      # http://localhost:8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173 (proxies /api → :8000)
```

### Tests & quality

```bash
cd backend && pytest            # 52 tests: business rules, RBAC, idempotency, webhooks, dashboard
cd backend && ruff check .
cd frontend && npm run build    # type-check + production build
```

## Environment variables

### Backend (`backend/.env`, see `.env.example`)

| Variable | Default | Description |
|---|---|---|
| `DJANGO_DEBUG` | `false` | Debug mode. Never true in production |
| `DJANGO_SECRET_KEY` | *(required when DEBUG=false)* | Signs JWTs and sessions |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames |
| `CSRF_TRUSTED_ORIGINS` | – | Origins for Django admin over HTTPS |
| `DATABASE_URL` | `postgres://cmrs:cmrs@localhost:5433/cmrs` | PostgreSQL connection URL |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Frontend origin(s) |
| `JWT_ACCESS_MINUTES` | `30` | Access token lifetime |
| `JWT_REFRESH_DAYS` | `1` | Refresh token lifetime (rotated + blacklisted) |
| `LOGIN_THROTTLE_RATE` | `10/min` | Brute-force protection on login |
| `SETTLEMENT_SLA_DAYS` | `2` | Days before an unsettled deposit counts as delayed |
| `DUPLICATE_COLLECTION_WINDOW_MINUTES` | `10` | Window for the possible-duplicate check |
| `PAYMENT_GATEWAY_WEBHOOK_SECRET` | `mock-webhook-secret` | HMAC secret for gateway webhooks |
| `LOG_LEVEL` | `INFO` | Root log level |

### Frontend (`frontend/.env`)

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | *(empty)* | API origin, e.g. `https://cmrs-api.onrender.com`. Leave empty when the API is served on the same origin or through the Vite proxy |

## Deploying to Render

1. Push this repository to GitHub.
2. In Render: **New → Blueprint**, then pick the repo. `render.yaml` creates **cmrs-db** (Postgres), **cmrs-api** (Django/gunicorn) and **cmrs-web** (static SPA).
3. If Render gives the services different hostnames, update `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` (API) and `VITE_API_BASE_URL` (web), then redeploy.
4. The API runs migrations and seeds the demo data on first boot (`seed_demo --if-empty`).

Free-tier note: the API sleeps when idle, so the first request after a pause can take about 30–50 seconds.

## Project layout

```
backend/
  config/            settings (env-driven), urls, wsgi
  apps/<app>/        models · services · serializers · views · urls · admin
  tests/             pytest suite
frontend/
  src/api            axios client (JWT refresh), typed API models
  src/auth           auth context
  src/components     UI kit, layout, filters
  src/lib            formatting, exact money helpers, query hooks
  src/pages          one file per screen
docs/                assumptions, schema, API, video outline
```

## What I'd improve with more time

- A proper **double-entry ledger** (cash-in-hand, branch vault and bank accounts per entity) in place of status columns.
- **Bank-statement import** (CSV/MT940) with automatic matching of deposits by reference and amount.
- A real **Razorpay/Cashfree sandbox** behind the existing `GatewayClient` interface, plus refund handling for over-captured payments.
- **Maker-checker** for reversals and discrepancy write-offs; agent liability tracking for shortages.
- An offline-first agent **PWA** (queue collections with idempotency keys, sync later).
- Playwright E2E tests in CI, Sentry, and CSV/Excel exports from every report.
