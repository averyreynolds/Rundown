# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js (React, TypeScript) frontend + Python (FastAPI) backend, as mandated by `CLAUDE.md`. Frontend is dashboard UI only and never calls a third-party data provider directly; backend owns all third-party integration, portfolio math, caching, and LLM orchestration. Not yet scaffolded — greenfield, docs-only at time of writing.

## Users

Primary user is the developer (Avery), building this first for their own daily use against their real Schwab account (via SnapTrade), and secondarily as a portfolio piece shown to others (e.g. potential employers). Single-user MVP — not designed for multi-tenant use yet.

The target persona described in `README.md` — an "engaged but time-constrained" investor who already knows what they own and wants to know what changed and whether it matters — is Avery themselves for now.

## Product Purpose

Rundown connects to a real brokerage account, aggregates equity holdings, and layers fundamentals, filings analysis, and personalized news on top, with a conversational AI advisor that explains day-to-day changes and why they matter. It exists to answer one question fast: **"does this matter?"**

MVP success is defined as the end-to-end pipeline working convincingly against real data — SnapTrade holdings sync → fundamentals/filings/news enrichment → AI advisor answering grounded questions — even before it becomes a daily habit. Replacing the daily brokerage-app check-in is the longer-term bar, not the v1 gate.

## Positioning

General brokerage apps (Schwab, Fidelity) serve every audience — retirees, day traders, options sellers, casual investors — at once, producing a crowded UI with plenty of data but little synthesis. Rundown's mechanism is different: it's scoped to one person's specific holdings, synthesizes fundamentals/filings/news into a single signal per position, and the AI advisor explains and contextualizes without ever prescribing — a boundary that's a deliberate legal/product choice (Investment Advisers Act), not just a style preference. A neighboring product couldn't casually copy this without either broadening back into general-audience noise or crossing into regulated advice.

## Operating Context

- Real brokerage connection via SnapTrade (personal tier, 5-connection limit); Avery's actual Schwab account is the reference holding set.
- Single-user, self-hosted deployment for now — not a multi-tenant SaaS.
- Data refreshed on a cache/schedule basis (e.g. daily), not fetched live per page load, to respect free-tier rate limits (FMP ~250 req/day, Finnhub 60 calls/min, SEC EDGAR unlimited but requires a descriptive User-Agent).
- The AI advisor is a text interface for MVP; voice is a stated future direction, not in scope now.

## Capabilities and Constraints

Confirmed, non-negotiable (from `CLAUDE.md`):

- The AI advisor explains; it never prescribes. No "buy," "sell," "you should," or allocation directives anywhere in the product, including prompts and UI copy.
- The advisor is grounded only in data the backend explicitly fetched and passed in (positions, a specific filing, a specific news item) — never general market knowledge. Filing summaries must cite/quote the specific source passage.
- No trade execution, order placement, or transfers — explicitly out of scope even though SnapTrade supports it.
- All third-party API keys live server-side only (backend `.env`), never in frontend code, `NEXT_PUBLIC_*` vars, logs, or browser-visible responses.
- Anything shown to the user carries its data source and an "as of" freshness timestamp.
- No real financial data, account numbers, or secrets in commits, fixtures, or tests — synthetic fixtures and `.env.example` placeholders only.

Undecided / open: exact per-data-type cache TTLs and refresh schedule are not yet specified beyond "daily, not live."

## Brand Commitments

- Name: **Rundown**. MIT License, copyright © 2026 averyreynolds.
- Voice demonstrated in `README.md`: plain-English, specific, non-alarmist explanations — e.g. *"Your position in X is now 18% of your portfolio, up from 11% three months ago — mostly price appreciation, not new buys."*
- No logo or other visual brand assets exist yet.
- Visual world: standing category-standard direction, chosen deliberately over invented worlds (newsroom-rundown, split-flap board) during the home dashboard's `shape` pass. Craft bar is consumer-fintech done well — **Robinhood, Copilot Money, Wealthfront** — not enterprise-SaaS (Linear/Stripe) or professional-terminal density (Bloomberg/Schwab). Execute the category convention at full commitment: no irony, no smuggled quirk.

## Evidence on Hand

None yet. No API access/accounts are set up for any provider (SnapTrade, FMP, SEC EDGAR, Finnhub, Anthropic) as of this writing — build proceeds against synthetic fixtures/mocks first, with real keys wired in later. There is no existing codebase beyond `README.md`, `CLAUDE.md`, and `LICENSE`. Future work must not fabricate testimonials, benchmarks, pricing, or sample holdings presented as real.

## Product Principles

1. Synthesize, don't dump — every surface should compress raw feeds into a single "does this matter" signal, not add another data table.
2. Personalize to actual holdings — relevance is scoped to what the user owns (and explicitly watches), not general market coverage.
3. Explain, never prescribe — the advisory boundary is a legal constraint, not a tone choice, and must be architected in, not just prompted around.
4. Design for free-tier sustainability — caching and scheduling are load-bearing, not an optimization; the product must run indefinitely without live-call rate-limit failures.
5. Hold up to both daily use and outside scrutiny — this is simultaneously a real personal tool and a piece of work Avery will show to others, so correctness and readability both matter.
