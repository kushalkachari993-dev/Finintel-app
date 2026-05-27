# CI/CD

This repository uses GitHub Actions for CI and Render's native
after-checks-pass deploy behavior for CD.

## CI

Workflow: `.github/workflows/ci.yml`

It runs on pushes to `main`/`master` and on pull requests.

Backend job:

- Installs Python 3.11
- Installs dependencies with `uv sync --locked`
- Compiles the backend with `python -m compileall backend`
- Runs the backend test suite with test-only environment values

Frontend job:

- Installs Node 22
- Installs dependencies with `npm ci`
- Builds the React app with `npm run build`

## Render CD

The Render Blueprint sets both services to:

```yaml
autoDeployTrigger: checksPass
```

That means Render deploys from `main`/`master` only after GitHub Actions
checks pass. This avoids deploying broken commits.

## Manual Render Deploy

Workflow: `.github/workflows/render-deploy.yml`

This is an optional manual fallback from the GitHub Actions page. It
triggers Render deploy hooks only when you run it manually.

To enable it, add these GitHub repository secrets:

```text
RENDER_BACKEND_DEPLOY_HOOK_URL
RENDER_FRONTEND_DEPLOY_HOOK_URL
```

You can find each hook in Render:

1. Open the Render service.
2. Go to **Settings**.
3. Copy the **Deploy Hook** URL.
4. Add it as a GitHub repository secret.

The manual deploy workflow is optional because the Blueprint already uses
Render's after-CI deploy behavior.

## Uptime Monitor

Workflow: `.github/workflows/uptime-monitor.yml`

This runs every 15 minutes and can also be started manually from GitHub
Actions. It checks:

- Frontend page loads successfully
- Backend `/health` returns `{"status":"ok"}`

Defaults:

```text
FRONTEND_URL=https://finintel-ai-frontend.onrender.com
BACKEND_URL=https://finintel-ai-backend.onrender.com
```

If Render gives your backend a different URL, add GitHub repository
variables:

```text
FRONTEND_URL=https://your-frontend.onrender.com
BACKEND_URL=https://your-backend.onrender.com
```

GitHub will mark the workflow failed if either service is down. Enable
GitHub Actions email notifications to receive uptime alerts.
