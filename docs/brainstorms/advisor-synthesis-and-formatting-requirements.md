---
date: 2026-08-20
topic: advisor-synthesis-and-formatting
---

# Advisor Response Synthesis and Formatting

## Summary

Keep the advisor's current response shape (prose answer plus a trailing citation list, no schema change), but fix how it renders — proper markdown instead of literal formatting characters, and a cleaner citation list — and extend the system prompt so answers synthesize what's notable, connected, and trending across the already-assembled context instead of reciting it block by block.

---

## Problem Frame

The advisor already assembles rich context per question — current holdings, SEC XBRL structured facts across multiple periods, FMP fundamentals, Finnhub news, and filing excerpts when one is referenced (`backend/app/services/claude_service.py`) — but the chat surface undersells it in two independent ways.

First, the response is rendered as raw text in a single paragraph (`frontend/components/advisor/AdvisorPanel.tsx`). When the model reaches for markdown-style emphasis or lists, which it does unprompted, the formatting characters show up literally in the UI instead of rendering. The trailing citation list is visually dense and hard to scan, especially when a citation carries a long filing quote.

Second, and separate from formatting, responses read as flat recitations of whatever context happens to be assembled. A question about a single holding surfaces figures and headlines in sequence rather than surfacing what's actually distinctive about the position, connecting a filing risk factor to a related headline, or calling out a multi-quarter trend when several periods for the same line item are already sitting in context. A recent real exchange — asking what's relevant to a COMP position — produced a dense, literally-asterisked paragraph that did none of that, despite the underlying context likely containing the material for it.

Both problems compound: a dense wall of unstructured, unprioritized prose is far harder to get value from than a shorter one that leads with what matters.

---

## Requirements

**Response rendering**
- R1. Advisor answer text in the chat panel renders markdown formatting (at minimum bold/emphasis and lists) rather than displaying raw markdown syntax characters.
- R2. The citation list attached to an advisor response is visually easier to scan than the current layout, particularly when a citation's quoted text is long (e.g., a filing excerpt).

**Answer synthesis**
- R3. The system prompt instructs the model to lead with what is most notable or distinctive about the position or topic in question, rather than reciting every context item in the order it was assembled.
- R4. When more than one period of the same structured fact (XBRL) is present in the context for a question, the system prompt instructs the model to call out the trend or change across periods rather than reporting only the latest figure.
- R5. When two or more context sources (holdings, filings, XBRL facts, news) bear on the same topic, the system prompt instructs the model to connect them explicitly rather than presenting them as unrelated blocks.
- R6. Synthesis instructions added under R3-R5 remain strictly descriptive of the user's own data and do not introduce evaluative or directive language — they reinforce, not loosen, the existing non-directive constraint (CLAUDE.md hard rule 1) and the context-grounding constraint (hard rule 2).

---

## Acceptance Examples

- AE1. **Covers R4.** Given the XBRL facts context contains three consecutive quarters of the same revenue line item, when the user asks a general question about that position, the answer describes the direction of change across those quarters rather than only stating the latest quarter's figure.
- AE2. **Covers R5.** Given both a recent news item and a filing excerpt reference the same topic (e.g., a legal proceeding), when the user asks what's relevant to that position, the answer connects the two rather than presenting them as separate, unrelated points.
- AE3. **Covers R3.** Given a position's context includes several data points but one is meaningfully unusual (e.g., a concentration flag, an outsized P&L swing), when the user asks a general "what's relevant" question, the answer leads with that unusual point rather than listing data points in context-assembly order.
- AE4. **Covers R6.** Given the model produces a synthesized answer, when that answer is checked against the existing lexical directive-language guard (`contains_directive_language`), the answer contains no directive or evaluative phrasing (e.g., "this looks concerning," "you should watch this") — only descriptive statements tied to cited data.

---

## Success Criteria

- A user reading an advisor response about one of their positions sees properly rendered formatting (no literal asterisks) and can scan the supporting citations without difficulty.
- A user asking a general "what's relevant" question gets an answer that surfaces the most notable thing about the position first, connects related context across sources when applicable, and calls out a trend when multiple periods are available — without any of that answer reading as a recommendation.
- The existing non-directive and context-grounding guarantees (system prompt wording plus the lexical filter) still hold after this work — spot-checking confirms no regression.
- Planning has enough detail to choose a markdown-rendering approach, revise the citation list layout, and rewrite the relevant portion of the system prompt without inventing new product behavior.

---

## Scope Boundaries

- Forcing a structured/schema response contract (the higher-upside alternative considered and set aside) — not built now; noted as a future escalation if prompt-only synthesis proves unreliable in practice.
- New context/data sources beyond what's already fetched (SnapTrade, FMP, EDGAR, Finnhub, XBRL).
- Conversation memory across questions, within or across sessions.
- Suggested or guided follow-up questions.
- Streaming responses.
- Inline citation-to-claim linking (e.g., footnote markers tied to specific sentences in the answer).
- Changing the response length budget (`_MAX_TOKENS`).
- Any change to the non-directive or context-grounding hard rules themselves.

---

## Key Decisions

- Keep the current prose-plus-trailing-citations response shape rather than moving to a structured/schema contract: reuses the existing citation mechanism and both non-directive guards without re-verifying them against a new response shape, matching the project's MVP/single-user framing.
- Address shallow answers via system-prompt instructions rather than new data fetching: the context already assembled (multi-period XBRL facts, news, filings) already contains what's needed for trend-calling and cross-source connection — the gap is instructional, not a missing data source.
- Scope the citation UI fix to visual/spacing cleanup, not restructuring citations to link inline to specific claims — matches the specific complaint raised (hard to scan visually, not unclear which claim a citation supports).

---

## Dependencies / Assumptions

- Rendering markdown in the chat panel requires either a markdown-rendering approach on the frontend or an equivalent client-side parsing solution; the specific mechanism (library vs. custom) is left to planning.
- No backend schema or API contract changes are required by this scope — `ChatResponse` and `Citation` shapes are unaffected.

---

## Outstanding Questions

### Resolve Before Planning

- None — synthesis was fully confirmed before this document was written.

### Deferred to Planning

- [Affects R1][Technical] Whether to introduce a markdown-rendering dependency on the frontend or write a narrow custom renderer for the constrained subset Claude actually produces (bold, lists, maybe headers).
- [Affects R2][Technical] Specific citation-list layout treatment (e.g., truncate-with-expand for long quotes, spacing/typography changes) — visual design left to planning/implementation.
- [Affects R3, R4, R5][Needs research] Exact system-prompt wording changes — should be drafted and spot-checked against a few real questions during planning/implementation to confirm synthesis instructions don't degrade citation-per-claim discipline.
