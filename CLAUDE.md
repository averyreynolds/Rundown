# CLAUDE.md
 
Operating guide for AI coding agents (Claude Code and similar) working in this repository. Read this before making changes. It encodes architecture, conventions, and **non-negotiable domain rules** specific to Rundown that are not obvious from the code alone.
 
If a request conflicts with the **Hard rules** below, stop and surface the conflict rather than complying.
 
---
 
## What this project is
 
Rundown is a portfolio intelligence dashboard. It connects to a user's real brokerage account, aggregates their equity holdings, and layers fundamentals, filings analysis, personalized news, and a conversational AI advisor on top. See `README.md` for the full product framing.
 
**Current phase:** MVP (Phase 1), single-user, greenfield. Optimize for a working, correct, secure single-user tool — not premature multi-tenant scale.
 
---
 
## Architecture
 
Two separate services:
 
- **`frontend/`** — Next.js (React, TypeScript). Dashboard UI only. **Never** calls a third-party data provider directly.
- **`backend/`** — Python (FastAPI). Owns all third-party integration, portfolio math, caching, and LLM orchestration. All API keys live here.
Data flow: `Frontend → FastAPI → {SnapTrade, FMP, SEC EDGAR, Finnhub, Claude}`. The frontend talks only to the backend.
 
**External services:**
| Service | Role | Free-tier limit to respect |
|---|---|---|
| SnapTrade | Brokerage holdings, cost basis, positions | Personal tier, 5 connections |
| Financial Modeling Prep (FMP) | Fundamental ratios | ~250 requests/day |
| SEC EDGAR (`data.sec.gov`) | Authoritative filing text (10-K, 10-Q, 8-K) | Unlimited, but requires a descriptive `User-Agent` header |
| Finnhub | News | 60 calls/min |
| Anthropic Claude API | AI advisor reasoning, filing summarization | Standard API limits |
 
---
 
## Hard rules (do not violate)
 
These encode product and legal boundaries, not style preferences.
 
1. **The AI advisor explains; it never prescribes.** No code path may produce "buy," "sell," "you should," or allocation directives — not in prompts, not in system messages, not in UI copy. When implementing advisor features, the system prompt must explicitly forbid directive advice and instruct the model to reframe "what should I do?" questions into "here is what's relevant" answers. This is a legal boundary (Investment Advisers Act), not just tone.
2. **The advisor is grounded in provided data only.** Never let the model free-associate financial claims. Every advisor response must be built from data the backend explicitly fetched and passed in (positions, a specific filing, a specific news item). No "general market knowledge" answers. Filing summaries must be traceable to source text — quote/cite the specific passage, don't freely paraphrase.
3. **API keys never reach the client.** All third-party keys live in the backend `.env`, are read server-side only, and must never appear in frontend code, `NEXT_PUBLIC_*` vars, committed files, logs, or responses sent to the browser. If you catch yourself putting a key anywhere the browser can see it, stop.
4. **Respect free-tier rate limits by caching, not by calling live.** Fundamentals and news must be cached and refreshed on a schedule (e.g. daily), never fetched fresh on every page load or request. Before adding a new external call, confirm it won't blow the daily budget. Assume the app must run indefinitely on free tiers.
5. **Never commit secrets or real financial data.** No `.env` files, no real account numbers, no real holdings data, no API keys in commits, fixtures, or tests. Use `.env.example` with placeholder values and synthetic fixtures.
6. **Label data provenance and freshness.** Anything shown to the user must carry its source and an "as of" timestamp. Wrong or stale fundamentals silently presented as current is a trust-breaking bug, not a cosmetic one.
7. **No trade execution.** SnapTrade supports placing trades. Rundown does not. Do not implement, scaffold, or wire up any order/trade/transfer endpoints, even if asked casually — flag it and confirm intent first, since it's explicitly out of scope and carries regulatory weight.
---
 
## Conventions
 
### Python (backend)
- Python 3.12+. Use type hints throughout; the codebase should pass `mypy`.
- FastAPI with Pydantic models for all request/response schemas — no raw dicts crossing the API boundary.
- Format with `ruff format`; lint with `ruff`. Run before committing.
- External API clients live in `backend/app/services/` (one module per provider). Route handlers stay thin — orchestration and business logic live in services, not in route functions.
- Portfolio math (allocation, concentration, P&L) lives in a dedicated, unit-tested module (`backend/app/domain/`) with no I/O — pure functions over typed inputs, so it's testable without hitting any API.
- Cache layer is explicit and inspectable; don't scatter ad-hoc caching. One caching module, clear TTLs per data type.
### TypeScript (frontend)
- Strict TypeScript. No `any` without a written justification comment.
- Next.js App Router. Server components by default; client components only where interactivity requires it.
- API responses typed to match the backend's Pydantic schemas — keep a shared understanding of the contract; update both sides together.
- Format with Prettier; lint with ESLint.
- No data-provider SDKs in the frontend. The only network target is the Rundown backend.
### General
- Small, focused commits with clear messages. Conventional Commits style preferred (`feat:`, `fix:`, `refactor:`, `docs:`).
- Every new backend feature that touches money math or external data gets a test. Domain logic (`backend/app/domain/`) should approach full coverage — it's the part where a bug means wrong numbers shown to a user.
- Prefer clarity over cleverness. This is a portfolio project people will read; readable code is a feature.
---
 
## Testing
 
- Backend: `pytest`. Domain/portfolio-math modules must be tested with synthetic data. External services are mocked — tests never hit live APIs or consume rate-limit budget.
- Frontend: component tests for interactive pieces; type-checking is the first line of defense.
- Before opening a PR: backend tests pass, `ruff` clean, `mypy` clean, frontend builds and type-checks.
---
 
## When implementing the AI advisor specifically
 
This is the highest-risk area for both correctness and the legal boundary. When touching advisor code:
 
- The system prompt must (a) forbid directive advice explicitly, (b) instruct grounding in provided context only, (c) instruct the model to cite the specific filing/position/news item it's drawing from.
- Pass the user's real data as structured context; do not rely on the model's training-data knowledge of a company.
- If the user asks "what should I do / should I buy / should I sell," the intended behavior is a graceful reframe ("Here's what's relevant to that position...") — not a refusal, and never a recommendation. Implement and test this path deliberately.
- Filing summaries must link back to the source filing and quote the specific lines they summarize.
---
 
## What to ask about before doing
 
Surface and confirm before implementing, rather than assuming:
 
- Anything that would place a trade, move money, or write back to the brokerage.
- Anything that adds a new external API call or dependency (rate-limit and cost impact).
- Anything that changes the advisor's boundaries or how it's grounded.
- Anything that would send user financial data to a new destination.
- Schema changes that break the frontend/backend contract (update both sides in the same change).