"""Shared response-schema building blocks.

`SourcedValue` wraps a payload with its provenance: CLAUDE.md hard rule 6
requires every data point shown to the user to carry its source and an
"as of" timestamp, so every provider-facing response schema in this app
(portfolio, fundamentals, filings, news) wraps its payload in this one
type rather than each inventing its own "source"/"as_of" fields.

Originally scoped to U4 in the backend scaffold plan, but pulled forward
here (U5) since it's a generic, provider-independent building block that
FMP's fundamentals response needs too, and nothing about it is
SnapTrade-specific.
"""

from datetime import datetime

from pydantic import BaseModel


class SourcedValue[T](BaseModel):
    """A value tagged with where it came from and when it was fetched.

    `is_stale` distinguishes a fresh live-or-cached value from the
    Key Technical Decisions' stale-fallback case (a provider failure
    served from an expired cache entry) -- `as_of` alone would look
    identical to a fresh value with an old cache hit unless the frontend
    can also tell "this is stale because the provider is currently down."
    """

    value: T
    source: str
    as_of: datetime
    is_stale: bool = False
