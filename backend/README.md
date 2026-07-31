# Rundown Backend

FastAPI service that owns every third-party integration, portfolio math, caching, and LLM orchestration for Rundown. See the [root README](../README.md) for the product framing. This document is the handoff artifact for a new session/person to go from a clean checkout to a running backend without reading source first.

---

## Current status

Every unit in the backend scaffold is implemented: portfolio (SnapTrade, read-only), fundamentals (FMP), filing text (SEC EDGAR), structured filing facts (SEC XBRL), news (Finnhub), the shared cache/data layer, the scheduled refresh/snapshot jobs, and the AI advisor (`/advisor/chat`, Claude).

Filing data reaches the advisor in two forms: exact XBRL figures, cited by accession number, and verbatim narrative prose, cited by quoted passage.

The advisor is the highest legal/product-risk area in the app — see [When implementing the AI advisor specifically](../CLAUDE.md#when-implementing-the-ai-advisor-specifically) in the root `CLAUDE.md` and `app/services/claude_service.py`'s module docstring before touching it. Its no-directive-advice boundary is enforced at two layers (system prompt + an output-side lexical phrase filter); the filter's known, accepted gap is documented in *Known limitations* below.

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
| `ANTHROPIC_API_KEY` | [Anthropic Console](https://console.anthropic.com/) — keys look like `sk-ant-...`. Used by `/advisor/chat`. |
| `SEC_EDGAR_USER_AGENT` | Your own value: `"AppName/Version (you@example.com)"`. SEC requires a descriptive, real contact email or `data.sec.gov` returns 403. Covers filing text and the XBRL facts API — same host, same header, no separate key or rate limit. |
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

First-time flow: `POST /portfolio/connect` returns a fresh SnapTrade connection portal URL every call (Personal-tier auth has no local user-registration step — see `app/services/snaptrade_service.py`'s module docstring); open it and link a brokerage account, then `/portfolio/accounts` and `/portfolio/positions` return real data. Before linking anything, those two routes return `200` with an empty list, not an error — there's no "not connected" state to distinguish from a provider outage once Personal-tier credentials are configured at all.

`POST /advisor/chat` answers a question grounded only in the data you name in `context_refs` (`symbols`, and/or a `filing_ref` for citation-grounded filing summarization) — it never answers from the model's general knowledge, and it never tells you what to do with a position. Returns `422` if none of the referenced context is actually available (no symbols, no connected portfolio, no matching filing).

XBRL facts are included for every symbol in scope, plus the `filing_ref`'s own symbol; facts the referenced filing reported are marked as such. The filing document block is prompt-cached (5-minute TTL), so follow-up questions about the same filing cost a fraction of the first.

## Running the test suite

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy .
```

All four should pass clean before opening a PR. The test suite never hits a live API or consumes rate-limit budget — every external call (SnapTrade, FMP, EDGAR, SEC XBRL, Finnhub) is mocked (`respx` for the httpx-based providers; a structural fake for the SnapTrade SDK). Domain tests (`tests/domain/`) do no I/O at all.

## Architecture at a glance

- `app/domain/` — pure functions, no I/O and no framework imports: portfolio math (allocation, concentration, P&L), filing section extraction and scoping (`filing_sections.py`), XBRL fact selection (`xbrl_facts.py`). The last two hold the policy decisions — which Items bear on a position, which us-gaap concepts are worth grounding on — so both are editable in one place and testable against synthetic fixtures.
- `app/services/` — one module per third-party integration, plus shared plumbing (`cache_through.py` for the read-through-cache-with-stale-fallback pattern every provider uses, `errors.py` for the exception types `app/api/error_handlers.py` maps to HTTP responses).
- `app/cache/` — the one caching module (`cache_entries` table via `CacheRepository`), with per-data-type TTLs centralized in `ttl_policy.py`.
- `app/db/` — the only package that knows a connection string or SQL dialect. Swapping SQLite for Postgres later is a `DATABASE_URL` + driver change here, not a rewrite.
- `app/scheduler/` — APScheduler jobs that refresh the cache on a schedule (never per-request): fundamentals and XBRL facts daily, news every 4h, plus the daily portfolio snapshot (`portfolio_snapshots` — write-only for now; trend/comparison logic is deferred follow-up work).
- `app/api/` — routers stay thin; all orchestration lives in `services/`.

## Known limitations (by design, for this MVP)

- **No encryption at rest** for cached positions/balances — the SQLite file is gitignored and assumed to never leave your machine. Add field-level encryption before running this anywhere less trusted than a single local machine. (No SnapTrade `user_secret` to worry about: Personal-tier auth has no local user-registration row at all — see `app/services/snaptrade_service.py`'s module docstring.)
- **SnapTrade's `connection_type="read"` enforcement is not independently verified.** Whether the brokerage enforces read-only access at the OAuth-consent level (a hard boundary) or only treats it as a request-shape hint to the connection portal hasn't been confirmed. The code-level guarantee — `app/services/snaptrade_service.py` never imports SnapTrade's trading/orders SDK namespace (enforced by a static AST test) — is the guarantee that's actually verified. Confirm the platform-level behavior against SnapTrade's docs/support before treating this as airtight.
- **No trade execution anywhere.** This is a hard product/legal boundary (see the root `CLAUDE.md`), not an oversight — do not add order/trade/transfer endpoints without explicitly revisiting that boundary first.
- **FMP and SnapTrade response shapes are now verified against live responses** (real credentials, `app/services/snaptrade_service.py`), not just SDK/API docs — this caught two real bugs since the initial scaffold: SnapTrade's auth mode must be set via an `auth=` object or every request silently goes unsigned, and `get_user_account_balance`/`get_all_account_positions` return different envelope shapes (a bare list of per-currency entries; a `{"results": [...], "data_freshness": {...}}` wrapper) than the flat single-object/bare-list shape originally assumed. See the module's docstring and inline comments for exactly what's now confirmed.
- **The advisor's no-directive-advice filter is lexical, not semantic.** `contains_directive_language()` in `app/services/claude_service.py` catches known phrases ("you should sell," "I recommend") but not semantically prescriptive, lexically-clean phrasing ("this looks like an attractive entry point"). This is an accepted MVP limitation, defended in depth by the system prompt; escalate to a second-pass semantic check (e.g. an extra classifier call) if real model outputs exhibit this pattern.
- **Anthropic Citations API response shape was verified by introspecting the installed SDK's type definitions, not a live response** (no real API key is available in this environment). Re-verify filing-summarization citation quality once real credentials exist.
- **The advisor sees a scoped excerpt, not the whole filing.** `app/domain/filing_sections.py` extracts more than it sends; the default scope is 10-K Items 7, 7A, 5, 3 (10-Q: Part I 2–3, Part II 1; 8-K whole). Risk Factors is extracted but out of scope — largest Item, lowest signal — and available via `scope=`, which nothing calls yet. Item 1 is never extracted. Omissions are always named in the model's context. Verified against 14 real filings from 7 filers (Apple, JPMorgan, P&G, Tesla, Coca-Cola, UnitedHealth).
- **Pointer sections resolve to notes only.** SEC rules let a filer satisfy an Item by cross-reference instead of restating it (JPMorgan's Item 3 is 76 characters). When such a section names a note — "Refer to Note 30" — that note's verbatim text is pulled from Item 8 and attached beneath it. Deferrals naming no note, or pointing at an exhibit or prior filing, are still reported as gaps.
- **XBRL coverage is verified only on large caps.** Filers disagree on concept names, so `app/domain/xbrl_facts.py` resolves each line item through a fallback chain of us-gaap tags; small caps, REITs, banks, and foreign issuers are untested. Non-GAAP measures (a REIT's FFO) are absent from the taxonomy entirely. Absences are reported to the model, never inferred as zero.
- **XBRL facts are advisor-only** — not exposed on any route, so the frontend contract is unchanged. `app/schemas/xbrl.py` is the shape to surface when that changes.
- **Portfolio, fundamentals, and news context carry no "as of" into the prompt.** `ContextItem` stores it but `_build_user_content` renders only `text`, so the model can't state how fresh they are. XBRL facts carry per-fact filing dates instead. Worth closing (hard rule 6).
