---
title: "feat: Scaffold Rundown FastAPI Backend"
type: feat
status: active
date: 2026-07-28
deepened: 2026-07-28
---

# feat: Scaffold Rundown FastAPI Backend

## Summary

Scaffold the entire `backend/` service from nothing to a running, typed, tested FastAPI application that a separate frontend session can build against. The backend owns all five external integrations (SnapTrade, FMP, SEC EDGAR, Finnhub, Anthropic Claude) behind one service module each, a pure-function domain layer for portfolio math, one SQLite-backed caching module wrapped in a swap-friendly repository, and an AI advisor whose grounding and no-directive-advice rules are enforced structurally (system prompt + a response-side phrase filter), not just by convention. Real HTTP clients are wired up against real endpoints and read keys from `backend/.env`; nothing here is a fixture-only stub. The plan ends with a "handoff readiness" unit whose verification criteria define what "ready for basic frontend implementation" concretely means.

---

## Problem Frame

The repository is currently documentation-only — `CLAUDE.md`, `README.md`, and `LICENSE` at the root, no code. CLAUDE.md dictates the backend's architecture and hard rules in detail (see Context & Research below) but none of it exists yet. Someone needs to build a real, working backend before frontend work can start, and that person will be a different session/person than the one who wrote this plan — so the plan needs to leave behind not just code, but a legible, runnable, documented starting point.

---

## Requirements

- R1. Backend exposes typed REST endpoints for portfolio holdings/positions synced read-only from SnapTrade, with allocation, concentration, and P&L computed by pure domain functions.
- R2. Backend exposes a fundamentals endpoint (FMP ratios/key metrics) that is cached with an explicit TTL and never fetched live per request.
- R3. Backend exposes a filings endpoint (SEC EDGAR) that can list a company's recent 10-K/10-Q/8-K filings and retrieve authoritative filing text for summarization.
- R4. Backend exposes a personalized news endpoint (Finnhub), filtered to the user's holdings/watchlist and cached.
- R5. Backend exposes an AI advisor chat endpoint (Claude) that answers only from explicitly-provided structured context, cites the specific source it drew from, never produces directive/prescriptive language, and gracefully reframes "what should I do" questions instead of refusing or recommending.
- R6. All third-party API keys are read from `backend/.env` server-side only and never appear in a response sent to a client.
- R7. Every data point returned to the frontend carries its source and an "as of" timestamp.
- R8. No trade/order/transfer execution endpoint exists anywhere in the codebase; the SnapTrade integration is structurally read-only.
- R9. The data/cache layer targets SQLite for the MVP but is abstracted (session factory + repository pattern) so swapping the underlying database is a small, contained change.
- R10. Domain (portfolio math) logic has full unit test coverage using synthetic fixtures; all external services are mocked in tests so the suite never hits a live API or consumes rate-limit budget.
- R11. The codebase passes `ruff` (format + lint) and `mypy`; the running app documents its contract via OpenAPI (`/docs`) well enough for a frontend session to integrate against without reading backend source.
- R12. A minimal daily snapshot of point-in-time holdings/allocation is persisted (no comparison/trend logic yet), so the historical data a future trend-narrative feature needs begins accumulating immediately rather than only after a later follow-up plan starts collecting it.

---

## Scope Boundaries

- No frontend implementation of any kind — this plan produces backend only, for handoff to a separate session.
- No trade, order, or transfer execution endpoints (hard rule; SnapTrade is wired up in `connection_type="read"` mode only).
- No multi-user authentication/session system. Single local user, backend and frontend assumed to run bound to `127.0.0.1` during development; access control is a shared-secret bearer token plus CORS-origin restriction (see Key Technical Decisions) — CORS alone was found during review to not be a request-level access control, so it is defense-in-depth, not the gate itself.
- No voice advisor (README explicitly scopes voice to "after" MVP).
- No production infrastructure — no Docker, no CI/CD pipeline, no cloud deployment config. This plan targets local-dev readiness only.
- No real API keys, account numbers, or holdings data anywhere in the repo; `.env.example` ships with placeholders only, and all test fixtures are synthetic.

### Deferred to Follow-Up Work

- Trend *comparison* logic and any related endpoint/UI (e.g. "up from 11% three months ago" from the README's advisor example) — querying and diffing snapshots is genuinely separate work from writing them. What is **not** deferred: R12 ships a minimal daily snapshot-*write* job (U9) now, specifically so historical data starts accumulating immediately rather than the comparison feature being blocked behind an additional multi-month data-collection wait once follow-up work eventually begins. (Surfaced during review: deferring the write job too, not just the comparison feature, would have quietly cut the README's own lead advisor example for longer than the deferral note originally implied.)
- Encryption-at-rest for the SnapTrade `user_secret` **and the cached positions/balances data** stored in SQLite — MVP relies on the local SQLite file being gitignored and never leaving the machine (see Risks & Dependencies); add field-level encryption if the app ever runs somewhere less trusted than a single local machine.
- A persisted, server-side watchlist entity for R4 — the news endpoint accepts a client-supplied `symbols` query parameter for MVP; watchlist state (if any) lives client-side. Add a persisted watchlist table only if a future frontend needs the backend to remember it.
- Any production deployment, containerization, or CI pipeline.

---

## Context & Research

### Relevant Code and Patterns

None — the repository has no existing backend code, `pyproject.toml`, `requirements.txt`, `.gitignore`, or CI config. `CLAUDE.md` and `README.md` are the only two documents to plan against, and both were read in full. Their conventions and hard rules (Python 3.12+/FastAPI/Pydantic, `backend/app/services/` one-module-per-provider, `backend/app/domain/` pure functions, one caching module, `ruff`+`mypy`, `pytest` with mocked externals, and the seven hard rules around advisor grounding/directive-advice, API-key isolation, rate-limit discipline via caching, no committed secrets, provenance/freshness labeling, and no trade execution) are treated as binding throughout this plan, not re-litigated.

### Institutional Learnings

None found — `docs/solutions/` does not exist yet in this repo. Worth standing up after this plan ships so architecture/tooling decisions made here (service-per-provider layout, single cache module, advisor grounding contract) become searchable institutional knowledge for future work.

### External References

- **SnapTrade deprecation (time-sensitive, two layers deep):** user-level "Get All User Holdings" / user-level Activities endpoints return `410 Gone` for accounts created after 2026-04-25 — this plan targets account-scoped endpoints instead. But the account-scoped positions endpoint the plan originally landed on, `get_user_account_positions`, carries its **own**, independent deprecation notice pointing integrators to the newer unified `get_all_account_positions` (equity + options + other asset classes in one call) — verified directly against the installed `snaptrade-python-sdk` package's bundled documentation during review, not just the docs site. This plan targets `list_user_accounts` → `get_all_account_positions` / `get_user_account_balance`. ([SnapTrade docs](https://docs.snaptrade.com/))
- **SnapTrade SDK has native async support (corrected during review):** `snaptrade-python-sdk` (verified against the actual PyPI package, v12.0.3) ships an `aiohttp`-backed async twin of every method (prefixed `a`, e.g. `aget_all_account_positions`, `alogin_snap_trade_user`, `aregister_snap_trade_user`) — it is not sync-only. This plan uses the async methods directly rather than wrapping the sync ones in `run_in_threadpool`, which avoids an unnecessary thread-safety question (a shared client's session accessed from multiple threadpool workers) the SDK's own async client sidesteps entirely.
- **FMP:** use `/stable/...` endpoints (`/stable/ratios`, `/stable/key-metrics-ttm`), not legacy `/api/v3/...`. Free tier: 250 requests/day. ([FMP docs](https://site.financialmodelingprep.com/developer/docs/stable/metrics-ratios))
- **SEC EDGAR:** `data.sec.gov` requires a descriptive `User-Agent` header on every request (app name + contact email) or requests 403. Fair-access limit is 10 req/sec per IP across all of EDGAR. No API key needed. Key endpoints: `submissions/CIK##########.json`, `api/xbrl/companyfacts/CIK##########.json`, full-text search at `efts.sec.gov`, and raw filing documents under `www.sec.gov/Archives/edgar/data/...`. ([SEC EDGAR developer resources](https://www.sec.gov/about/developer-resources))
- **Finnhub:** free tier 60 calls/min; `company-news` endpoint. ([Finnhub rate limits](https://finnhub.io/docs/api/rate-limit))
- **Anthropic:** current recommended default model is `claude-sonnet-5` (avoid hardcoding a dated model id — deprecations happen on a rolling schedule; `claude-opus-4-1-20250805` retires 2026-08-05). The Citations API (`citations: {"enabled": true}` on a `document` content block) is a structural mechanism for grounding filing summaries in exact source passages, not just prompt wording. ([Anthropic model overview](https://platform.claude.com/docs/en/about-claude/models/overview), [Citations](https://platform.claude.com/docs/en/build-with-claude/citations))
- **FastAPI 0.140.x** (Pydantic v2-only, `>=2.7.0`): lifespan context manager is the only non-deprecated startup/shutdown hook; `BackgroundTasks` is single-fire and unsuitable for periodic refresh — use **APScheduler**'s `AsyncIOScheduler` started in lifespan, single-worker assumption. ([FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/))
- **httpx + respx** for typed async clients and HTTP-layer test mocking without hitting live APIs. ([httpx async docs](https://www.python-httpx.org/async/), [respx guide](https://lundberg.github.io/respx/guide/))
- **SQLAlchemy 2.0 async ORM** (`aiosqlite` driver now, `asyncpg` later) behind a repository pattern — the driver string is the only thing that changes when swapping databases, provided nothing above the session factory writes driver-specific SQL. ([SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html))
- **mypy strict mode + ruff**: strict flag set and a FastAPI-aware ruff rule selection (`E,W,F,I,UP,B,N,ANN,S,SIM,RUF,FAST,PT`) documented for `pyproject.toml`.

---

## Key Technical Decisions

- **Service-per-provider clients, one shared `httpx.AsyncClient` each:** each of FMP/EDGAR/Finnhub/Anthropic gets one long-lived `httpx.AsyncClient` (or SDK client wrapping one) constructed in the FastAPI lifespan and stored on `app.state`, injected into services via `Depends`. Avoids per-request client churn and keeps connection pooling intact, which matters for rate-limit discipline. This applies uniformly across all four HTTP-based providers so System-Wide Impact's interaction graph and this decision agree on what's lifespan-managed.
- **Use the SnapTrade SDK's native async methods, not `run_in_threadpool`-wrapped sync calls.** `snaptrade-python-sdk` ships an `aiohttp`-backed async twin of every method (corrected during review — see External References); one lifespan-shared async SDK client instance is constructed, consistent with the other providers. This is simpler and avoids a thread-safety question (a shared client's session accessed from multiple threadpool workers) that wrapping the sync methods would have introduced for no benefit, since the SDK already solves it natively.
- **SnapTrade integration is account-scoped and read-only, enforced at two independent levels — code-level and (pending verification) platform-level:** the code-level guarantee is certain: the service module never imports SnapTrade's trading/orders SDK namespace, checked in review. The platform-level guarantee — whether `login_snap_trade_user(..., connection_type="read")` is enforced by the brokerage's own OAuth consent (a hard boundary on what the resulting `user_secret` can authorize, even outside Rundown's code) versus being only a request-shape hint to SnapTrade's connection portal — is *not* independently confirmed by this plan's research and should be explicitly verified against SnapTrade's platform documentation during U4 (see Open Questions). Treat the code-level import restriction as the actually-enforced guarantee until that's confirmed; this matters more than it would otherwise because encryption-at-rest for the same `user_secret` is deferred (Scope Boundaries), so a leaked secret's blast radius depends on which of the two guarantees is real. The `snaptrade_connection` row is treated as a true singleton (unique/single-row constraint): a second concurrent `connect()` call that races the first's check-then-register sees the conflict and reuses the row that won, rather than double-registering with SnapTrade or crashing on an unhandled integrity error.
- **One generic `cache_entries` table, not bespoke tables per provider:** `(provider, cache_key, payload_json, fetched_at, ttl_seconds)` behind a single `CacheRepository.get_or_none()` / `.set()`, with per-data-type TTLs centralized in one `ttl_policy.py`. Matches CLAUDE.md's "one caching module" instruction directly and keeps TTL policy inspectable in one place. `.set()` is a single atomic `INSERT ... ON CONFLICT(provider, cache_key) DO UPDATE` statement, not a check-then-insert-or-update round trip — two near-simultaneous writers targeting the same key (a scheduled refresh racing a request-triggered fetch-on-miss for the same symbol) must not be able to both observe "no row" and both attempt an insert.
- **SQLAlchemy 2.0 async engine/session behind a single `db/session.py` factory, using `Base.metadata.create_all()` at startup rather than Alembic, with WAL journal mode and a busy-timeout PRAGMA set at engine creation.** Swapping SQLite for Postgres later is a `DATABASE_URL` + driver dependency change, not a rewrite — but only holds if nothing outside `db/` and the repositories ever imports SQLAlchemy or writes raw SQL. Versioned migrations were reconsidered during review and dropped for now: R9 only requires a swap-friendly session/repository abstraction, which `create_all()` plus the repository pattern already satisfies, and for a single developer with a single SQLite file and no deployment target, Alembic is tooling for a problem this MVP doesn't have yet — it can be added later, before any real multi-environment or production need arises, without touching the repository layer at all. WAL mode lets request-serving reads proceed without blocking on a concurrent scheduler write (only writer-vs-writer is serialized); the busy-timeout is a retry-on-lock safety net for the remaining writer-vs-writer case (a scheduled refresh and a request-triggered positions-cache write landing at the same moment). Without this, the plan's own design — request handlers and an in-process scheduler both writing `cache_entries` on one SQLite file — would intermittently produce `database is locked` failures on otherwise-healthy requests. Services also fetch external data *before* opening the write transaction, so the SQLite write lock is held only for the local upsert, never for the round-trip to an external provider.
- **Cache-layer failures are treated as a cache miss, not a hard error.** If `CacheRepository.get_or_none()`/`.set()` itself raises (e.g. a lock-timeout that outlasts the busy-timeout retry), the calling service logs it and proceeds as if the cache were cold — attempting a live fetch — rather than letting the exception propagate as an unhandled 500. This keeps the "external failures never leak raw exceptions" guarantee intact even when the failure originates in the cache layer rather than the provider.
- **Scheduler jobs access shared resources by direct construction, not FastAPI `Depends`.** APScheduler jobs run outside any request context, so `jobs.py` cannot use route-scoped `Depends`. Services (`fmp_service.py`, `finnhub_service.py`, etc.) are plain, independently-constructible classes/functions taking their client and repository as explicit arguments; `api/dependencies.py`'s `Depends`-wrapped factories are a thin adapter over the same constructors, not the only way to build them. Lifespan teardown order is the reverse of startup: the scheduler is shut down first (waiting for any in-flight job to finish) *before* the DB engine is disposed and the HTTP clients are closed, so a mid-flight job never touches an already-closed resource during a dev-server restart.
- **Stale-but-labeled fallback on provider failure:** when FMP/EDGAR/Finnhub calls fail and a cache entry exists (even expired), the service returns the last-known value labeled with its true (past) as-of timestamp instead of a hard error. A hard error is only returned when no cached value exists at all. This maximizes dashboard availability during a provider outage while staying honest about freshness (CLAUDE.md rule 6) rather than either silently serving stale-as-fresh or going dark.
- **APScheduler `AsyncIOScheduler` started/stopped in the FastAPI lifespan**, not Celery/RQ — no broker or separate worker process needed for a single-user, single-process app. Documented single-worker constraint (`uvicorn --workers 1`): APScheduler assumes one process, and a multi-worker deployment would create N independent schedulers each refreshing the cache.
- **Advisor grounding enforced at two layers, not one:** (1) the system prompt explicitly forbids directive language and instructs context-only grounding and citation, and (2) a lightweight output-side phrase filter scans the model's response for prescriptive language ("you should", "I recommend", imperative "buy"/"sell") before it reaches the client, substituting a safe fallback message on a match. Defense-in-depth against prompt drift or an unexpected model response, since this is the single highest legal/product risk area in the app.
- **Anthropic Citations API for filing summaries**, not hand-rolled quote-checking — passing the actual filing text as a `document` content block with citations enabled is a structural mechanism for "quote the specific passage," more reliable than prompting alone for a rule with legal weight.
- **Model id lives in settings, not inline code** — `claude-sonnet-5` is today's recommended default, but model ids deprecate on a rolling schedule; hardcoding one anywhere but config would make the eventual required swap error-prone.
- **No multi-user auth, but a shared-secret bearer token gates every route (corrected during review).** The original plan treated CORS-origin restriction as the access-control layer; that's a category error — CORS governs whether a *browser* lets calling JavaScript *read* a cross-origin response, it does nothing to stop a non-browser client (curl, another local process, malware) or a "simple" cross-origin request (no preflight) from a malicious page in another tab from reaching the backend and having it *execute* (e.g. triggering `POST /portfolio/connect` or burning the Anthropic budget via `POST /advisor/chat` as a drive-by action). The actual gate is a static bearer token read from `.env` and checked by one FastAPI dependency applied to every router (U1); CORS remains as a secondary browser-side restriction, not the mechanism doing the real work. The whole model still depends on the backend binding to `127.0.0.1` only — `backend/README.md` (U10) documents this as a hard local-dev constraint, not a default that's safe to casually widen (e.g. to check the dashboard from a phone on the same network).
- **The advisor's output-side phrase filter is a lexical guard, not a semantic guarantee — this residual gap is accepted and documented, not hidden.** A keyword/phrase filter catches responses containing known directive phrases ("you should," "I recommend") but not semantically prescriptive, lexically-clean language ("this looks like an attractive entry point"). Closing that gap fully would need a second-pass semantic check (e.g. an extra classifier call asking whether the response constitutes a recommendation), which adds latency and cost to every advisor call; for MVP the lexical filter plus the system prompt is judged sufficient, with the semantic gap named explicitly here (and in Risks & Dependencies) rather than assumed away. Escalate to a semantic check if real model outputs during implementation or later use exhibit this pattern.
- **`core/logging.py` (U1) redacts secrets from every log record before emission.** CLAUDE.md hard rule 3 names logs explicitly as a place API keys must never appear, and nothing else in the plan owns this concern — a logging filter/formatter scrubs known secret fields (all provider API keys, the SnapTrade `user_secret`) and avoids logging raw request/response objects from provider SDKs or httpx, where a stringified exception could otherwise leak an `Authorization` header or similar.
- **Positions get a short cache TTL too (not just fundamentals/news).** CLAUDE.md's rate-limit rule targets fundamentals/news specifically, but routing positions through the same cache module with a short TTL (a few minutes) avoids hammering SnapTrade on rapid frontend polling, at negligible staleness cost.
- **A minimal daily snapshot-write job ships now, without the trend-comparison feature (R12).** U9 adds a lightweight `portfolio_snapshots` table (U3) and a third scheduled job that writes one row per holding per day (market value, allocation percent) with no query/comparison logic on top. This was added during review: deferring the write job along with the comparison feature (as originally scoped) would have meant the README's own headline advisor example ("up from 11% three months ago") stays unanswerable for months *after* a future follow-up plan even begins, since historical data can't be backfilled retroactively. Writing minimal snapshots now, reusing U9's existing scheduler and U3's existing repository pattern, is cheap; the comparison logic itself remains genuinely deferred.

---

## Open Questions

### Resolved During Planning

- **Real integrations vs. stubs:** real HTTP clients reading keys from `.env`, mocked at the HTTP layer in tests. (User decision, carried in from the initiating request.)
- **Database choice:** SQLite for MVP, behind a swap-friendly repository/session-factory abstraction. (User decision.)
- **Auth strategy:** no multi-user auth, but a shared-secret bearer token gates every route (revised during review — see Key Technical Decisions; CORS alone is not access control). Materially affects U1's setup, but is low-risk and reversible, so resolved here rather than deferred.
- **Portfolio snapshot *comparison*:** out of scope for this plan (see Deferred to Follow-Up Work) — but the underlying *snapshot-write* job is not deferred (R12, U9), specifically so historical data starts accumulating now.
- **Migration tooling:** `Base.metadata.create_all()` at startup, not Alembic, for this MVP's single-file/single-environment scope (revised during review — see Key Technical Decisions). Add Alembic later if a real deployment or multi-environment need arises.
- **Watchlist persistence for R4:** no server-side watchlist entity; the news endpoint takes a client-supplied `symbols` query parameter (see Scope Boundaries).

### Deferred to Implementation

- Exact SQLAlchemy model field names/types for `cache_entries`, `snaptrade_connection`, and `portfolio_snapshots` — knowable once the implementer is looking at SQLAlchemy 2.0's declarative syntax directly.
- Exact wording of the advisor system prompt and the output-filter's forbidden-phrase list — U8's approach and test scenarios constrain the *behavior* required; the implementer should iterate on exact prompt text against the test suite.
- Whether `pytest-asyncio` or `anyio`'s pytest plugin is used for async test support — both satisfy the requirement; pick whichever integrates more cleanly once respx/httpx test fixtures are actually being written.
- Precise TTL values per data type (fundamentals: likely 24h; news: likely 1-4h; positions: likely a few minutes) — implementer should pick concrete numbers in `ttl_policy.py` per the rationale already established, not re-derive the rationale.
- **Whether `connection_type="read"` is enforced by SnapTrade/the brokerage at the OAuth-consent level (a hard boundary) or is only a request-shape hint** — verify against SnapTrade's platform documentation (or a live sandbox test) during U4; if it turns out to be a soft boundary only, surface that explicitly rather than continuing to describe the integration as "read-only by construction" on the strength of the code-level import restriction alone.

---

## Output Structure

    backend/
      pyproject.toml
      .env.example
      .gitignore
      README.md
      app/
        __init__.py
        main.py
        core/
          __init__.py
          config.py
          logging.py
        api/
          __init__.py
          dependencies.py
          routers/
            __init__.py
            health.py
            portfolio.py
            fundamentals.py
            filings.py
            news.py
            advisor.py
        schemas/
          __init__.py
          common.py
          portfolio.py
          fundamentals.py
          filings.py
          news.py
          advisor.py
        domain/
          __init__.py
          types.py
          allocation.py
          concentration.py
          pnl.py
        services/
          __init__.py
          snaptrade_service.py
          fmp_service.py
          edgar_service.py
          finnhub_service.py
          claude_service.py
        cache/
          __init__.py
          cache_repository.py
          ttl_policy.py
        db/
          __init__.py
          session.py
          models.py
        scheduler/
          __init__.py
          jobs.py
      tests/
        conftest.py
        domain/
          test_allocation.py
          test_concentration.py
          test_pnl.py
        cache/
          test_cache_repository.py
        services/
          test_snaptrade_service.py
          test_fmp_service.py
          test_edgar_service.py
          test_finnhub_service.py
          test_claude_service.py
        api/
          test_portfolio_routes.py
          test_fundamentals_routes.py
          test_filings_routes.py
          test_news_routes.py
          test_advisor_routes.py
        scheduler/
          test_jobs.py
        fixtures/
          synthetic_positions.py
          synthetic_filing.py
          synthetic_news.py

---

## Implementation Units

### U1. Project scaffolding, tooling, and app skeleton

**Goal:** A running, empty-but-typed FastAPI app with config, logging, CORS, and a health check — the foundation every later unit builds on.

**Requirements:** R6, R11

**Dependencies:** None

**Files:**
- Create: `backend/pyproject.toml`, `backend/.env.example`, `backend/.gitignore`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/core/__init__.py`, `backend/app/core/config.py`, `backend/app/core/logging.py`, `backend/app/api/__init__.py`, `backend/app/api/dependencies.py`, `backend/app/api/routers/__init__.py`, `backend/app/api/routers/health.py`
- Test: `backend/tests/conftest.py`, `backend/tests/api/test_health_route.py`

**Approach:**
- `pyproject.toml` declares Python 3.12+, FastAPI 0.140.x, Pydantic >=2.7, and dev deps (`pytest`, `pytest-asyncio` or `anyio`, `respx`, `ruff`, `mypy`); `[tool.mypy]` uses `strict = true` plus `warn_unreachable = true` and the `pydantic.mypy` plugin; `[tool.ruff]` targets `py312` and selects `E,W,F,I,UP,B,N,ANN,S,SIM,RUF,FAST,PT`.
- `core/config.py` is a `pydantic-settings` `BaseSettings` reading all API keys/URLs/DB URL/CORS origins/the shared API bearer token from environment variables, with required fields having no default (fail loudly at startup if missing) and non-secret fields (TTLs, model id) having sensible defaults.
- `.env.example` lists every variable `config.py` reads, with placeholder values and a comment per hard rule 5 — never real keys.
- `.gitignore` explicitly excludes the local SQLite DB file(s) (e.g. `*.db`, `*.sqlite3`) and `.env` — this is the one control the plan's deferred-encryption decision for the SnapTrade `user_secret` and cached positions/balances (Scope Boundaries) actually depends on, so it's load-bearing, not boilerplate.
- `api/dependencies.py` defines a `require_api_token` dependency (checks a bearer token header against the configured shared secret, raises 401 on mismatch/absence) applied at the app or router level to every route except `/health` and `/docs`. This is the actual access-control gate (Key Technical Decisions) — CORS is a secondary, browser-side restriction, not a substitute for it.
- `core/logging.py` installs a logging filter/formatter that redacts known secret fields (every provider API key, the shared bearer token, and — once U4 exists — the SnapTrade `user_secret`) from any log record before emission, and avoids logging raw request/response objects from provider SDKs or httpx (Key Technical Decisions; CLAUDE.md hard rule 3 names logs explicitly).
- `app/main.py` builds the FastAPI app via an app-factory function, registers CORS middleware restricted to configured frontend origin(s), applies `require_api_token` globally, and wires an (initially empty) `lifespan` context manager that later units extend.
- `health.py` router exposes `GET /health` returning a simple status payload, exempt from the bearer-token check — used later as the handoff smoke check and as an unauthenticated liveness probe.

**Patterns to follow:**
- FastAPI's own "Bigger Applications" router-splitting pattern; lifespan-based startup/shutdown (not the deprecated `@app.on_event`).

**Test scenarios:**
- Happy path: with all required env vars set (via a test `.env` or monkeypatched environment), `Settings()` loads and every field has the expected type.
- Error path: a required env var (e.g. an API key) missing raises a clear validation error at settings-construction time, not a later `NoneType` failure deep in a service.
- Integration: `GET /health` via `TestClient` returns 200 with the app fully constructed (lifespan runs) using only placeholder env values, and without a bearer token — proves the app boots without needing real external credentials and that the liveness probe stays unauthenticated.
- Happy path: a request to a protected route with the correct bearer token succeeds; edge: a request with a missing or incorrect token returns 401.
- Edge: CORS preflight (`OPTIONS`) from the configured frontend origin succeeds; a request from an unconfigured origin is rejected.
- Edge: logging a caught exception that embeds a fake secret value (e.g. an API key in a mocked error message) produces a log record with the secret redacted, not the literal value.

**Verification:**
- `uvicorn app.main:app` starts cleanly with placeholder `.env` values.
- `ruff check` and `mypy` run clean on the (currently minimal) codebase.
- Creating the dev SQLite DB file and running `git status` shows it untracked (`.gitignore` is actually excluding it, not just declaring intent to).
- A request to any non-`/health`, non-`/docs` route without the bearer token is rejected with 401.

---

### U2. Domain module — portfolio math

**Goal:** Pure, I/O-free functions for allocation, concentration, and P&L that every downstream consumer (portfolio endpoint, advisor context) shares.

**Requirements:** R1, R10

**Dependencies:** U1

**Files:**
- Create: `backend/app/domain/__init__.py`, `backend/app/domain/types.py`, `backend/app/domain/allocation.py`, `backend/app/domain/concentration.py`, `backend/app/domain/pnl.py`
- Test: `backend/tests/domain/test_allocation.py`, `backend/tests/domain/test_concentration.py`, `backend/tests/domain/test_pnl.py`

**Approach:**
- `types.py` defines a plain typed `Holding` (symbol, quantity, cost_basis, current_price, market_value) decoupled from any provider's schema — `services/snaptrade_service.py` (U4) maps SnapTrade's response shape into this type, not the other way around. This keeps domain logic testable with synthetic fixtures and reusable by both the portfolio endpoint and the advisor's context assembly (U8).
- `allocation.py`: given a list of `Holding`, returns each holding's percentage of total portfolio market value.
- `concentration.py`: given allocations and a configurable threshold, flags holdings above it; also returns a top-N by weight summary.
- `pnl.py`: given a `Holding`, returns unrealized gain/loss in both dollars and percent.
- No function performs any I/O, network call, or DB access — inputs and outputs are plain typed values only.

**Execution note:** Implement test-first — write the synthetic-fixture test cases for each function's expected output before implementing the calculation. This module is pure and low-risk to iterate on test-first, and CLAUDE.md calls it out as needing to "approach full coverage" since bugs here mean wrong numbers shown to a user.

**Patterns to follow:** None yet in-repo; this is the first code written. Keep functions small, typed, and free of any framework import (no FastAPI, no Pydantic required here — plain dataclasses or NamedTuples are enough).

**Test scenarios:**
- Happy path: three holdings with known market values → allocation percentages sum to 100% (within floating-point tolerance).
- Edge: single-holding portfolio → 100% allocation; empty holdings list → empty result, not a divide-by-zero.
- Happy path: concentration flags holdings above a threshold (e.g. >20%) and returns none flagged when all holdings are under it.
- Happy path: top-N by weight returns holdings in descending weight order.
- Error path: zero or negative total portfolio value (a data anomaly, not a legitimate empty-portfolio case) raises a domain-level error rather than producing `NaN`/`inf`.
- Happy path: P&L returns correctly-signed gain and loss in both dollars and percent for a gaining and a losing position.
- Edge: cost basis of zero (a real brokerage data-quality case) is handled with documented, explicit behavior (e.g. percent P&L is `None`/undefined rather than a divide-by-zero crash).

**Verification:**
- `pytest backend/tests/domain/` passes with no I/O of any kind occurring (no mocks needed — pure functions).
- Coverage on `app/domain/` is at or near 100% per CLAUDE.md's expectation for money-math code.

---

### U3. Data layer and caching module

**Goal:** A SQLite-backed, swap-friendly persistence layer and a single generic cache module with explicit per-data-type TTLs.

**Requirements:** R2, R4, R9, R12

**Dependencies:** U1

**Files:**
- Create: `backend/app/db/__init__.py`, `backend/app/db/session.py`, `backend/app/db/models.py`, `backend/app/cache/__init__.py`, `backend/app/cache/cache_repository.py`, `backend/app/cache/ttl_policy.py`
- Test: `backend/tests/cache/test_cache_repository.py`

**Approach:**
- `db/session.py`: `create_async_engine(settings.database_url)` + `async_sessionmaker(engine, expire_on_commit=False)`; a `Depends`-with-`yield` dependency (`get_session`) opens/closes a session per call. This file is the *only* place a connection string or dialect is known. For the SQLite driver specifically, sets WAL journal mode and a multi-second busy-timeout PRAGMA at connection/engine creation (Key Technical Decisions) — these are SQLite-only settings and must not leak outside this file, the same swap-friendliness constraint the rest of the module already follows. Calls `Base.metadata.create_all()` against the engine during lifespan startup (not Alembic — Key Technical Decisions) so all tables exist on first run.
- `db/models.py`: SQLAlchemy 2.0 declarative models for `cache_entries` (`provider`, `cache_key`, `payload_json`, `fetched_at`, `ttl_seconds`; unique on `(provider, cache_key)`) and `portfolio_snapshots` (`snapshot_date`, `symbol`, `market_value`, `allocation_pct`; R12 — written by U9, not queried/compared by anything in this plan).
- `cache/cache_repository.py`: `CacheRepository(session)` with `get_or_none(provider, key) -> CacheEntry | None` (returns `None` if `fetched_at + ttl_seconds` has elapsed, using an injectable clock so tests don't depend on real time) and `set(provider, key, payload, ttl_seconds)`, implemented as a single atomic `INSERT ... ON CONFLICT(provider, cache_key) DO UPDATE` statement rather than a check-then-insert-or-update round trip, so two near-simultaneous writers targeting the same key can't both observe "no row" and both attempt an insert (Key Technical Decisions). Also exposes a variant that returns an expired entry explicitly when the caller wants stale-fallback (per the Key Technical Decision), so services can distinguish "nothing cached" from "cached but expired." Callers (U5/U6/U7/U9) are expected to complete their external fetch *before* calling `.set()`, so the write transaction only ever wraps the local upsert, never a network round trip.
- `cache/ttl_policy.py`: named constants per data type (e.g. `FUNDAMENTALS_TTL_SECONDS`, `NEWS_TTL_SECONDS`, `POSITIONS_TTL_SECONDS`) — the single place TTL policy is readable and changeable.
- No route, service, or domain module imports SQLAlchemy or writes raw SQL directly — everything goes through `db/` and the repositories.

**Patterns to follow:** Repository pattern over SQLAlchemy Core/ORM (cosmicpython-style) — abstract interface implied by the repository class's public methods, concrete implementation is the only thing touching `AsyncSession`.

**Test scenarios:**
- Happy path: `set()` then `get_or_none()` immediately after returns the payload before TTL expiry.
- Edge: `get_or_none()` returns `None` once the injectable clock advances past `fetched_at + ttl_seconds`.
- Edge: `get_or_none()` returns `None` for a cache key that was never written (cold miss), distinct from an expired entry.
- Integration: starting the app against a fresh (nonexistent) SQLite file auto-creates both `cache_entries` and `portfolio_snapshots`; starting again against the now-existing file is a no-op (no error, no duplicate tables).
- Integration: two concurrent `set()` calls for the same `(provider, cache_key)` (simulated via concurrent async tasks against the same temp DB) both complete without an integrity error; the row reflects whichever write committed last, which is acceptable per the Key Technical Decision on atomic upsert (last-write-wins on near-simultaneous writes is cosmetic staleness, not corruption).
- Error path: attempting to `set()` a non-JSON-serializable payload raises a clear error rather than writing a corrupt row.

**Verification:**
- A fresh SQLite file, once the app starts, has both a working `cache_entries` and `portfolio_snapshots` table.
- `pytest backend/tests/cache/` passes against a temp SQLite DB (not the dev DB file).
- WAL mode is confirmed active on the SQLite connection (e.g. `PRAGMA journal_mode` reports `wal`).

---

### U4. SnapTrade integration and portfolio endpoints

**Goal:** Read-only brokerage connection and holdings sync, exposed as typed, provenance-labeled portfolio endpoints built on U2's domain math.

**Requirements:** R1, R6, R7, R8

**Dependencies:** U1, U2, U3

**Files:**
- Create: `backend/app/services/snaptrade_service.py`, `backend/app/schemas/common.py`, `backend/app/schemas/portfolio.py`, `backend/app/api/routers/portfolio.py`
- Modify: `backend/app/db/models.py` (add a `snaptrade_connection` table: `user_id`, `user_secret`, `connected_at`, unique on `user_id`), `backend/app/api/dependencies.py` (add `get_snaptrade_client`), `backend/app/main.py` (register the portfolio router; construct the shared async SnapTrade SDK client in lifespan)
- Test: `backend/tests/services/test_snaptrade_service.py`, `backend/tests/api/test_portfolio_routes.py`, `backend/tests/fixtures/synthetic_positions.py`

**Approach:**
- `schemas/common.py` defines a shared `SourcedValue`/`ProvenanceMeta` pattern (source name + as-of timestamp) reused by every response schema across the app (R7).
- `snaptrade_service.py`: `connect()` — if no `snaptrade_connection` row exists, calls `aregister_snap_trade_user` once and persists the returned `user_secret`; if one exists, skips re-registration. `snaptrade_connection` is a singleton/unique-constrained table (Key Technical Decisions), so if two `connect()` calls race and both attempt to register, the losing insert hits the uniqueness conflict and the service catches it, re-reads the row the winner persisted, and proceeds as "already connected" rather than surfacing a raw integrity error or leaving an orphaned remote SnapTrade registration. Always calls `alogin_snap_trade_user(..., connection_type="read")` to produce a connection portal URL. `list_positions()` / `list_balances()` call the account-scoped endpoints only (`list_user_accounts` → `get_all_account_positions` / `get_user_account_balance` — the unified positions endpoint, not the older `get_user_account_positions`, which itself carries a separate deprecation notice per Context & Research) using the SDK's native `a`-prefixed async methods, and map the response into U2's `Holding` type (Key Technical Decisions — no `run_in_threadpool` wrapping needed).
- If `list_positions()`/`list_balances()` are called before `connect()` has ever succeeded (no `snaptrade_connection` row exists), the service returns a distinct "not connected yet" result rather than treating it as a provider error — the router surfaces this as a typed 409-style response so the frontend can distinguish "nothing to show yet, prompt the user to connect" from "SnapTrade is down." U9's scheduled refresh job (see U9) checks for this same state and skips its run entirely rather than iterating zero holdings.
- Positions/balances are routed through U3's cache module with a short TTL (a few minutes) to avoid hammering SnapTrade on rapid frontend polling, using the stale-fallback behavior from Key Technical Decisions on a SnapTrade error.
- `portfolio.py` router: `POST /portfolio/connect` (returns portal URL), `GET /portfolio/accounts`, `GET /portfolio/positions` (mapped holdings + computed allocation/concentration/P&L from U2, each value carrying `SourcedValue` provenance).
- The service module never imports SnapTrade's trading/orders SDK namespace — this is a static property to check in review, not something a runtime test can prove.

**Patterns to follow:** U2's `Holding` type as the mapping target; U3's `CacheRepository` for the short-TTL positions cache; U1's provenance/config/bearer-token conventions.

**Test scenarios:**
- Happy path: first-time `connect()` registers once (mocked SnapTrade SDK) and persists `user_secret`; a second `connect()` call does not re-register, reusing the persisted secret.
- Happy path: `GET /portfolio/positions` returns mapped `Holding`-derived data with source="SnapTrade" and an as-of timestamp, built from a mocked account+positions response using `get_all_account_positions`.
- Edge: cache hit within the positions TTL does not trigger a second mocked SnapTrade call.
- Edge: two concurrent `connect()` calls against an empty `snaptrade_connection` table (simulated via concurrent async tasks) result in exactly one registration call to the mocked SnapTrade SDK and both callers ending up with the same persisted `user_secret` — no unhandled integrity error, no orphaned registration.
- Edge: `GET /portfolio/positions` called with no `snaptrade_connection` row yet returns a typed 409-style "not connected" response, not a 502 or a crash.
- Error path: a mocked SnapTrade API error/timeout on `list_positions()` (after a successful connection) returns a typed 502-style error response when no cached value exists; falls back to the last cached value (labeled with its true as-of time) when one does.
- Integration: every SnapTrade call in the service uses the SDK's `a`-prefixed async methods, never the sync ones (verified against the pattern in review; the SDK is mocked at its own boundary in tests, not via `respx`/httpx, since it isn't httpx-based).

**Verification:**
- Code review confirms `snaptrade_service.py` imports only the authentication and account-information SDK namespaces — never orders/trading — and only the async (`a`-prefixed) methods.
- `GET /portfolio/positions` in a `TestClient` smoke test returns allocation/concentration/P&L consistent with U2's own unit-tested output for the same synthetic holdings.

---

### U5. FMP integration and fundamentals endpoint

**Goal:** Cached fundamental ratios per holding, respecting FMP's 250-req/day free tier.

**Requirements:** R2, R6, R7

**Dependencies:** U1, U3

**Files:**
- Create: `backend/app/services/fmp_service.py`, `backend/app/schemas/fundamentals.py`, `backend/app/api/routers/fundamentals.py`
- Modify: `backend/app/api/dependencies.py` (add `get_fmp_client`), `backend/app/main.py` (register router; construct the shared `httpx.AsyncClient` for FMP in lifespan)
- Test: `backend/tests/services/test_fmp_service.py`, `backend/tests/api/test_fundamentals_routes.py`

**Approach:**
- `fmp_service.py` calls `/stable/ratios` and `/stable/key-metrics-ttm` via the shared `httpx.AsyncClient`, parses responses into Pydantic models immediately, and reads through `CacheRepository` (provider="fmp", key=symbol) with `FUNDAMENTALS_TTL_SECONDS` (U3). On a cache miss, fetches live and writes the cache; on a provider error with an existing (possibly expired) cache entry, returns the stale value labeled with its true as-of time per the Key Technical Decision.
- `fundamentals.py` router exposes `GET /fundamentals/{symbol}` returning ratios/key metrics each tagged with `SourcedValue` provenance (U4's shared schema).

**Patterns to follow:** U4's shared `httpx.AsyncClient`-in-lifespan pattern; U3's cache repository and stale-fallback behavior; U4's `SourcedValue` schema.

**Test scenarios:**
- Happy path: `GET /fundamentals/{symbol}` returns ratios with source="FMP" and an as-of timestamp, using a mocked `/stable/ratios` + `/stable/key-metrics-ttm` response via `respx`.
- Edge: a second call within the TTL does not trigger a second mocked HTTP call (`respx` call-count assertion of 1).
- Error path: FMP returns 429/5xx with no cached value → typed error response; with a cached (possibly expired) value → stale value returned, labeled with its true as-of timestamp.
- Edge: an unknown/invalid symbol returns a clear 4xx, not an unhandled parse error.

**Verification:**
- `pytest backend/tests/services/test_fmp_service.py backend/tests/api/test_fundamentals_routes.py` passes with zero live network calls (enforced by `respx`).

---

### U6. SEC EDGAR integration and filings endpoint

**Goal:** Fetch authoritative filing metadata and full text, ready for the advisor's citation-grounded summarization in U8.

**Requirements:** R3, R7

**Dependencies:** U1, U3

**Files:**
- Create: `backend/app/services/edgar_service.py`, `backend/app/schemas/filings.py`, `backend/app/api/routers/filings.py`
- Modify: `backend/app/api/dependencies.py` (add `get_edgar_client`), `backend/app/main.py` (register router; construct the shared `httpx.AsyncClient` for EDGAR with the required `User-Agent` header set at construction)
- Test: `backend/tests/services/test_edgar_service.py`, `backend/tests/api/test_filings_routes.py`, `backend/tests/fixtures/synthetic_filing.py`

**Approach:**
- The EDGAR `httpx.AsyncClient` is constructed once in lifespan with a descriptive `User-Agent` header (app name + a contact email from settings) baked in at the client level, so every request carries it without per-call boilerplate — directly satisfies SEC's access requirement.
- `edgar_service.py`: resolves ticker → CIK (via SEC's ticker mapping), fetches `submissions/CIK##########.json` to list recent 10-K/10-Q/8-K filings, and fetches a specific filing document's raw text/HTML by URL. Responses are cached via U3 (`provider="edgar"`) since filing lists/text don't change once published.
- `filings.py` router: `GET /filings/{symbol}` (recent filings list) and `GET /filings/{symbol}/{accession_number}` (filing text) — the latter is what U8 consumes for citation-grounded summarization, not summarized here (this unit only fetches; Claude does the summarizing).

**Patterns to follow:** U5's cache-through-service pattern and stale-fallback; U4's `SourcedValue` schema.

**Test scenarios:**
- Happy path: fetching a company's filing history (mocked CIK lookup + submissions response) returns a list of recent 10-K/10-Q/8-K filings with metadata.
- Happy path: fetching a specific filing's text (mocked response) returns raw text ready for downstream summarization.
- Edge: a ticker not found in the SEC ticker→CIK mapping returns a typed 404-style domain error, not a crash.
- Integration: every outgoing EDGAR request carries the descriptive `User-Agent` header (asserted via `respx` request-matching).
- Error path: EDGAR returns 403/429 → typed error with no cache, or stale-labeled fallback with a cache entry.

**Verification:**
- `pytest backend/tests/services/test_edgar_service.py backend/tests/api/test_filings_routes.py` passes with zero live network calls; the `User-Agent` assertion specifically passes.

---

### U7. Finnhub integration and news endpoint

**Goal:** Cached, holdings-filtered news, respecting Finnhub's 60-calls/min free tier.

**Requirements:** R4, R7

**Dependencies:** U1, U3

**Files:**
- Create: `backend/app/services/finnhub_service.py`, `backend/app/schemas/news.py`, `backend/app/api/routers/news.py`
- Modify: `backend/app/api/dependencies.py` (add `get_finnhub_client`), `backend/app/main.py` (register router; construct the shared `httpx.AsyncClient` for Finnhub in lifespan)
- Test: `backend/tests/services/test_finnhub_service.py`, `backend/tests/api/test_news_routes.py`, `backend/tests/fixtures/synthetic_news.py`

**Approach:**
- `finnhub_service.py` calls `company-news` per symbol via the shared client, reads through U3's cache (`provider="finnhub"`, `NEWS_TTL_SECONDS`), and applies the same stale-fallback behavior on provider failure.
- `news.py` router: `GET /news?symbols=...` filters results to the requested holdings/watchlist symbols and returns each item tagged with `SourcedValue` provenance.

**Patterns to follow:** U5's and U6's cache-through-service and stale-fallback pattern.

**Test scenarios:**
- Happy path: `GET /news?symbols=...` returns cached-or-fresh items for the requested symbols, each with source="Finnhub" and an as-of timestamp.
- Edge: a call within the TTL does not trigger a second mocked HTTP call.
- Edge: no news found for a symbol/date range returns an empty list, not an error.
- Error path: a mocked Finnhub rate-limit/error response triggers the stale-fallback or typed-error behavior per the Key Technical Decision.

**Verification:**
- `pytest backend/tests/services/test_finnhub_service.py backend/tests/api/test_news_routes.py` passes with zero live network calls.

---

### U8. Claude advisor service and endpoints

**Goal:** A grounded, cited, never-directive AI advisor — the highest-risk unit in the plan, both legally and in terms of trust.

**Requirements:** R5, R6, R7

**Dependencies:** U1, U2, U4, U5, U6, U7

**Files:**
- Create: `backend/app/services/claude_service.py`, `backend/app/schemas/advisor.py`, `backend/app/api/routers/advisor.py`
- Modify: `backend/app/api/dependencies.py` (add `get_claude_client`), `backend/app/main.py` (register router; construct the shared Anthropic client in lifespan)
- Test: `backend/tests/services/test_claude_service.py`, `backend/tests/api/test_advisor_routes.py`

**Approach:**
- `claude_service.py` builds every request from explicitly-assembled context: current holdings + computed allocation/concentration/P&L (reusing U2's domain functions directly, not reimplementing them), specific cached fundamentals (U5), specific filing text (U6) for summarization requests, and specific news items (U7) — never free-form "the user owns X" text without the backing data attached.
- System prompt (a single versioned constant) explicitly: (a) forbids "buy"/"sell"/"you should"/allocation-directive language, (b) instructs the model to use only facts present in the provided context and say so when something isn't covered rather than inferring it, (c) instructs citing which context item every claim is drawn from, quoting the specific line for filing-derived claims, and (d) instructs reframing "what should I do" questions into "here's what's relevant" answers.
- Filing summarization specifically uses the Anthropic Citations API — the filing text (U6) is passed as a `document` content block with `citations: {"enabled": true}`, and the response's citation blocks are surfaced in the API response schema alongside the summary text, linking back to the source filing.
- **Output-side guard:** before returning any advisor response to the client, scan it for a documented list of forbidden directive phrases/patterns; on a match, log it and substitute a safe fallback message instead of forwarding the raw model output. This is defense-in-depth alongside the system prompt, not a replacement for it. It is a lexical guard, not a semantic one (Key Technical Decisions) — the residual gap (prescriptive meaning without a flagged phrase) is an accepted, documented MVP limitation, not something this unit claims to fully close.
- Model id (`claude-sonnet-5` by default) is read from settings, not hardcoded in `claude_service.py`.

**Execution note:** Write the reframe/grounding test fixtures — a table of directive-phrased questions and the forbidden-phrase list the output filter checks — before implementing the system prompt and the filter, so both are built against concrete, agreed cases rather than assumed correct. This is the path CLAUDE.md calls out to "implement and test... deliberately."

**Technical design:**
> This illustrates the intended request/response shape and is directional guidance for review, not implementation specification.
>
> ```
> POST /advisor/chat
>   { question: str, context_refs: { symbols: [...], filing_ref: optional } }
>   → service assembles context bundle (Holding[], fundamentals, filing text, news)
>   → system prompt (grounding + no-directive rules) + user turn (question + context block)
>   → Claude Messages API call
>   → output-side forbidden-phrase filter
>   → AdvisorResponse { answer: str, citations: [{source, quote, as_of}] }
> ```

**Patterns to follow:** U2's domain functions for any portfolio math referenced in advisor answers (parity with what the dashboard itself shows); U4/U5/U6/U7's `SourcedValue` provenance pattern for citations.

**Test scenarios:**
- Happy path: given a mocked context bundle and a neutral question, the response is built only from the injected context (assert the constructed Claude request's context block contains exactly the injected data, via a mocked Anthropic client).
- Happy path (Covers R5): filing summarization returns a summary with citation blocks referencing the source filing (mocked Citations API response), and the response schema includes the source filing reference and quoted passage.
- Error/reframe path (Covers R5 — the core legal-boundary behavior): a table-driven test over several directive-phrased inputs ("Should I sell NVDA?", "Should I buy more?", "Is now a good time to add to this position?", "What would you do here?") asserts (a) the system prompt sent to the mocked Claude client contains the no-directive-advice instruction, and (b) if a mocked model response contains forbidden directive language, the output-side filter catches it and substitutes the safe fallback rather than forwarding it.
- Error path: a mocked Claude API failure/timeout returns a typed "advisor unavailable" error, never a partial or garbled response that could read as advice.
- Edge: a filing-summarization request with no available filing text for the requested symbol returns a clear 4xx explaining insufficient context, rather than letting the model fill the gap from training knowledge.
- Integration: advisor context assembly for portfolio-related questions invokes U2's allocation/concentration functions directly (asserted via mocking those functions), so the advisor's numbers can never drift from what the dashboard itself computes.
- Edge (documents a known limitation, doesn't need to pass a fix): a mocked filing/news context item itself contains injected directive-style text (e.g. a news headline reading "consider adding to this position now") — the test demonstrates whether the output filter catches prescriptive language that originates from ingested third-party content, not just from the model's own free response, since externally-authored text entering the advisor's context window is a distinct trust boundary from the user's own question.

**Verification:**
- The full directive-question test table passes.
- Code review confirms the system prompt text matches CLAUDE.md's four required elements verbatim in spirit (forbid directive language, context-only grounding, citation instruction, graceful reframe).

---

### U9. Scheduled cache refresh and daily snapshot

**Goal:** Fundamentals and news are refreshed on a schedule, never fetched fresh per request, per the rate-limit hard rule; a minimal daily portfolio snapshot begins accumulating history now (R12).

**Requirements:** R2, R4, R12

**Dependencies:** U3, U4, U5, U7

**Files:**
- Create: `backend/app/scheduler/__init__.py`, `backend/app/scheduler/jobs.py`
- Modify: `backend/app/main.py` (start/stop `AsyncIOScheduler` in lifespan, register jobs)
- Test: `backend/tests/scheduler/test_jobs.py`

**Approach:**
- `jobs.py` defines a fundamentals-refresh job (iterates current holdings from U4, calls U5's fetch-and-cache path per symbol), a news-refresh job (same, via U7), and a daily snapshot job (iterates current holdings, writes one `portfolio_snapshots` row per holding via U3's repository — symbol, market value, allocation percent from U2's own allocation function, no comparison/query logic), each registered with an explicit interval trigger (daily for fundamentals and the snapshot, every few hours for news) — the schedule itself is the human-readable TTL policy. Jobs construct their service/repository instances directly from the same constructor functions `api/dependencies.py`'s `Depends` factories wrap (Key Technical Decisions), since a scheduler job has no request context to inject through.
- The snapshot job checks for the "not connected yet" state (U4) and skips its run entirely if no SnapTrade connection exists yet, rather than writing an empty/meaningless snapshot.
- One symbol's failure during a batch refresh is caught and logged; the job continues to the next symbol rather than aborting the whole run (partial-failure isolation).
- `main.py`'s lifespan starts the scheduler after the DB/HTTP clients are ready. Teardown is the reverse: the scheduler is shut down first — waiting for any in-flight job to finish — *before* the DB engine is disposed and the HTTP clients are closed, so a mid-flight refresh job never touches an already-closed resource during a dev-server restart (Key Technical Decisions). A code comment and the backend README both note the single-worker requirement (`uvicorn --workers 1`) since APScheduler assumes one process.

**Patterns to follow:** U5/U7's cache-write path, invoked directly rather than through the HTTP layer; U2's allocation function for the snapshot's allocation-percent field.

**Test scenarios:**
- Happy path: on lifespan startup, the scheduler has the expected jobs registered (fundamentals, news, snapshot) with the expected trigger intervals (asserted against the scheduler's job store, not by waiting for real time to pass).
- Integration: manually invoking the fundamentals-refresh job (mocked HTTP, real temp DB) iterates mocked current holdings and writes/updates one cache entry per symbol via U3's repository.
- Happy path: manually invoking the snapshot job (mocked holdings, real temp DB) writes one `portfolio_snapshots` row per holding with the correct symbol/market-value/allocation-percent.
- Edge: invoking the snapshot job with no SnapTrade connection yet skips the run and writes no rows, rather than erroring or writing an empty snapshot.
- Error path: one symbol's refresh fails (mocked provider error) — the job logs and continues to the remaining symbols rather than aborting the batch.
- Edge: the scheduler shuts down cleanly on lifespan teardown with no dangling jobs after the test app context exits, and shutdown happens before the DB engine/HTTP clients are torn down (asserted via call-order, not timing).

**Verification:**
- `pytest backend/tests/scheduler/` passes; manually triggering a refresh job against mocked providers populates the cache as expected; manually triggering the snapshot job populates `portfolio_snapshots` as expected.
- Restarting the dev server (`Ctrl+C` then rerun) produces no "attempted to use a closed resource" errors from an in-flight job.

---

### U10. Handoff readiness

**Goal:** Prove, end-to-end, that the backend is ready for a frontend session to build against — this unit's verification criteria *are* the plan's definition of done.

**Requirements:** R11

**Dependencies:** U1–U9

**Files:**
- Create: `backend/README.md`
- Modify: `backend/app/main.py` (final CORS/OpenAPI metadata pass — title, description, version)
- Test: `backend/tests/api/test_smoke.py`

**Approach:**
- `backend/README.md` documents: installing dependencies, copying `.env.example` to `.env` and where to get each real API key (including generating a value for the shared bearer token), running the dev server (tables auto-create on first run — no separate migration step), the single-worker note from U9, the hard `127.0.0.1`-only binding constraint the access-control model depends on (Key Technical Decisions), and running the test suite — written so a new session/person can go from a clean checkout to a running backend without reading source first.
- `test_smoke.py` is an end-to-end `TestClient` pass (all externals mocked) hitting `/health` (no token needed), `/docs` (OpenAPI schema), and one representative route from each router (portfolio, fundamentals, filings, news, advisor) with the bearer token supplied, asserting 200s and response shapes matching their Pydantic schemas — this is the concrete proof the whole app wires together, not just its parts in isolation.

**Test scenarios:**
- Test expectation: none beyond the smoke suite below — this unit is integration/documentation, not new behavior.
- Integration: the full smoke suite (`/health`, `/docs`, one route per router with the bearer token) passes against a fully-wired `TestClient` app with every external mocked.
- Edge: the same smoke routes (excluding `/health`/`/docs`) return 401 when called without the bearer token, confirming the access-control gate from U1 is actually wired into every router, not just the one it was written against.
- Edge: CORS preflight from the configured frontend origin succeeds in the smoke suite; a non-configured origin is rejected.

**Verification:**
- `uvicorn app.main:app --workers 1` boots cleanly from a clean checkout following only `backend/README.md`, using placeholder `.env` values.
- `GET /docs` renders and lists every endpoint (portfolio, fundamentals, filings, news, advisor, health) with typed request/response schemas visible.
- `pytest`, `ruff check`, and `mypy` all pass clean across the whole `backend/` tree.
- A frontend session could read `backend/README.md` plus `/docs` and start building against the API without needing to read backend source.

---

## System-Wide Impact

- **Interaction graph:** the FastAPI lifespan wires up every shared resource (DB engine, four provider clients including Anthropic, the APScheduler instance) that every router depends on via `Depends`. The scheduler is a second, structurally different consumer of the same resources — it reaches them by direct construction (Key Technical Decisions), not through `Depends` — so a future change to a dependency factory could silently stop covering the scheduler's copy unless both paths are updated together. A bug in lifespan startup breaks every route, not just one — U1 and U10 both need to verify the full app still boots after each later unit adds to lifespan.
- **Error propagation:** external API failures (SnapTrade/FMP/EDGAR/Finnhub) surface as typed HTTP error responses via the stale-fallback-or-typed-error pattern (Key Technical Decisions), never raw exceptions/stack traces. Cache-layer failures (e.g. a lock-timeout from concurrent SQLite writers) are treated as a cache miss and fall through to a live fetch, not an unhandled 500 (Key Technical Decisions). Claude failures during advisor chat return a typed "advisor unavailable" response — silently falling back to an ungrounded answer is explicitly disallowed by CLAUDE.md.
- **State lifecycle risks:** `register_snap_trade_user` must only ever run once per local user, enforced by treating `snaptrade_connection` as a singleton row rather than relying solely on a check-then-act guard (U4, Key Technical Decisions); a scheduled refresh job (U9) failing mid-batch must not leave a partially-written cache row (U3's `set()` is a single atomic upsert statement per symbol, so partial failure only affects that symbol, not the whole cache table). **Concurrency risk:** request-serving code and the in-process scheduler both write to `cache_entries` on one SQLite file — without WAL mode and a busy-timeout (Key Technical Decisions), this produces intermittent `database is locked` failures on otherwise-healthy requests; this risk touches every route that reads or writes the cache, not just U9.
- **Access control:** every router sits behind the shared-secret bearer-token check from U1 (Key Technical Decisions), applied once at the app level rather than per-route, so adding a new router in a later unit doesn't require remembering to wire access control into it individually — only `/health` and `/docs` are explicitly exempted. CORS remains a secondary, browser-only restriction on top of this, not the access-control layer itself.
- **API surface parity:** the advisor (U8) computes portfolio math via the exact same domain functions (U2) as the portfolio endpoint (U4), so the dashboard and the advisor can never disagree about a holding's allocation or P&L.
- **Data exposure surface:** the SnapTrade `user_secret`, cached positions, and cached balances all share the same at-rest protection level (a gitignored local SQLite file, per U1's verification step) — encryption-at-rest is deferred for all three together (Scope Boundaries), not just the credential, since a local compromise exposes real holdings data alongside the connection secret.
- **Integration coverage:** beyond the per-unit tests, at least one test should exercise SnapTrade service → domain mapping → allocation calculation → portfolio route end-to-end (U4), one should exercise cache-miss → fetch → cache-write → second-call cache-hit with no second HTTP call (U5/U6/U7), one should exercise the bearer-token gate across a representative route from every router (U10), one should exercise externally-authored content (a filing excerpt or news item) reaching the advisor's context and confirm the output filter's behavior against it (U8), and U10's smoke suite exercises the full app assembly.
- **Unchanged invariants:** none — this is a greenfield build with nothing pre-existing to preserve.

---

## Alternative Approaches Considered

- **Redis for caching** instead of a SQLite-backed cache table: rejected — adds an external service dependency for what's currently a single-user, single-machine app. SQLite keeps the whole backend self-contained, consistent with CLAUDE.md's "not premature multi-tenant scale."
- **Celery/RQ for scheduled refresh** instead of in-process APScheduler: rejected — requires a message broker and a separate worker process, which is over-engineering for a single-user, single-process MVP. APScheduler runs in-process with zero added infrastructure.
- **Prompt-only citation checking** instead of Anthropic's Citations API for filing summaries: considered as a fallback if the Citations API proved unavailable or insufficient, but the Citations API is a structural mechanism (not just prompt wording) for a rule with legal weight, so it's the primary approach; hand-rolled quote-then-verify prompting is documented as the fallback if needed during implementation.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| No real API keys/credentials are available in this environment for SnapTrade, FMP, Finnhub, or Anthropic. | Build against documented API shapes and mock every external call in tests (R10). Real end-to-end verification against live services is explicitly a post-handoff step for whoever holds the credentials, not something this plan can complete unassisted. |
| Claude model ids deprecate on a rolling schedule (`claude-opus-4-1-20250805` retires 2026-08-05, just after this plan was written). | Model id lives in settings, never hardcoded inline (Key Technical Decisions); implementer should re-check `platform.claude.com/docs/en/about-claude/model-deprecations` at implementation time in case `claude-sonnet-5` itself has moved by then. |
| APScheduler's single-process assumption breaks silently if the app is ever run with multiple workers. | Explicit single-worker note in `backend/README.md` and a code comment at the scheduler's registration site (U9). |
| A future change could accidentally call one of the SnapTrade SDK's sync methods instead of its `a`-prefixed async twin, blocking the event loop. | All SnapTrade calls are centralized in one service module (U4); code review confirms only async methods are used (U4 Verification). |
| The advisor's no-directive-advice rule is the single highest legal/product risk in the app; the output-side filter is lexical, not semantic, so a response can be prescriptive in meaning without using any flagged phrase. | Enforced at two layers (system prompt + output-side phrase filter), with a dedicated table-driven test suite including one adversarial-content scenario (U8) — CLAUDE.md explicitly calls for this path to be "implemented and tested deliberately." The lexical-filter gap is an accepted, explicitly documented MVP limitation (Key Technical Decisions), not a hidden one; escalate to a semantic check if real outputs exhibit it. |
| A schema change to `cache_entries` or `portfolio_snapshots` affects multiple service integrations plus indirectly the advisor's context assembly. | `Base.metadata.create_all()` plus the repository pattern (U3) keep the schema surface small, explicit, and centralized in `db/models.py`; add Alembic before any real multi-environment or deployment need arises. |
| Request-serving code and the in-process scheduler both write to `cache_entries`/`portfolio_snapshots` on one SQLite file concurrently — without an explicit concurrency policy this produces intermittent "database is locked" failures on otherwise-healthy requests. | WAL journal mode + busy-timeout PRAGMA and an atomic `INSERT ... ON CONFLICT` upsert (U3, Key Technical Decisions); cache-layer failures fall through to a live fetch rather than surfacing as an unhandled 500. |
| Two near-simultaneous `POST /portfolio/connect` calls (a double-click, a retried request) could both attempt to register with SnapTrade before either persists a `user_secret`, risking an orphaned remote registration or a crash on conflict. | `snaptrade_connection` is a singleton/unique-constrained table; a losing insert is caught and treated as "already connected," reusing the winning row (U4). |
| CORS-origin restriction alone doesn't prevent a non-browser client, or a same-machine/same-LAN caller, from directly hitting every endpoint and having it execute — CORS only governs whether a browser lets calling JS read the response, not whether the server runs the request. | A shared-secret bearer token gates every route as the actual access-control layer (Key Technical Decisions, U1); `backend/README.md` documents `127.0.0.1`-only binding as a hard constraint the whole model depends on. |
| SnapTrade's `get_user_account_positions` endpoint carries its own deprecation notice (independent of the 2026-04-25 user-level cutoff), pointing integrators to the unified `get_all_account_positions`. | U4 targets `get_all_account_positions` directly, verified against the actual installed SDK package rather than relying on the docs site alone. |
| Whether `connection_type="read"` is enforced at the brokerage OAuth/platform level (a hard boundary) versus being only a request-shape hint isn't independently confirmed by this plan's research — and matters more because encryption-at-rest for the resulting `user_secret` is deferred. | Treat the code-level "never import trading endpoints" convention as the actually-enforced guarantee (Key Technical Decisions); verify SnapTrade's `connection_type` semantics against their platform docs during U4 and flag to the user if it turns out to be a soft boundary only (Open Questions). |
| The MVP defers encryption-at-rest for the SnapTrade `user_secret` and cached positions/balances (Scope Boundaries), relying entirely on the SQLite DB file never being committed or leaving the machine. | `.gitignore` explicitly excludes the DB file (U1), with an explicit verification step confirming it's actually untracked — the deferral is only as sound as this one control. |

---

## Documentation / Operational Notes

- `backend/README.md` (U10) is the primary handoff artifact — it must be sufficient on its own for a new session/person to get a running backend without reading source.
- Real API keys are the responsibility of whoever picks up frontend/integration work next; this plan explicitly cannot obtain or verify them.
- This plan intentionally excludes CI/CD, containerization, and any deployment target — purely local-dev readiness for a frontend handoff.
- The whole access-control model (shared bearer token + CORS) depends on the backend staying bound to `127.0.0.1`; widening the host bind (e.g. to check the dashboard from another device) is a deliberate decision the next session should make consciously, with the security implications in mind, not a casual `--host 0.0.0.0` flag flip.

---

## Sources & References

- [SnapTrade docs](https://docs.snaptrade.com/)
- [SnapTrade Python SDK (PyPI)](https://pypi.org/project/snaptrade-python-sdk/)
- [FMP stable Ratios API](https://site.financialmodelingprep.com/developer/docs/stable/metrics-ratios)
- [FMP stable Key Metrics TTM](https://site.financialmodelingprep.com/developer/docs/stable/key-metrics-ttm)
- [FMP Pricing Plans](https://site.financialmodelingprep.com/pricing-plans)
- [SEC EDGAR developer resources](https://www.sec.gov/about/developer-resources)
- [SEC.gov Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
- [Finnhub rate limits](https://finnhub.io/docs/api/rate-limit)
- [Finnhub company news](https://finnhub.io/docs/api/market-news)
- [Anthropic model overview](https://platform.claude.com/docs/en/about-claude/models/overview)
- [Anthropic model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations)
- [Anthropic Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
- [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages)
- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI dependencies with yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)
- [FastAPI background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [httpx async docs](https://www.python-httpx.org/async/)
- [respx guide](https://lundberg.github.io/respx/guide/)
- [SQLAlchemy 2.0 asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Cosmic Python — Repository Pattern](https://www.cosmicpython.com/book/chapter_02_repository.html)
- [mypy command-line docs](https://mypy.readthedocs.io/en/stable/command_line.html)
- [ruff rules](https://docs.astral.sh/ruff/rules/)
