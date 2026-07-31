# Handoff: rework how filing data reaches the advisor

Paste everything below the line into a fresh Claude Code session started in
`C:\Users\avery.reynolds\Rundown`.

---

## Context

Rundown is a portfolio intelligence dashboard (see `CLAUDE.md` and `README.md`).
One of its features is an AI advisor that answers questions grounded in a
specific SEC filing, using Anthropic's Citations API. I need to change how
filing data gets to that advisor.

**Read `CLAUDE.md` first.** The hard rules that bind this work: the advisor
explains and never prescribes (rule 1); every claim is grounded in data the
backend explicitly fetched and filing claims must be traceable to source
passages (rule 2); cache rather than calling live (rule 4); everything shown
carries source and "as of" (rule 6). Also note its "ask before doing" list —
adding external calls and changing how the advisor is grounded are both on it.

## Current state of the working tree

**All of this is uncommitted on `main`.** Nothing is pushed. Decide with me
whether to commit it as a checkpoint before building on top.

```
 M backend/README.md
 M backend/app/services/claude_service.py
 M backend/app/services/edgar_service.py
 M backend/pyproject.toml
 M backend/tests/fixtures/synthetic_filing.py
 M backend/tests/services/test_claude_service.py
 M backend/tests/services/test_edgar_service.py
 M backend/uv.lock
?? backend/app/domain/filing_sections.py
?? backend/tests/domain/test_filing_sections.py
```

A prior session built a filing **section extractor**:

- `backend/app/domain/filing_sections.py` — pure, no I/O. Two stages:
  (1) BeautifulSoup + lxml normalizes arbitrary filer HTML into
  block-structured plain text; (2) regex segmentation on Regulation S-K Item
  numbering (`Item 1A`, `Item 7`, Part-anchored for 10-Q). Also does
  priority-ordered budget fitting into `_MAX_FILING_CHARS = 300_000`, and
  flags "pointer" sections (under 1,000 chars — filers satisfying an Item by
  cross-reference rather than content).
- `EdgarService.get_filing_sections()` — caches the *parsed* result separately
  from raw text, parses in a worker thread via `anyio.to_thread.run_sync`.
- `ClaudeService._build_filing_attachment()` — sends extracted sections as the
  Citations document block, plus a `provenance_note()` telling the model which
  sections it did and didn't get.
- Deps added: `beautifulsoup4>=4.13`, `lxml>=5.3`, `anyio>=4.4`.

183 tests pass; `ruff format`, `ruff check`, and `mypy --strict` are clean.

## Why this is being reworked

The extractor works, but it optimized the wrong layer. Findings from running it
against 14 real filings from 7 filers (Apple, JPMorgan, P&G, Tesla, Coca-Cola,
UnitedHealth):

**1. The section allowlist is only a ~2× trim; BeautifulSoup did the real work.**

| | raw | after BS4 | after section filter |
|---|---|---|---|
| AAPL 10-K | 1.52 MB | 207 K (−86%) | 97 K (−53%) |
| KO 10-K | 3.76 MB | 601 K (−84%) | 234 K (−61%) |

A typical excerpt is still 24K–58K tokens, re-sent on every question, to
produce a 1024-token answer.

**2. Risk Factors is the largest and lowest-signal item in the allowlist** —
AAPL 68 K chars, TSLA 84 K, KO 92 K. Boilerplate, near-identical year over
year. Roughly 40% of the excerpt.

**3. Item 8 was excluded, but it's where the cross-references point.** Three of
seven filers defer Item 3 straight into the notes, which live in Item 8:
JPMorgan "Refer to **Note 30**"; UnitedHealth "incorporated by reference to …
**Note 12** … in **Part II, Item 8**"; Tesla "see **Note 13**". The pointer
detector announces a gap that the exclusion policy created.

**4. The verification sample was biased toward success** — all mega-caps with
professional document generators. Small caps, REITs, SPACs, 20-F foreign
issuers, and pre-2001 plain-text filings are untested and will be worse.

**5. No prompt caching** on a document block that is static, immutable, and
re-sent verbatim every question.

**6. The big miss: SEC publishes structured XBRL and we never looked.**
Confirmed live:

```
GET https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json
  → 200, 3.79 MB, taxonomies ['dei','us-gaap'], 503 us-gaap concepts

  RevenueFromContractWithCustomerExcludingAssessedTax, unit USD:
  {"start":"2024-09-29","end":"2025-09-27","val":416161000000,
   "accn":"0000320193-25-000079","fy":2025,"form":"10-K","filed":"2025-10-31"}

GET .../companyconcept/CIK0000320193/us-gaap/EarningsPerShareDiluted.json
  → 200, 48.7 KB
```

Every fact carries its **accession number** — machine-verifiable provenance
back to the source filing, which is *stronger* grounding than a quoted passage.
No parsing, no filer variation, same free unlimited EDGAR host with the same
`User-Agent` requirement. For the quantitative half of a filing, SEC already
solved the format-variation problem.

Known wrinkle: facts repeat across filings (FY2024 revenue appears under both
the FY2024 and FY2025 accessions as a prior-year comparative). Needs dedup on
`filed`/`accn`, and a decision about whether to prefer the original filing or
the latest restatement.

## What to build

Structured facts become the primary filing-derived grounding; narrative
extraction shrinks to only what XBRL can't express.

1. **`backend/app/services/xbrl_service.py`** — new provider service wrapping
   `companyconcept` and `companyfacts`. Goes through the existing shared EDGAR
   `httpx.AsyncClient` (the SEC `User-Agent` is baked in at construction in
   `app/main.py`) and the existing `fetch_with_cache` + `CacheRepository`
   pattern. Typed Pydantic schemas; facts carry `accn`, period, unit, and form
   so provenance survives to the UI. Needs a curated allowlist of us-gaap
   concepts — 503 are available and most are noise.

2. **Narrow the narrative policy** in `filing_sections.py` — keep Item 7 (MD&A)
   and 8-K bodies as the default; drop Item 1A (Risk Factors) from default
   context, available on explicit request. Keep stage 1 (BS4) unchanged; it's
   correct and needed regardless.

3. **Turn the pointer detector into a router.** When a section is flagged as a
   pointer to "Note N," resolve it — extract that note from Item 8 rather than
   just labeling the content as absent. This is the fix for finding 3.

4. **Add `cache_control: {"type": "ephemeral"}`** to the Citations document
   block in `claude_service.py`.

5. **Update the advisor's context assembly** so structured facts and narrative
   are distinguishable to the model, each with its accession-number provenance.

Deferred (do not build now, but design so it's not blocked): a pre-computed
cited digest per filing, generated once at ingest and cached indefinitely since
filings are immutable.

## Decide with me before implementing

- **Do XBRL facts surface on the dashboard, or stay advisor-only?** Surfacing
  them is a frontend/backend contract change; `CLAUDE.md` requires updating
  both sides together. Note the frontend currently consumes only
  `FilingMetadata` (`frontend/lib/types.ts`), never `FilingText`.
- **Which us-gaap concepts make the allowlist?**
- **Does this reduce or replace the FMP dependency?** FMP supplies computed
  ratios under a ~250 req/day free-tier cap; XBRL supplies the raw facts those
  ratios derive from, unlimited. Worth evaluating — it's the one provider with
  a real budget constraint.
- **Commit the existing extractor work first, or fold it into one change?**

## Environment notes

- The venv is **uv-managed and has no pip**. Use `uv sync` from `backend/`
  (with `$env:UV_PROJECT_ENVIRONMENT=".venv"`), and run tools as
  `.\.venv\Scripts\python.exe -m <tool>`.
- Gates, all currently clean — keep them that way:
  ```
  .\.venv\Scripts\python.exe -m ruff format .
  .\.venv\Scripts\python.exe -m ruff check .
  .\.venv\Scripts\python.exe -m mypy app tests
  .\.venv\Scripts\python.exe -m pytest -q
  ```
- Installed: `bs4 4.15.0` (ships `py.typed`, no stubs needed), `lxml 6.1.1`.
- **This machine sits behind a TLS-inspecting proxy.** Dev scripts that hit
  live SEC endpoints fail with `CERTIFICATE_VERIFY_FAILED` unless they use the
  Windows trust store:
  ```python
  ctx = ssl.create_default_context()
  ctx.load_default_certs(ssl.Purpose.SERVER_AUTH)
  httpx.Client(verify=ctx, headers={"User-Agent": "<descriptive UA>"})
  ```
  Tests must never do this — they mock everything via `respx`.
- Live-filing verification scripts from the prior session are in the scratchpad
  at `C:\Users\AVERY~1.REY\AppData\Local\Temp\claude\C--Users-avery-reynolds-Rundown\`
  `4bfaf2fe-1028-4f4d-91e5-7bf188cf8067\scratchpad\` (`verify_real_filings.py`,
  `check_xbrl.py`) — may be cleared; rewrite if gone.

## Definition of done

- XBRL facts reach the advisor with accession-number provenance and an "as of".
- Narrative context is materially smaller than today's 24K–58K tokens per
  question, and prompt-cached.
- Pointer sections resolve to their referenced notes rather than only being
  labeled.
- New domain/service logic is unit-tested against synthetic fixtures; no test
  touches a live API (`CLAUDE.md` testing rules).
- All four gates clean; frontend still type-checks if the contract changed.
- Verified against real filings from filers *outside* the mega-cap sample —
  include at least one small cap and one REIT.
