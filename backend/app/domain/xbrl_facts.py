"""Selection of portfolio-relevant facts from SEC's XBRL company facts.

Pure functions over an already-parsed `companyfacts` payload -- no I/O,
no provider knowledge beyond SEC's own tag vocabulary -- so the entire
selection policy is testable against synthetic fixtures without touching
EDGAR (CLAUDE.md's rule for `app/domain/`).

Why this exists
---------------
`data.sec.gov/api/xbrl/companyfacts/CIK##########.json` returns every
concept a filer has ever tagged: 503 us-gaap concepts for Apple, in a
3.8 MB document. Most of it is noise for someone holding the stock --
segment breakdowns, tax-rate reconciliation lines, deprecated tags from a
decade ago. Handing all of it to the advisor would repeat the mistake
this work exists to correct: spending context on volume instead of
signal. So this module is the *selection policy*, kept deliberately
small and readable: an ordered allowlist, and the rules for turning
SEC's raw entries into one comparable value per concept per period.

The allowlist lives here rather than in `services/xbrl_service.py` for
the same reason `_TEN_K_POLICY` lives in `filing_sections.py` rather than
in `edgar_service.py`: which disclosures bear on a position is policy,
not transport.

Three properties of the source data drive the whole design:

1. **Filers disagree on tag names.** There is no single "revenue"
   concept. Post-ASC-606 filers use
   `RevenueFromContractWithCustomerExcludingAssessedTax`, pre-2018
   filings use `SalesRevenueNet`, banks report
   `RevenuesNetOfInterestExpense`. Each allowlist entry is therefore an
   *ordered chain* of tags, and the first one the filer actually
   reported wins.

2. **Duration vs instant.** Income-statement and cash-flow concepts
   cover a span and carry both `start` and `end`; balance-sheet concepts
   are a point in time and carry `end` only. That distinction is the
   dedup key, so conflating the two silently merges values that are not
   the same fact.

3. **Facts repeat across filings, and can disagree.** FY2024 revenue
   appears under the FY2024 accession as the current year and again
   under the FY2025 accession as a prior-year comparative -- with a
   different value if it was restated in between. `_latest_filed`
   resolves this: the most recently filed report wins, and the surviving
   fact keeps *that* filing's accession number, so the citation always
   points at the filing which actually reported the number being quoted.

What this deliberately cannot do
--------------------------------
XBRL covers the GAAP statements, not a filer's preferred non-GAAP
measures. A REIT's FFO/AFFO -- the figures it leads with -- are non-GAAP
and therefore absent from this taxonomy no matter what the allowlist
asks for. That is a real limit of structured facts, and the reason
narrative MD&A extraction stays in the picture rather than being
replaced outright.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Final, Literal

_Shape = Literal["duration", "instant"]
_DURATION: Final[_Shape] = "duration"
_INSTANT: Final[_Shape] = "instant"


@dataclass(frozen=True, slots=True)
class _ConceptSpec:
    """One allowlisted line item: what to call it, and how to find it.

    `tags` is an ordered fallback chain, most-preferred first -- see this
    module's docstring on why a single canonical tag name doesn't exist.
    """

    label: str
    tags: tuple[str, ...]
    unit: str
    shape: _Shape
    taxonomy: str = "us-gaap"


# Ordered by what a position holder actually asks about, and emitted in
# this order -- so the advisor's context reads top-line first rather than
# alphabetically. Adding a concept here is the intended way to widen
# coverage; nothing else needs to change.
_ALLOWLIST: Final[tuple[_ConceptSpec, ...]] = (
    # --- Income statement: duration, USD -----------------------------------
    _ConceptSpec(
        "Revenue",
        (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "Revenues",
            # Banks report revenue net of interest expense; without this
            # link in the chain a financial holding has no top line at all.
            "RevenuesNetOfInterestExpense",
            # Pre-ASC-606 filings, which still appear in the older end of
            # any multi-year history window.
            "SalesRevenueNet",
        ),
        "USD",
        _DURATION,
    ),
    _ConceptSpec("Gross profit", ("GrossProfit",), "USD", _DURATION),
    _ConceptSpec("Operating income", ("OperatingIncomeLoss",), "USD", _DURATION),
    _ConceptSpec(
        "Net income",
        (
            "NetIncomeLoss",
            # Net income *including* noncontrolling interests -- the only
            # bottom line some consolidated filers tag.
            "ProfitLoss",
        ),
        "USD",
        _DURATION,
    ),
    _ConceptSpec("R&D expense", ("ResearchAndDevelopmentExpense",), "USD", _DURATION),
    # --- Per share: duration, USD/shares -----------------------------------
    _ConceptSpec("EPS (basic)", ("EarningsPerShareBasic",), "USD/shares", _DURATION),
    _ConceptSpec("EPS (diluted)", ("EarningsPerShareDiluted",), "USD/shares", _DURATION),
    _ConceptSpec(
        "Dividends declared per share",
        (
            "CommonStockDividendsPerShareDeclared",
            # Filers who report what was actually paid per share rather
            # than what was declared.
            "CommonStockDividendsPerShareCashPaid",
        ),
        "USD/shares",
        _DURATION,
    ),
    # --- Balance sheet: instant, USD ---------------------------------------
    _ConceptSpec("Total assets", ("Assets",), "USD", _INSTANT),
    _ConceptSpec("Total liabilities", ("Liabilities",), "USD", _INSTANT),
    _ConceptSpec(
        "Shareholders' equity",
        (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        "USD",
        _INSTANT,
    ),
    _ConceptSpec(
        "Cash and equivalents",
        (
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ),
        "USD",
        _INSTANT,
    ),
    _ConceptSpec(
        "Long-term debt",
        (
            # Total carrying amount, current portion included. Ordered
            # ahead of the noncurrent-only slice deliberately: a filer who
            # tags both should give us the whole debt load, not the part
            # that happens to fall due beyond a year.
            "LongTermDebt",
            "LongTermDebtNoncurrent",
        ),
        "USD",
        _INSTANT,
    ),
    # --- Cash flow: duration, USD ------------------------------------------
    _ConceptSpec(
        "Operating cash flow",
        (
            "NetCashProvidedByUsedInOperatingActivities",
            # Filers with discontinued operations split the statement and
            # tag only the continuing-operations line.
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ),
        "USD",
        _DURATION,
    ),
    # The quantitative half of Item 5 (issuer purchases of equity
    # securities), which the narrative policy keeps but which is mostly a
    # table anyway.
    _ConceptSpec("Share repurchases", ("PaymentsForRepurchaseOfCommonStock",), "USD", _DURATION),
    _ConceptSpec(
        "Dividends paid",
        (
            "PaymentsOfDividendsCommonStock",
            # Undifferentiated total (common, preferred, and minority
            # interests together) -- the only dividend outflow many filers
            # tag.
            "PaymentsOfDividends",
        ),
        "USD",
        _DURATION,
    ),
    # --- Share counts ------------------------------------------------------
    _ConceptSpec(
        "Diluted shares outstanding",
        ("WeightedAverageNumberOfDilutedSharesOutstanding",),
        "shares",
        _DURATION,
    ),
    _ConceptSpec(
        "Shares outstanding (cover page)",
        ("EntityCommonStockSharesOutstanding",),
        "shares",
        _INSTANT,
        taxonomy="dei",
    ),
)

#: Every label this module can produce, in emission order. Public so
#: callers can describe the full scope of what was asked for without
#: reaching into `_ALLOWLIST` -- and so tests assert the "every concept is
#: either found or reported missing" invariant against the allowlist
#: itself rather than a hardcoded count that breaks whenever it's edited.
ALLOWLIST_LABELS: Final[tuple[str, ...]] = tuple(spec.label for spec in _ALLOWLIST)

DEFAULT_ANNUAL_PERIODS: Final = 5
DEFAULT_QUARTERLY_PERIODS: Final = 4

# Duration facts are bucketed by the length of the period they cover,
# *not* by the form that reported them. A fiscal year is a fiscal year
# whether it was first reported in a 10-K or restated in a later 10-Q --
# and since `_latest_filed` can hand a year-end figure to a 10-Q, form is
# not a safe bucketing signal.
#
# The ranges are wide because fiscal years aren't 365 days: 52/53-week
# retail calendars, transition periods after a year-end change, and
# leap years all drift the span.
_ANNUAL_SPAN_DAYS: Final = range(300, 401)
_QUARTERLY_SPAN_DAYS: Final = range(60, 121)

# Instant concepts have no span to measure, so the annual series is
# identified by the form that reported the date instead. Matched as a
# prefix to catch amendments and legacy suffixes (`10-K/A`, `10-K405`).
_ANNUAL_FORM_PREFIX: Final = "10-K"


@dataclass(frozen=True, slots=True)
class SelectedFact:
    """One reported value for one concept in one period, with its source filing."""

    label: str
    concept: str
    taxonomy: str
    value: Decimal
    unit: str
    period_start: dt.date | None
    period_end: dt.date
    fiscal_year: int | None
    fiscal_period: str | None
    form: str
    accession_number: str
    filed: dt.date


@dataclass(frozen=True, slots=True)
class _Candidate:
    """A fact plus the one thing about its *sources* the window fitter needs.

    `reported_annually` is true when **any** filing that reported this
    period was an annual report. It cannot be recovered from the surviving
    fact's own `form`: a 10-Q's balance sheet carries the prior fiscal
    year-end as its comparative column, and being filed later that copy
    wins `_latest_filed` -- so a genuine year-end date ends up stamped
    `10-Q`. Tracking it across duplicates instead is what lets
    balance-sheet history reach as far back as income-statement history.
    """

    fact: SelectedFact
    reported_annually: bool


@dataclass(frozen=True, slots=True)
class SelectedFacts:
    """Every allowlisted fact found for one filer, plus what wasn't found.

    `missing_labels` carries the same weight here as
    `FilingDocument.omitted_labels` does for narrative sections: without
    it, CLAUDE.md hard rule 2's "say so when the context doesn't cover
    something" makes the model report that the *company* never disclosed
    a figure when in fact only this allowlist didn't ask for it.
    """

    facts: tuple[SelectedFact, ...]
    missing_labels: tuple[str, ...]


def select_facts(
    payload: dict[str, Any],
    *,
    annual_periods: int = DEFAULT_ANNUAL_PERIODS,
    quarterly_periods: int = DEFAULT_QUARTERLY_PERIODS,
) -> SelectedFacts:
    """Reduce a `companyfacts` payload to the allowlisted facts worth grounding on.

    Args:
        payload: A parsed `companyfacts` response. Only `payload["facts"]`
            is read; a malformed or partial document yields fewer facts
            rather than an exception, since one filer's odd tagging must
            not take down the advisor.
        annual_periods: How many fiscal years to keep per concept.
        quarterly_periods: How many quarters to keep per concept.

    Returns:
        Facts in allowlist order, newest period first within each concept.

    Raises:
        ValueError: if either period count is negative.
    """
    if annual_periods < 0 or quarterly_periods < 0:
        raise ValueError(
            "Period counts must be non-negative, got "
            f"annual_periods={annual_periods}, quarterly_periods={quarterly_periods}."
        )

    taxonomies = payload.get("facts") or {}
    facts: list[SelectedFact] = []
    missing: list[str] = []

    for spec in _ALLOWLIST:
        resolved = _resolve_tag(taxonomies, spec)
        if resolved is None:
            missing.append(spec.label)
            continue

        tag, entries = resolved
        candidates = [
            candidate
            for candidate in (_build_fact(spec, tag, entry) for entry in entries)
            if candidate is not None
        ]
        kept = _fit_window(
            _latest_filed(candidates, shape=spec.shape),
            shape=spec.shape,
            annual_periods=annual_periods,
            quarterly_periods=quarterly_periods,
        )
        # A tag can resolve and still yield nothing usable -- e.g. a filer
        # who only ever reported year-to-date spans for it. That's an
        # absence the advisor still has to be told about.
        if not kept:
            missing.append(spec.label)
            continue

        facts.extend(kept)

    return SelectedFacts(facts=tuple(facts), missing_labels=tuple(missing))


def _resolve_tag(
    taxonomies: dict[str, Any], spec: _ConceptSpec
) -> tuple[str, list[dict[str, Any]]] | None:
    """Walk `spec.tags` in order and return the first one this filer reported."""
    concepts = taxonomies.get(spec.taxonomy) or {}
    for tag in spec.tags:
        units = (concepts.get(tag) or {}).get("units") or {}
        entries = units.get(spec.unit)
        if entries:
            return tag, list(entries)
    return None


def _build_fact(spec: _ConceptSpec, tag: str, entry: dict[str, Any]) -> _Candidate | None:
    """Convert one raw `units[...]` entry into a `_Candidate`, or `None` if unusable.

    Returns `None` rather than raising on anything malformed or
    out-of-shape: a single odd entry should cost one data point, not the
    whole concept.
    """
    period_end = _parse_date(entry.get("end"))
    filed = _parse_date(entry.get("filed"))
    value = _parse_decimal(entry.get("val"))
    accession_number = entry.get("accn")
    form = entry.get("form")

    if period_end is None or filed is None or value is None:
        return None
    if not isinstance(accession_number, str) or not isinstance(form, str):
        return None

    period_start = _parse_date(entry.get("start"))
    if spec.shape == _DURATION:
        if period_start is None:
            return None
        # Drops year-to-date spans (a 10-Q reports both the three-month
        # and the six/nine-month figure for the same `end`, distinguished
        # only by `start`). Keeping both would sit a Q3 number next to a
        # nine-month number with nothing but dates to tell them apart.
        span_days = (period_end - period_start).days
        if span_days not in _ANNUAL_SPAN_DAYS and span_days not in _QUARTERLY_SPAN_DAYS:
            return None
    else:
        # Instant concepts have no span; SEC omits `start`, but don't
        # trust that and carry a stray value into the period fields.
        period_start = None

    fiscal_year = entry.get("fy")
    fiscal_period = entry.get("fp")
    return _Candidate(
        fact=SelectedFact(
            label=spec.label,
            concept=tag,
            taxonomy=spec.taxonomy,
            value=value,
            unit=spec.unit,
            period_start=period_start,
            period_end=period_end,
            fiscal_year=fiscal_year if isinstance(fiscal_year, int) else None,
            fiscal_period=fiscal_period if isinstance(fiscal_period, str) else None,
            form=form,
            accession_number=accession_number,
            filed=filed,
        ),
        reported_annually=form.upper().startswith(_ANNUAL_FORM_PREFIX),
    )


def _latest_filed(candidates: list[_Candidate], *, shape: _Shape) -> list[_Candidate]:
    """Collapse repeated reports of the same period, keeping the latest filed.

    The accession number is the tiebreak purely so the result is
    deterministic when two filings share a `filed` date -- without it,
    which of two equally-recent reports wins would depend on dict
    ordering in SEC's response.

    `reported_annually` is OR'd across every duplicate rather than taken
    from the winner, so a year-end balance restated by a later 10-Q is
    still recognized as a year-end. Only the *value* is a contest; being
    reported annually is a property of the period itself.
    """
    best: dict[tuple[dt.date | None, dt.date], _Candidate] = {}
    for candidate in candidates:
        fact = candidate.fact
        key = (
            (fact.period_start, fact.period_end) if shape == _DURATION else (None, fact.period_end)
        )
        incumbent = best.get(key)
        if incumbent is None:
            best[key] = candidate
            continue
        winner = (
            candidate
            if (fact.filed, fact.accession_number)
            > (incumbent.fact.filed, incumbent.fact.accession_number)
            else incumbent
        )
        best[key] = _Candidate(
            fact=winner.fact,
            reported_annually=candidate.reported_annually or incumbent.reported_annually,
        )
    return list(best.values())


def _fit_window(
    candidates: list[_Candidate],
    *,
    shape: _Shape,
    annual_periods: int,
    quarterly_periods: int,
) -> list[SelectedFact]:
    """Trim to the most recent N annual and N quarterly periods, newest first."""
    by_recency = sorted(candidates, key=lambda candidate: candidate.fact.period_end, reverse=True)

    if shape == _INSTANT:
        # A balance-sheet date has no span, so the annual series is the
        # dates a 10-K reported and the quarterly series is simply the
        # most recent dates. Taking the N most recent overall instead
        # would cap balance-sheet history at roughly two years for any
        # filer who reports quarterly -- while revenue got five.
        chosen: dict[dt.date, SelectedFact] = {}
        annual_dates = [c for c in by_recency if c.reported_annually][:annual_periods]
        for candidate in annual_dates + by_recency[:quarterly_periods]:
            chosen.setdefault(candidate.fact.period_end, candidate.fact)
        return sorted(chosen.values(), key=lambda fact: fact.period_end, reverse=True)

    facts = [candidate.fact for candidate in by_recency]
    annual = [fact for fact in facts if _span_days(fact) in _ANNUAL_SPAN_DAYS][:annual_periods]
    quarterly = [fact for fact in facts if _span_days(fact) in _QUARTERLY_SPAN_DAYS][
        :quarterly_periods
    ]
    return sorted(annual + quarterly, key=lambda fact: fact.period_end, reverse=True)


def _span_days(fact: SelectedFact) -> int:
    """Length of `fact`'s period, or `-1` for an instant fact (in no span range)."""
    if fact.period_start is None:
        return -1
    return (fact.period_end - fact.period_start).days


def _parse_date(raw: object) -> dt.date | None:
    if not isinstance(raw, str):
        return None
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        return None


def _parse_decimal(raw: object) -> Decimal | None:
    """Parse a reported value, via `str` so float binary error never enters a Decimal.

    `bool` is excluded explicitly because it's an `int` subclass in
    Python, and `Decimal(str(True))` would raise rather than quietly
    producing 1 -- but rejecting it here keeps the failure at the parse
    boundary where every other malformed entry is handled.
    """
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    try:
        return Decimal(str(raw))
    except InvalidOperation:
        return None
