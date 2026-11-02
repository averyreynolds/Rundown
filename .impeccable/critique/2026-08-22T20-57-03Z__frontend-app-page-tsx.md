---
target: landing home page
total_score: 33
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 2
timestamp: 2026-08-22T20-57-03Z
slug: frontend-app-page-tsx
---
Method: dual-agent (A: abfbe2bd38562c10e · B: a848b9ece7cc729e8)

**Note on target naming**: "the landing home page" is `frontend/app/page.tsx` — but per PRODUCT.md/DESIGN.md/the surface brief, this is not a marketing landing page. It's Rundown's single daily-use dashboard (mode: **Operate**), the screen Avery opens to check real brokerage holdings. The critique below evaluates it as that.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 4 | Bespoke skeleton, portfolio-wide freshness timestamp + stale chip, advisor "Thinking…" state all present |
| 2 | Match System / Real World | 4 | Brokerage-native vocabulary (P/E, ROE TTM, cost basis) matches the target user's existing mental model |
| 3 | User Control and Freedom | 3 | `ErrorState`'s "Try again" does a full page reload rather than a scoped retry; advisor drawer has 3 clean exits |
| 4 | Consistency and Standards | 4 | One card system, one radius scale, one chip component used uniformly |
| 5 | Error Prevention | 4 | Connect flow opens SnapTrade in a new tab rather than navigating away and losing state |
| 6 | Recognition Rather Than Recall | 3 | Fundamentals abbreviations (P/E, ROE (TTM)) shown with no explanatory affordance |
| 7 | Flexibility and Efficiency | 1 | No sort/filter/search across up to 30 holdings; flagged rows aren't surfaced first; no keyboard path through the list |
| 8 | Aesthetic and Minimalist Design | 4 | Restrained palette, generous card padding, no visual noise — confirmed clean by the detector (0 findings) |
| 9 | Error Recovery | 4 | `ErrorState` names the failed source (SnapTrade) and offers retry |
| 10 | Help and Documentation | 2 | No glossary/tooltip anywhere for P/E, ROE, TTM, or freshness semantics |
| **Total** | | **33** | **/40 — Good** |

All 10 heuristics were scored (none marked n/a) — this is an Operate surface with real efficiency and help-text surface area, so 7 and 10 apply and both came back weak.

## Design Specificity Verdict

**LLM assessment**: Authored for Rundown, not template-skinned — but deliberately playing a category-standard visual world straight, per PRODUCT.md's documented direction choice. The Rundown-specific fingerprints are real and non-decorative: `PnlValue.tsx` carries an inline comment justifying the no-red/green rule as a *legal* boundary (Investment Advisers Act), every data-bearing block renders the CLAUDE.md-mandated `{source} · as of {timestamp}` provenance line, the "worth a look" flag ties directly to the product's "does this matter?" thesis, and the loading skeleton is shaped to the actual card/row geometry rather than a generic shimmer. So the "could this be any dashboard template" read is real at the surface-chrome level, but it's a documented strategic choice (category-standard, chosen over two invented worlds during shape), not an authorship failure.

**Deterministic scan**: `detect.mjs --json frontend/app/page.tsx frontend/components` exited 0 with zero findings. No automated red flags on genericness, banned patterns, or structural anti-patterns anywhere in the scanned tree. This corroborates rather than contradicts Assessment A: the mechanical scan has nothing to add here, and Assessment A's qualitative "category-standard, played straight, by design" read stands uncontested.

**Visual overlays**: Not applicable — `detect.mjs`'s browser-injection overlay path is for static file targets served via `live-server.mjs`; this target is a live Next.js dev server, so Assessment B correctly skipped injection and substituted direct screenshots instead. No overlay is available in a `[Human]` tab for this run.

## Overall Impression

The bones are genuinely good: a calm, compliance-correct dashboard that gets the hard legal stuff right where it's easy to get wrong (neutral P&L color, cited advisor grounding, provenance lines). The biggest gap is that the product's own headline promise — "does this matter?" — isn't yet fully wired into the UI. Per-position staleness is fetched into the data model and then silently dropped at render, the holdings list makes the user scan everything instead of surfacing what's flagged, and the expanded row dumps four data types at once instead of leading with the answer. These aren't cosmetic; they're the exact places where the product's central idea currently loses to its own plumbing.

## What's Working

- **`PnlValue`'s compliance-aware implementation**: neutral ink + a faint directional glyph, applied identically at portfolio-total and per-row level, with the legal reasoning documented inline in the component itself. This is a real regulatory boundary correctly translated into pixels, not just described in CLAUDE.md.
- **Provenance line coverage**: `{source} · as of {timestamp}` renders on the portfolio summary, fundamentals, news, and filing blocks alike — a systemic pattern applied everywhere the rule requires it, not spot-fixed for review.
- **Clean mechanical health**: zero detector findings, zero console errors/warnings across all five states (stale/empty/error/loading/advisor-open), zero failed network requests. The states that exist are genuinely solid, distinct, and dissonance-free (aside from one copy note below).

## Priority Issues

**[P0] Per-position staleness is fetched but never rendered — `frontend/components/holdings/HoldingRow.tsx`**
- **Why it matters**: Every `SourcedValue<T>` (fundamentals, news, filing) carries an `isStale: boolean`, populated all the way from the API layer through `lib/dashboard.ts` into `lib/types.ts` — but `HoldingRow.tsx` only ever renders the source/as-of text, never checks `.isStale`. Only the whole-portfolio banner in `PortfolioSummary.tsx` reflects staleness. A stale fundamentals or news block for one position looks identical to a fresh one. CLAUDE.md calls this exact scenario "a trust-breaking bug, not a cosmetic one," and the surface brief explicitly requires per-position staleness flagging.
- **Fix**: Render a `StatusChip tone="stale"` (or an inline wash matching the existing pattern) on each nested fundamentals/news/filing card, driven by that block's own `isStale` flag — not just the portfolio-level one.
- **Suggested command**: `/impeccable harden`

**[P1] No sort/filter at the stated 30-position scale — `frontend/components/holdings/HoldingsList.tsx`**
- **Why it matters**: The list is fixed-sorted by allocation with no way to surface flagged positions first, sort by P&L, or filter. At 11 positions the 3 flagged rows are already scattered through the list; at the brief's stated 30-position ceiling this gets worse. It directly undercuts "does this matter?" — the user still has to read the whole list to find what's flagged.
- **Fix**: Default-sort flagged positions to the top (or add a lightweight sort/filter affordance).
- **Suggested command**: `/impeccable optimize`

**[P1] Expanded row dumps everything at once — `frontend/components/holdings/HoldingRow.tsx`**
- **Why it matters**: Flag reason, fundamentals, news, and filing all render simultaneously on expand with equal visual weight — four distinct data types in one reveal, no staging. This is the one place the UI actually contradicts the product's stated "synthesize, don't dump" principle.
- **Fix**: Lead with the flag reason as the direct answer to "does this matter," and move raw fundamentals/filing/news behind a secondary "see the data" disclosure.
- **Suggested command**: `/impeccable distill`

**[P2] Expanded row's accessible name is an unstructured concatenation — `frontend/components/holdings/HoldingRow.tsx`**
- **Why it matters**: The `<button>` wrapping the whole row has no `aria-label`, so a screen reader announces the full run-on text content (ticker + flag chip + company name + value + percent + signed P&L) for every row, up to 30 times per session. `aria-expanded`/`aria-controls` are already wired correctly, which makes this an isolated, easy fix.
- **Fix**: Add `aria-label={`${symbol} — ${name}, expand for details`}` to the row toggle.
- **Suggested command**: `/impeccable harden`

**[P2] Help & Documentation gap on financial jargon — throughout the fundamentals/holdings surfaces**
- **Why it matters**: P/E, ROE (TTM), net margin, and freshness semantics ("stale") are shown with zero explanatory affordance anywhere on the page. Fine for Avery today; a real gap the moment this is shown to an outside viewer (the stated secondary "portfolio piece" audience) who doesn't already know the vocabulary.
- **Fix**: Lightweight inline tooltip or `title`/definition affordance on the abbreviated fundamentals labels.
- **Suggested command**: `/impeccable clarify`

## Persona Red Flags

**Alex (Power User)**: No sort/filter mechanism in `HoldingsList.tsx` means Alex's daily habit is a full linear re-scan of a fixed-order list every single time, even though the product's entire value proposition is surfacing what changed. This is exactly why Heuristic 7 scores a 1.

**Sam (Accessibility / screen reader / keyboard)**: The `HoldingRow` toggle's missing accessible name (P2 above) is the clearest failure — every row announces as one unstructured run-on string. Secondary: `AllocationBar`'s segment composition is exposed only via a native `title` attribute, which touch devices and most screen readers never surface (partially mitigated since the legend below repeats the same data as real text).

**Riley (Edge-case stress tester)**: The P0 staleness gap is the sharpest find — the data is plumbed all the way from the API layer into the type system and then silently dropped at render, which is exactly the kind of "looks like it works, quietly doesn't" bug Riley is built to catch. Riley would also flag that long fund/ETF names are untested against the existing `truncate` class — the class is there, but no fixture data exercises it.

## Minor Observations

- `LoadingSkeleton.tsx` hardcodes 6 placeholder rows regardless of actual holding count (fixtures have 11) — cosmetic mismatch, not a bug.
- `ErrorState`'s "Try again" does a full page reload via `next/link` rather than a scoped refetch.
- `AllocationBar.tsx` hardcodes the accent color inline (`rgba(54, 84, 214, ...)`) instead of referencing the `--color-accent` custom property already defined in `globals.css` — a duplicated source of truth for the system's one accent hue.
- `formatSignedCurrency`/`formatSignedPercent` correctly use a true minus sign (U+2212) rather than a hyphen — good typographic care, easy to have missed.
- The `?state=` preview harness has no direct "ready" case — `?state=stale` is the only way to preview the full data view, and it always shows the amber stale chip, so there's currently no way to preview the truly fresh happy path without a live backend.
- `PageHeader`'s "Does this matter?" tagline renders unchanged directly above `ErrorState`'s "Couldn't reach your portfolio data" — a small copy dissonance at exactly the moment the page is telling the user it can't answer that question.
- Browser evidence found zero console errors/warnings and zero failed network requests across all states — mechanically the page is in good health. Mobile-viewport (~375px) screenshots could not be captured this run due to a browser-automation tool limitation (`resize_window` reported success but the tab's actual viewport didn't change) — this is a tooling gap, not a finding about the page's responsive behavior, so treat the mobile layout as unverified rather than confirmed-good this round.

## Questions to Consider

1. What if the holdings list defaulted to flagged-first instead of allocation-sort — would "does this matter?" become literally true at first glance instead of requiring a full scan?
2. What if the `isStale` field already being fetched into every fundamentals/news/filing block actually rendered — closing the exact gap between what CLAUDE.md requires and what currently ships?
3. What if the expanded row led with "what changed" (the flag reason) and pushed raw fundamentals/filing metadata behind a second tap, so the reveal matched the product's own synthesis promise instead of flattening four data types into one view?
