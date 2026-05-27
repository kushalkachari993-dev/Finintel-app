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
- `AUTH_DATABASE_PATH` optional legacy override
- `AUDIT_DATABASE_PATH` optional legacy override
- `AUTH_TOKEN_SECRET`
- `AUTH_TOKEN_EXPIRE_MINUTES` optional

For the React app, set these in `frontend/.env` when using Sentry:

- `VITE_SENTRY_DSN`
- `VITE_APP_ENV`
- `VITE_APP_RELEASE`
- `VITE_SENTRY_TRACES_SAMPLE_RATE`
- `AUTH_ALLOW_REGISTRATION` optional
- `AUTH_EMAIL_VERIFICATION_TOKEN_MINUTES` optional
- `AUTH_PASSWORD_RESET_TOKEN_MINUTES` optional
- `AUTH_INITIAL_ADMIN_EMAILS` optional
- `CLERK_JWKS_URL` optional for Clerk session JWT verification
- `CLERK_ISSUER` optional for Clerk JWT issuer validation
- `CLERK_AUDIENCE` optional for Clerk JWT audience validation
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
Startup applies any pending migrations to the configured auth/audit
database paths.

The current migrations are:

- `001_create_users.sql`
- `002_create_chat_audit.sql`
- `003_add_auth_controls.sql`

For future schema changes, add a new numbered SQL file instead of
editing old migrations, for example:

```text
004_add_feedback_table.sql
005_add_answer_detail_to_chat_audit.sql
```

## API Security

`/chat` requires an API key:

```http
X-API-Key: your_app_api_key
```

Streamlit reads `APP_API_KEY` from the environment and sends this
header automatically. If the key is missing or invalid, the backend
returns `401`. If a client exceeds `RATE_LIMIT_PER_MINUTE`, it returns
`429`.

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

## User Login

The React frontend can use user accounts instead of exposing an API key
in the browser. The backend provides:

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `POST /auth/verify-email`
- `POST /auth/password-reset/request`
- `POST /auth/password-reset/confirm`
- `GET /admin/users` admin only
- `PATCH /admin/users/{user_id}` admin only

Users are stored in the configured SQLite database. By default the app
uses `DATABASE_URL=sqlite:///data/finintel.sqlite3`, so users and chat
history share one local database file. `AUTH_DATABASE_PATH` remains
available as a legacy override. Passwords are stored with PBKDF2 hashes,
and access tokens are signed with `AUTH_TOKEN_SECRET`.

For local development, registration and password reset responses include
`dev_email_verification_token` or `dev_password_reset_token`. In
production, plug these tokens into an email provider instead of exposing
them to the client.

Set `AUTH_INITIAL_ADMIN_EMAILS` to a comma-separated list of emails to
promote matching users to admin on startup.

## Clerk Auth

Clerk can be enabled as an external auth provider while keeping local
auth and API-key auth as fallbacks.

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

When Clerk is configured, the React app uses Clerk's hosted sign-in and
sign-up UI. The frontend sends the Clerk session token as:

```http
Authorization: Bearer <clerk_session_token>
```

FastAPI verifies the token and uses `clerk:<user_id>` as the chat
principal, so chat history remains isolated per Clerk user.

## Observability

Built-in observability endpoints:

- `GET /metrics` returns Prometheus-style metrics
- `GET /observability` returns a JSON snapshot
- `GET /observability/dashboard` returns a simple HTML dashboard

The dashboard includes request counts, error counts, timeout counts,
average latency, alert messages, and recent traces.

## Chat Audit & History

Chat requests are persisted to the configured SQLite database. By
default this is the same `DATABASE_URL=sqlite:///data/finintel.sqlite3`
file used for users. `AUDIT_DATABASE_PATH` remains available as a legacy
override. Stored fields include principal id, query, route, routing
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
