"""Schemas for SEC XBRL company facts -- the structured half of a filing.

Not currently returned by any route: XBRL facts reach the user only
through the advisor's grounded context (the decision on this change was
advisor-only for now). These are still Pydantic models rather than raw
dicts, per CLAUDE.md's "no raw dicts crossing the API boundary" -- the
boundary they cross is `XbrlService` -> `ClaudeService`, and surfacing
them on a route later should be additive, not a rewrite.

Every fact carries its own `accession_number`, `form`, and `filed` date.
That is the whole reason this data is worth having: provenance is
machine-verifiable back to a specific filing rather than resting on a
quoted passage the model had to locate correctly (CLAUDE.md hard rules 2
and 6).
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class XbrlFact(BaseModel):
    """One reported value for one concept in one period, with its source filing."""

    label: str
    concept: str
    taxonomy: str
    value: Decimal
    unit: str

    # `None` for instant concepts (balance-sheet items are a point in
    # time, not a span). Duration concepts -- income statement, cash flow
    # -- always carry both.
    period_start: date | None
    period_end: date

    fiscal_year: int | None
    fiscal_period: str | None
    form: str
    accession_number: str
    filed: date

    # True when this value was reported by the filing the user's question
    # references, as opposed to an earlier/later filing in the history
    # window. Facts are symbol-scoped so the advisor can speak to trends;
    # this flag is what lets it still distinguish "this filing said" from
    # "the company has reported".
    from_referenced_filing: bool = False


class XbrlFacts(BaseModel):
    """Every allowlisted fact found for one symbol, plus what wasn't found.

    `missing_labels` exists for the same reason
    `FilingDocument.omitted_labels` does: without it, CLAUDE.md hard rule
    2's "say so when the context doesn't cover something" makes the model
    report that the *company* never disclosed a figure when in fact only
    this allowlist didn't ask for it. A filer that reports no R&D, or a
    REIT whose headline metric is non-GAAP and therefore absent from XBRL
    entirely, is an ordinary case -- not an error.
    """

    symbol: str
    facts: list[XbrlFact]
    missing_labels: list[str]
