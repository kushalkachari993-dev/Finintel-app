# FinIntel AI

Indian Financial Intelligence & Research Platform.

## Stack
- FastAPI
- Streamlit
- Groq API
- Tavily
- Yahoo Finance via yfinance
- Pydantic

## Run Backend
uvicorn backend.main:app --reload

## Run Frontend

React frontend:

```powershell
cd frontend
npm install
npm run dev
```

The React dev server runs on `http://127.0.0.1:5173` by default.

Production build:

```powershell
cd frontend
npm run build
```

Legacy Streamlit frontend:

```powershell
streamlit run frontend/streamlit_app.py
```

## Deploy To Render

This repo includes a Render Blueprint at `render.yaml` with a FastAPI
backend service and a React static frontend service. See
`docs/render-deployment.md` for the setup checklist and required
environment variables.

## CI/CD

GitHub Actions workflows live in `.github/workflows`:

- `ci.yml` runs backend compile/tests and frontend production build.
- `render-deploy.yml` can manually trigger Render deploy hooks.
- `uptime-monitor.yml` checks the deployed frontend and backend health
  every 15 minutes.

See `docs/ci-cd.md` for setup details.

## Configuration

Copy `.env.example` to `.env` and set:

- `GROQ_API_KEY`
- `TAVILY_API_KEY`
- `APP_ENV` optional, for example `development` or `production`
- `APP_RELEASE` optional release label for observability
- `SENTRY_DSN` optional backend Sentry DSN
- `SENTRY_TRACES_SAMPLE_RATE` optional, defaults to `0.05`
- `GROQ_MODEL` optional legacy default
- `GROQ_FAST_MODEL` optional, used for brief/basic routes
- `GROQ_COMPLEX_MODEL` optional, used for detailed mode and complex routes
- `BACKEND_API_URL` optional for Streamlit
- `FRONTEND_ALLOWED_ORIGINS` optional comma-separated CORS origins
- `APP_API_KEY`
- `API_CLIENTS_JSON` optional for multiple API clients
- `DATABASE_URL` optional, defaults to `sqlite:///data/finintel.sqlite3`
- `AUDIT_DATABASE_PATH` optional legacy override
- `CLERK_JWKS_URL` required for Clerk session JWT verification
- `CLERK_ISSUER` required for Clerk JWT issuer validation
- `CLERK_AUDIENCE` optional Clerk JWT audience validation

For the React app, set `VITE_CLERK_PUBLISHABLE_KEY` and the optional
Sentry values in `frontend/.env`:

- `VITE_CLERK_PUBLISHABLE_KEY`
- `VITE_SENTRY_DSN`
- `VITE_APP_ENV`
- `VITE_APP_RELEASE`
- `VITE_SENTRY_TRACES_SAMPLE_RATE`
- `RATE_LIMIT_PER_MINUTE` optional
- `CHAT_EXECUTION_TIMEOUT_SECONDS` optional
- `EXTERNAL_CALL_TIMEOUT_SECONDS` optional
- `RAG_ENABLED` optional
- `RAG_TOP_K` optional
- `RAG_MIN_SCORE` optional
- `LOG_LEVEL` optional
- `STOCK_DATA_CACHE_SECONDS` optional
- `SEARCH_CACHE_SECONDS` optional
- `TICKER_CACHE_SECONDS` optional
- `REDIS_URL` optional for shared cache/rate limiting
- `SYMBOL_MASTER_PATH` optional

## Quality Checks

Run tests:

```powershell
uv run pytest
```

Run a syntax/import compile check:

```powershell
uv run python -m compileall backend frontend testing.py
```

## Database Migrations

SQLite schema changes are versioned in `backend/storage/migrations`.
Startup applies any pending migrations to the configured audit database.

The current migrations are:

- `001_create_users.sql`
- `002_create_chat_audit.sql`
- `003_add_auth_controls.sql`
- `004_add_chat_response_payload.sql`
- `005_create_chat_conversations.sql`
- `006_add_conversation_organization.sql`

The user/auth migrations are retained as immutable migration history, but
the application no longer reads or writes those local account tables.

For future schema changes, add a new numbered SQL file instead of
editing old migrations, for example:

```text
004_add_feedback_table.sql
005_add_answer_detail_to_chat_audit.sql
```

## API Security

The React frontend authenticates `/chat`, `/report`, and history requests
with a Clerk bearer token. API keys are reserved for legacy Streamlit and
other explicitly configured server-to-server clients:

```http
X-API-Key: your_app_api_key
```

Streamlit reads `APP_API_KEY` from the environment and sends this header
automatically. The React build does not receive an API key. Invalid or
missing credentials return `401`; exceeding `RATE_LIMIT_PER_MINUTE`
returns `429`.

For multiple clients, prefer `API_CLIENTS_JSON` with SHA-256 key hashes:

```json
[
  {
    "client_id": "frontend",
    "name": "Streamlit frontend",
    "key_hash": "sha256_hex_digest",
    "role": "user",
    "active": true
  }
]
```

`APP_API_KEY` still works as a single default client for local setup.

## Clerk Auth

Clerk is the only user account provider. The application does not expose
local registration, login, email-verification, password-reset, or local
user-administration endpoints. Clerk's hosted sign-in flow handles these
account operations, including password recovery.

Frontend:

```env
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
```

Backend:

```env
CLERK_JWKS_URL=https://.../.well-known/jwks.json
CLERK_ISSUER=https://...
CLERK_AUDIENCE=
```

The React app uses Clerk's hosted sign-in and sign-up UI. The frontend
sends the Clerk session token as:

```http
Authorization: Bearer <clerk_session_token>
```

FastAPI verifies the token and uses `clerk:<user_id>` as the chat
principal, so chat history remains isolated per Clerk user. `GET /auth/me`
returns the verified Clerk profile. API keys remain available only for
legacy Streamlit and explicitly configured server-to-server clients.

## Observability

Built-in observability endpoints:

- `GET /metrics` returns Prometheus-style metrics
- `GET /observability` returns a JSON snapshot
- `GET /observability/dashboard` returns a simple HTML dashboard

The dashboard includes request counts, error counts, timeout counts,
average latency, alert messages, and recent traces.

## Chat Audit & History

Chat requests are persisted to the configured database. By default this
is `DATABASE_URL=sqlite:///data/finintel.sqlite3`. `AUDIT_DATABASE_PATH`
remains available as a legacy override. Stored fields include principal
id, query, route, routing
metadata, query intelligence, response status/error, confidence score,
latency, and timestamp.

Users can retrieve their own recent chat history with:

```http
GET /chat/history
Authorization: Bearer <token>
```

## Shared Cache & Rate Limiting

Set `REDIS_URL` to use Redis for shared chat rate limiting and TTL
caches across multiple backend workers. If Redis is not configured or is
unavailable, the app falls back to in-process memory for local
development.

## RAG

Educational answers use a local curated knowledge base in
`data/knowledge/educational_finance.json`. The retriever is deterministic
and dependency-light, so tests can run without live APIs.

Run the RAG retrieval evaluation:

```powershell
uv run python scripts/rag_eval.py
```

## Trusted Company Context

Fundamental and comparison answers enrich Yahoo Finance metrics with
on-demand trusted web context from filtered finance sources. Retrieved
source URLs are returned as `sources_used` and shown in the UI.

## Company Symbol Master

Company recognition and local ticker resolution use
`data/market/indian_equities.csv` through `SYMBOL_MASTER_PATH`. The
bundled file is generated from the public IIFL NSE/BSE cash-equity scrip
master and normalized into the app's symbol format.

Refresh it with:

```powershell
uv run python scripts/update_symbol_master.py
```
