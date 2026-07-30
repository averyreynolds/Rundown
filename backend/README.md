# Rundown Backend

FastAPI service that owns every third-party integration, portfolio math, caching, and (eventually) LLM orchestration for Rundown. See the [root README](../README.md) for the product framing. This document is the handoff artifact for a new session/person to go from a clean checkout to a running backend without reading source first.

---

## Current status

Implemented: portfolio (SnapTrade, read-only), fundamentals (FMP), filings (SEC EDGAR), news (Finnhub), the shared cache/data layer, and the scheduled refresh/snapshot jobs.

**Not yet implemented: the AI advisor (`/advisor/*`).** It was deliberately deferred — it's the highest legal/product-risk area (no-directive-advice boundary) and needs its own Anthropic API key and careful review before being built. Everything else in this document describes what exists today.

---

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for dependency management

## Setup

```bash
cd backend
uv sync
cp .env.example .env
```

Fill in `.env` with real values:

| Variable | Where to get it |
|---|---|
| `SNAPTRADE_CLIENT_ID`, `SNAPTRADE_CONSUMER_KEY` | [SnapTrade dashboard](https://dashboard.snaptrade.com/) — free personal tier |
| `FMP_API_KEY` | [Financial Modeling Prep](https://site.financialmodelingprep.com/) — free tier, ~250 requests/day |
| `FINNHUB_API_KEY` | [Finnhub](https://finnhub.io/) — free tier, 60 calls/min |
| `ANTHROPIC_API_KEY` | [Anthropic Console](https://console.anthropic.com/) — not yet used by any route, but `Settings()` requires it to be present |
| `SEC_EDGAR_USER_AGENT` | Your own value: `"AppName/Version (you@example.com)"`. SEC requires a descriptive, real contact email or `data.sec.gov` returns 403. |
| `API_BEARER_TOKEN` | Generate one: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |

Every other variable in `.env.example` (DB URL, CORS origins, cache TTLs, log level) has a sensible default — only change them if you know why.

## Running the dev server

```bash
uv run uvicorn app.main:app --reload
```

- Tables auto-create on first run against a fresh SQLite file — there is no separate migration step (see `app/db/session.py`).
- **Never run this with `--workers` set above 1** (uvicorn's `--reload` and `--workers` flags are mutually exclusive anyway, so this only matters once you drop `--reload` for a more production-like run). APScheduler (the scheduled cache-refresh/snapshot jobs) assumes a single process; multiple workers would create N independent schedulers each refreshing the cache redundantly, and would break the in-process lock that prevents `SnapTradeService.connect()` from double-registering with SnapTrade under a race.
- Visit `http://127.0.0.1:8000/docs` for the interactive OpenAPI schema — every implemented endpoint's request/response shape is there.

### The `127.0.0.1`-only constraint

The backend has no multi-user auth — access control is a shared-secret bearer token (`API_BEARER_TOKEN`, sent as `Authorization: Bearer <token>`) checked on every route except `/health` and `/docs`. CORS is a secondary, browser-only restriction on top of that, **not** the real gate: it only governs whether a browser lets JavaScript *read* a cross-origin response, not whether the server *executes* a request from a non-browser client.

This whole model depends on the backend staying bound to `127.0.0.1`. Widening the bind (e.g. `--host 0.0.0.0` to check the dashboard from a phone) is a deliberate decision to make consciously — it exposes every route to anything on the local network with only the bearer token standing between it and your real brokerage/financial data.

## Calling the API

Every route except `/health`, `/docs`, `/openapi.json`, and `/redoc` requires the bearer token:

```bash
curl -H "Authorization: Bearer <your API_BEARER_TOKEN>" http://127.0.0.1:8000/portfolio/positions
```

First-time flow: `POST /portfolio/connect` registers (once) and returns a SnapTrade connection portal URL; open it, connect a brokerage account, then `/portfolio/accounts` and `/portfolio/positions` return real data. Before connecting, those two routes return `409` (not a crash) so the frontend can distinguish "nothing to show yet" from a provider outage.

## Running the test suite

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy .
```

All four should pass clean before opening a PR. The test suite never hits a live API or consumes rate-limit budget — every external call (SnapTrade, FMP, EDGAR, Finnhub) is mocked (`respx` for the httpx-based providers; a structural fake for the SnapTrade SDK). Domain/portfolio-math tests (`tests/domain/`) do no I/O at all.

## Architecture at a glance

- `app/domain/` — pure portfolio math (allocation, concentration, P&L). No I/O, no framework imports.
- `app/services/` — one module per third-party integration, plus shared plumbing (`cache_through.py` for the read-through-cache-with-stale-fallback pattern every provider uses, `errors.py` for the exception types `app/api/error_handlers.py` maps to HTTP responses).
- `app/cache/` — the one caching module (`cache_entries` table via `CacheRepository`), with per-data-type TTLs centralized in `ttl_policy.py`.
- `app/db/` — the only package that knows a connection string or SQL dialect. Swapping SQLite for Postgres later is a `DATABASE_URL` + driver change here, not a rewrite.
- `app/scheduler/` — APScheduler jobs that refresh the cache on a schedule (never per-request) and write the daily portfolio snapshot (`portfolio_snapshots` — write-only for now; trend/comparison logic is deferred follow-up work).
- `app/api/` — routers stay thin; all orchestration lives in `services/`.

## Known limitations (by design, for this MVP)

- **No encryption at rest** for the SnapTrade `user_secret` or cached positions/balances — the SQLite file is gitignored and assumed to never leave your machine. Add field-level encryption before running this anywhere less trusted than a single local machine.
- **SnapTrade's `connection_type="read"` enforcement is not independently verified.** Whether the brokerage enforces read-only access at the OAuth-consent level (a hard boundary) or only treats it as a request-shape hint to the connection portal couldn't be confirmed without a live SnapTrade account. The code-level guarantee — `app/services/snaptrade_service.py` never imports SnapTrade's trading/orders SDK namespace (enforced by a static AST test) — is the guarantee that's actually verified. Confirm the platform-level behavior against SnapTrade's docs/support before treating this as airtight.
- **No trade execution anywhere.** This is a hard product/legal boundary (see the root `CLAUDE.md`), not an oversight — do not add order/trade/transfer endpoints without explicitly revisiting that boundary first.
- **FMP/SnapTrade response field names were verified by introspecting the installed SDK/API docs, not against a live response** (no real API keys are available in this environment). Re-verify against real data once you have credentials — see the module docstrings in `app/services/fmp_service.py` and `app/services/snaptrade_service.py` for exactly what's unverified.
