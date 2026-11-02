---
title: Scope advisor context to matched symbols and company names for general questions
type: fix
status: active
date: 2026-08-20
---

# Scope Advisor Context to Matched Symbols and Company Names for General Questions

## Summary

Fix `ClaudeService.chat()` so a general, unscoped advisor question (the homepage "Ask about your portfolio" entry point) can still pull fundamentals, news, and XBRL facts: when the caller supplies no explicit symbols and no filing reference, detect any of the user's currently-held tickers or company names mentioned in the question text, and use those to drive the same fundamentals/news/facts builders the explicitly-scoped "Ask about this position" flow already uses. Company-name resolution reuses SEC's ticker map that `EdgarService` already fetches and caches for CIK resolution — no new external data source. Holdings display, explicit scoping, and filing summarization are all unchanged.

---

## Problem Frame

`ClaudeService.chat()` only fetches fundamentals, news, and XBRL facts when `context_refs.symbols` is non-empty (`backend/app/services/claude_service.py`, the `if context_refs.symbols:` gate and `_build_facts_context`'s internal loop). The "Ask about this position" flow (`AdvisorTrigger` → `scopeSymbol` set in `frontend/components/advisor/AdvisorPanel.tsx`) always sends `symbols: [scopeSymbol]`, so it gets full context. The general homepage "Ask about your portfolio" button opens the panel with no scope, so the frontend always sends `symbols: []` — meaning a general question only ever sees raw holdings (quantity, market value, allocation, P&L) and never fundamentals, news, or facts for any position, even when the question is clearly about one of them, whether the user names it by ticker or by company name.

---

## Requirements

- R1. When a general (unscoped, non-filing) advisor question mentions one of the user's currently-held ticker symbols by name, fundamentals, XBRL facts, and news for that symbol are included in the assembled context.
- R2. When a general question mentions one of the user's currently-held companies by name (not ticker), the same context is included for that symbol.
- R3. When a general question does not mention any held symbol or company name, context assembly behaves exactly as it does today (holdings only; no fundamentals/news/facts).
- R4. The holdings list shown in general-question context is unaffected by matching — it continues to show every current holding regardless of whether a symbol was matched.
- R5. Matching is limited to the user's own held symbols and their company names (not arbitrary tickers or companies), and reuses data EdgarService already fetches for CIK resolution rather than adding a new external data source or dependency.
- R6. The "Ask about this position" flow (`context_refs.symbols` already explicitly set) is unaffected by this change.
- R7. Filing summarization (`context_refs.filing_ref` set) is unaffected by this change — matching never runs when a filing is referenced, regardless of what the question text says.
- R8. If the brokerage connection is unavailable when a general question is asked, symbol/name matching fails gracefully (no matches) rather than raising an error.

---

## Scope Boundaries

- Colloquial or brand names that differ from a company's SEC-registered legal name (e.g., a company commonly known by a name other than its filer title) — matching covers literal name mentions only, not brand-name resolution. Accepted limitation (see Key Technical Decisions).
- A stricter disambiguation strategy for short/common-word tickers or single-word company names that are also ordinary English words — accepted known limitation (see Key Technical Decisions).
- Changes to the "Ask about this position" or filing-summarization flows.
- Frontend changes — this is entirely backend (`ClaudeService`, `EdgarService`); the general panel already sends the full question text needed for matching.
- Conversation memory or multi-turn context accumulation.

---

## Context & Research

### Relevant Code and Patterns

- `backend/app/services/claude_service.py` — `ClaudeService.chat()`, `_build_portfolio_context`, `_build_facts_context`, `_build_fundamentals_context`, `_build_news_context`: the exact gate and builders this plan touches.
- `backend/app/services/edgar_service.py` — `_fetch_ticker_map` fetches and caches (`cache_key="ticker_cik_map"`, 7-day TTL) SEC's full `company_tickers.json`, but only extracts `ticker` and `cik_str` per entry today, discarding `title` (the company's registered name). `resolve_cik` reads this same cached payload.
- `backend/tests/fixtures/synthetic_filing.py` — `SYNTHETIC_TICKER_MAP` already includes a `title` field per entry (e.g. `"title": "Synthetic Test Co"`), confirming the real SEC payload shape carries company names even though the code doesn't use that field yet.
- `backend/app/domain/allocation.py`, `backend/app/domain/concentration.py` — the project's established pattern for pure, no-I/O domain functions (Args/Returns docstrings, `Sequence` inputs); the new symbol/name-matching function follows this pattern.
- `backend/app/services/snaptrade_service.py` — `SnapTradeService.list_positions()`, already used by `_build_portfolio_context`; the new held-symbol lookup reuses it.
- `backend/tests/services/test_claude_service.py`, `backend/tests/services/test_edgar_service.py` — existing test harnesses and patterns to extend.
- `backend/tests/fixtures/synthetic_positions.py` — `build_fake_snaptrade_client`'s `positions_error` parameter, needed to actually exercise `ProviderUnavailableError` (rather than `connected=False`, which only yields an empty-but-successful account list).
- `backend/tests/domain/test_concentration.py` — pattern for pure-function domain tests with no mocking.

### Institutional Learnings

- None — `docs/solutions/` does not exist yet in this repo.

### External References

- None — pure internal architecture change, no new technology or external API.

---

## Key Technical Decisions

- **Match both ticker and company name, reusing EdgarService's already-cached SEC ticker map.** `_fetch_ticker_map` already fetches and caches `company_tickers.json` for CIK resolution; that payload already carries each ticker's registered `title`. Broadening the cached payload to retain `title` alongside `cik_str` (instead of adding a new fetch) is how company-name matching stays within R5's "no new data source" constraint.
- **`resolve_cik`'s existing signature and behavior are unchanged.** It keeps reading the cik portion of the (now richer) cached payload; a new method resolves company names from the same cache entry, best-effort (a symbol absent from SEC's map — e.g., some ETFs — simply has no name to match on, and ticker matching still applies).
- **Company name matching normalizes away common corporate suffixes** (e.g. Inc., Corp., Corporation, Co., Ltd., LLC, PLC, Class A/B/C) before requiring the normalized name as a whole-phrase, word-boundary match — deliberately not a general NLP fuzzy matcher, consistent with "prefer clarity over cleverness."
- **Reuse `list_positions()` again rather than refactoring `_build_portfolio_context`'s signature.** The SnapTrade cache-through layer (300s TTL) makes a second call within the same request a cache hit in the common case, and this keeps `_build_portfolio_context` — and its existing test coverage — completely untouched.
- **`effective_symbols = context_refs.symbols or matched_symbols`, and matching only runs when `context_refs.filing_ref` is also `None`.** Explicit scoping always wins, and a filing-only call never triggers matching regardless of question wording — closing a gap where the original formula could leak fundamentals/news into a filing-summarization call that the plan otherwise promises to leave untouched.
- **`_build_facts_context` takes an explicit `symbols` list (plus `filing_ref`) instead of the whole `ContextRefs`**, so the caller can pass `effective_symbols` and both the explicit-symbol path and the matched-symbol path share the same facts-fetching code.
- **Accepted limitation, broadened to names:** a held ticker or a single-word company name (after suffix-stripping) that's also an ordinary English word could false-positive match inside ordinary question text. No current holding triggers this. Treated as a known MVP limitation (extra context included, not wrong data), not solved with a disambiguation heuristic.
- **Accepted limitation:** SEC's registered legal name can differ from a company's common or brand name (e.g. a filer's legal title vs. how the company is colloquially known). Matching only covers literal name mentions in the question; it does not resolve brand names to legal names.

---

## Open Questions

### Resolved During Planning

- Ticker-only vs. company-name matching → both; SEC's ticker map already carries company titles via the same cache used for CIK resolution, so no new data source is needed.
- Whether a matched symbol should narrow the holdings list → no; holdings context stays full regardless of a match.
- Whether to guard against common-word ticker/name false positives → accepted as a known limitation, not built.
- Whether legal-name/brand-name mismatch (e.g. a filer's registered title differing from its common name) needs solving → accepted limitation, documented, not solved.

### Deferred to Implementation

- Exact regex-escaping approach for symbols and company names containing non-alphanumeric characters (e.g. a class-share ticker like `BRK.B`, or a name containing `&`) — straightforward with standard escaping, left to implementation.
- Exact corporate-suffix list to strip during name normalization — a short, explicit list (Inc., Corp., Corporation, Co., Ltd., LLC, PLC, Class A/B/C and similar) is sufficient; left to implementation rather than enumerated here.

---

## Implementation Units

### U1. Symbol-and-name matching domain function

**Goal:** A pure, no-I/O function that finds which of a user's held symbols are mentioned in a question's text, by ticker or by (normalized) company name.

**Requirements:** R1, R2, R3, R5

**Dependencies:** None

**Files:**
- Create: `backend/app/domain/symbol_matching.py`
- Test: `backend/tests/domain/test_symbol_matching.py`

**Approach:**
- Input is a sequence of held symbols, each with an optional company name (a symbol may have no resolved name).
- Ticker matching: case-insensitive, word-boundary match, same as before.
- Name matching: normalize the company name by stripping common corporate suffixes and trailing punctuation, then require the normalized name as a whole-phrase, word-boundary, case-insensitive match in the question — not a match on any single word of a multi-word name.
- A symbol matches if either its ticker or its normalized name is found; matches are deduplicated and returned in held-symbols order (not order-of-appearance in the question).
- No I/O — pure function over plain strings and an in-memory name list, mirroring `concentration.py`'s style.

**Technical design:** *(directional only, not implementation specification)*
```
@dataclass(frozen=True, slots=True)
class HeldSymbol:
    symbol: str
    company_name: str | None

def match_held_symbols(question: str, held: Sequence[HeldSymbol]) -> list[str]:
    # for each held symbol: word-boundary match on symbol.symbol,
    # OR word-boundary phrase match on normalize(symbol.company_name) if present
    # collect matches, preserve held order, dedupe
```

**Patterns to follow:**
- `backend/app/domain/concentration.py` (pure function, `Sequence` input, Args/Returns docstring style)
- `backend/tests/domain/test_concentration.py` (no-mocking domain test style)

**Test scenarios:**
- Happy path: question mentions a held symbol's ticker as a standalone word (any case) → that symbol is returned.
- Happy path: question mentions a held symbol's company name (no ticker mentioned) → that symbol is returned.
- Happy path: question mentions multiple held symbols (mix of ticker and name mentions) → all are returned, in held-symbols order.
- Edge case: a held symbol's ticker or name appears only as a substring inside a longer word in the question → not returned.
- Edge case: only one word of a multi-word company name appears in the question (e.g. the generic part of the name) → not returned; the full normalized name must appear as a phrase.
- Edge case: a symbol has no resolved company name (`company_name is None`) → still matches on ticker alone.
- Edge case: question mentions a ticker or name not in `held` → not returned (matching is scoped to the caller's own holdings, never an arbitrary company).
- Edge case: `held` is empty, or question text is empty → returns empty list.

**Verification:** Function returns correct, deduplicated matches for the scenarios above with zero I/O; unit tests pass without mocks.

---

### U2. Expose company names from EdgarService's cached ticker map

**Goal:** `EdgarService` can resolve a held symbol's company name from the same cached SEC ticker map it already uses for CIK resolution, without changing `resolve_cik`'s existing contract.

**Requirements:** R5

**Dependencies:** None

**Files:**
- Modify: `backend/app/services/edgar_service.py`
- Test: `backend/tests/services/test_edgar_service.py`

**Approach:**
- `_fetch_ticker_map`'s cached payload keeps both `cik_str` and `title` per ticker (currently only `cik_str` survives); `resolve_cik` is updated to read the cik portion of the richer payload so its external behavior is unchanged.
- Add a new method that resolves company names for a batch of symbols from the same cached payload, returning only the symbols found (silently omitting unresolved ones — best-effort, unlike `resolve_cik`'s raise-on-not-found).
- Same cache key (`ticker_cik_map`) and TTL as `resolve_cik` — this is a shape change to an existing cache entry, not a new cache surface.

**Technical design:** *(directional only, not implementation specification)*
```
async def resolve_company_names(self, symbols: Sequence[str]) -> dict[str, str]:
    # read the same cached ticker map resolve_cik uses (same cache key/TTL)
    # return {symbol: title} for symbols present in the map; omit the rest
```

**Patterns to follow:**
- `EdgarService.resolve_cik`'s existing cache-through call shape (same `fetch_with_cache` call, same cache key, same TTL).
- `backend/tests/fixtures/synthetic_filing.py`'s `SYNTHETIC_TICKER_MAP`, which already includes `title` per entry — no new fixture needed.

**Test scenarios:**
- Happy path: resolving one held symbol present in the ticker map returns its title.
- Happy path: resolving multiple symbols returns all resolved titles.
- Edge case: a symbol not present in the ticker map is omitted from the result (not raised).
- Edge case: empty `symbols` input returns an empty dict.
- Regression: `resolve_cik`'s existing behavior and test coverage are unaffected by the payload shape change.

**Verification:** New tests pass; `resolve_cik`'s full existing test suite still passes unmodified; `ruff`/`mypy` clean.

---

### U3. Wire matched symbols into `ClaudeService.chat`'s context assembly

**Goal:** General (unscoped, non-filing) advisor questions get fundamentals/news/XBRL facts for any held symbol they mention by ticker or company name, while explicit scoping, holdings display, and filing summarization stay exactly as they are today.

**Requirements:** R1, R2, R3, R4, R6, R7, R8

**Dependencies:** U1, U2

**Files:**
- Modify: `backend/app/services/claude_service.py`
- Test: `backend/tests/services/test_claude_service.py`

**Approach:**
- In `chat()`, matching runs only when `context_refs.symbols` is empty **and** `context_refs.filing_ref` is `None`. When it runs: fetch the connected portfolio's held symbols (reusing `SnapTradeService.list_positions()`, tolerating `ProviderUnavailableError` the same way `_build_portfolio_context` already does), resolve their company names via `EdgarService.resolve_company_names` (best-effort — an unresolved name still allows ticker-only matching for that symbol), and run U1's matcher against the question text to derive `effective_symbols`.
- When `context_refs.symbols` is already set, or `context_refs.filing_ref` is set, matching never runs and `effective_symbols` is exactly `context_refs.symbols` — unchanged from today for both flows.
- The fundamentals/news gate (currently `if context_refs.symbols:`) becomes `if effective_symbols:`.
- `_build_portfolio_context` and its call site are untouched — holdings context continues to use `context_refs.symbols or None` exactly as today.

**Execution note:** Write the integration test scenarios below against the existing `_build_claude_service` harness before wiring the implementation, since this unit's correctness is defined entirely by what ends up in the assembled prompt.

**Technical design:** *(directional only, not implementation specification)*
```
effective_symbols = context_refs.symbols
if not effective_symbols and context_refs.filing_ref is None:
    effective_symbols = await self._match_symbols_in_question(question)
context_items += await self._build_facts_context(effective_symbols, context_refs.filing_ref)
if effective_symbols:
    context_items += await self._build_fundamentals_context(effective_symbols)
    ... news ...
```

**Patterns to follow:**
- `_build_portfolio_context`'s existing `try/except ProviderUnavailableError: return None` shape, for the new held-symbol lookup's failure handling.
- `test_claude_service.py`'s `_prompt_text` / `_build_claude_service` / `_mock_symbol_providers` helpers.
- `tests/fixtures/synthetic_positions.py`'s `build_fake_snaptrade_client(positions_error=...)`, to force a real `ProviderUnavailableError` rather than relying on `connected=False` (which only yields an empty-but-successful account list and does not exercise the exception path).

**Test scenarios:**
- Happy path: `ContextRefs()` (no symbols, no filing) with a question naming a held symbol by ticker → sent prompt includes "Fundamentals for <SYMBOL>" and a recent-news block for it. Covers R1.
- Happy path: `ContextRefs()` with a question naming a held symbol by company name only (no ticker mentioned) → same context is included. Covers R2.
- Happy path: `ContextRefs()` with a question naming none of the held symbols or names (e.g. "How is my portfolio balanced?") → sent prompt has no fundamentals or news block; holdings list is still present. Covers R3, R4.
- Integration: the holdings list in the sent prompt shows every held position, not just the matched one, when a symbol was matched. Covers R4.
- Integration: `ContextRefs(symbols=["AAPL"])` with a question naming a *different* held symbol → only AAPL's fundamentals/news are sent; explicit scope wins and matching does not add the mentioned-but-unscoped symbol. Covers R6.
- Integration: `ContextRefs(filing_ref=..., symbols=[])` with a question naming a held symbol/company by name → fundamentals/news stay absent; only the filing's own facts (already independent of matching) are present. Matching does not run at all when a filing is referenced. Covers R7.
- Integration: a general question naming one held (matched) symbol alongside a plausible non-held company → the assembled context has no data for the non-held company, so the model has nothing to answer from except the existing "say so explicitly" grounding behavior — verifies the partial-match case doesn't quietly widen what gets sent. Covers R1-R3 jointly.
- Error path: no brokerage connection, forced via a real `ProviderUnavailableError` (not `connected=False`) with a question naming a held-sounding symbol → `chat()` does not raise from the matching step itself; existing success/`InsufficientContextError` behavior is unchanged from today. Covers R8.

**Verification:** New and existing tests in `test_claude_service.py` and `test_advisor_routes.py` pass; `ruff` and `mypy` clean on the changed file.

---

## System-Wide Impact

- **Interaction graph:** `ClaudeService.chat()` and its private builders, plus `EdgarService`'s ticker-map cache payload, are touched; no callbacks, middleware, or observers involved. The new cross-cutting effects are a second `SnapTradeService.list_positions()` call and an `EdgarService.resolve_company_names()` lookup per general-question request — the latter reads an already-cached, already-fetched payload (no new network call).
- **Error propagation:** The new held-symbol lookup reuses the exact `ProviderUnavailableError → no-op` handling `_build_portfolio_context` already has. Company-name resolution is best-effort (unresolved symbols just fall back to ticker-only matching) rather than error-raising.
- **State lifecycle risks:** None — no new persisted state; the ticker-map cache entry's payload shape changes, but it's TTL-bound and self-refreshing, not a migration concern.
- **API surface parity:** `ChatRequest`, `ContextRefs`, and `ChatResponse` schemas are unchanged; no frontend changes needed.
- **Integration coverage:** New tests exercise the real `ClaudeService.chat()` path end-to-end (through the same DB-session/cache/service wiring `_build_claude_service` already uses), not mocks-only, since the point of this fix is what actually reaches the assembled prompt.
- **Unchanged invariants:** `_build_portfolio_context`'s signature and behavior, `resolve_cik`'s signature and behavior, the "Ask about this position" flow, and filing summarization are all explicitly unmodified by this plan.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| A held ticker or single-word company name that's also a common English word could false-positive match inside ordinary question text, pulling in fundamentals/news the user didn't ask about. | Accepted known limitation (confirmed with user) — failure mode is extra context, not wrong data. No current holding triggers it. |
| A company's SEC-registered legal name may differ from its common/brand name, so some real-world phrasing still won't match. | Accepted limitation, documented; not solved by this plan. |
| An extra `list_positions()` call per general question adds a small amount of latency/cache-layer load; during a genuine SnapTrade outage with nothing cached, this doubles failed live-fetch attempts per request alongside `_build_portfolio_context`'s own call. | Goes through the existing cache-through layer (300s TTL); in the common case (dashboard already loaded this session) it's a cache hit, not a live SnapTrade fetch. |
| Refactoring `_build_facts_context`'s signature, or `EdgarService`'s cached ticker-map payload shape, could silently change behavior for the existing explicit-symbol, filing-ref, or CIK-resolution paths. | `effective_symbols` reduces to `context_refs.symbols` unchanged whenever it was already non-empty or a filing is referenced; `resolve_cik`'s full existing test suite must pass unmodified against the new payload shape. |
| A general question naming both a held (matched) symbol and a non-held company could tempt the model to fill in the unmatched company from training knowledge. | Covered by a dedicated test scenario in U3; enforced by the system prompt's existing context-only grounding rule (hard rule 2), not a new mechanism. |

---

## Sources & References

- Related code: `backend/app/services/claude_service.py`, `backend/app/services/edgar_service.py`, `backend/app/domain/concentration.py`, `backend/app/services/snaptrade_service.py`
- Adjacent prior work (separate scope, same module): `docs/brainstorms/advisor-synthesis-and-formatting-requirements.md`
