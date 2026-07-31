"""SEC XBRL integration: structured, per-filing-attributable financial facts.

SEC publishes the quantitative half of every filing as structured XBRL at
`data.sec.gov/api/xbrl/companyfacts/CIK##########.json` -- the same free,
unlimited host as the rest of EDGAR, under the same descriptive
`User-Agent` requirement, and therefore through the same shared
`httpx.AsyncClient` the lifespan constructs (see `app/main.py`). No
parsing, no filer-format variation, and every value carries the accession
number of the filing that reported it.

That last property is why this service exists. A quoted passage grounds a
claim only as well as the model located the passage; an accession number
is checkable. For anything numeric, this is stronger grounding than
narrative extraction can offer (CLAUDE.md hard rules 2 and 6).

Two caching decisions worth knowing
-----------------------------------
**The reduced result is cached, not the raw response.** `companyfacts` is
3.8 MB for a large filer and 503 concepts wide, of which the allowlist
wants ~18. Caching the raw blob would store megabytes per symbol and
re-run the reduction on every read. So the fetch, the JSON parse, and the
reduction all happen inside `fetch_live`, and what lands in the cache is
the handful of kilobytes the advisor actually sees -- mirroring how
`EdgarService` caches parsed `sections:` separately from raw `text:`.

**The cache key is the CIK alone, never the referenced filing.** Which
filing a question happens to be about must not fragment the cache, so
`from_referenced_filing` is applied *after* the read rather than baked
into the stored payload.
"""

import datetime as dt
import json
from typing import Any

import anyio.to_thread
import httpx

from app.cache.cache_repository import CacheRepository
from app.cache.ttl_policy import filings_ttl_seconds
from app.domain.xbrl_facts import SelectedFacts, select_facts
from app.schemas.common import SourcedValue
from app.schemas.xbrl import XbrlFact, XbrlFacts
from app.services.cache_through import fetch_with_cache
from app.services.edgar_service import EdgarService
from app.services.errors import ProviderFetchError

_PROVIDER = "xbrl"
_SOURCE_NAME = "SEC XBRL company facts"


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class XbrlService:
    """Fetches, reduces, and caches one filer's allowlisted XBRL facts."""

    def __init__(
        self, client: httpx.AsyncClient, cache: CacheRepository, edgar_service: EdgarService
    ) -> None:
        self._client = client
        self._cache = cache
        # Depends on EdgarService purely for ticker->CIK resolution. Doing
        # its own lookup would mean a second copy of SEC's ticker map
        # under a second cache key, and two places for the mapping to go
        # stale independently.
        self._edgar_service = edgar_service

    async def get_facts(
        self, symbol: str, *, referenced_accession: str | None = None
    ) -> SourcedValue[XbrlFacts]:
        """Return `symbol`'s allowlisted XBRL facts, cached per `ttl_policy`.

        Args:
            symbol: Ticker. Resolved to a CIK via `EdgarService`.
            referenced_accession: The filing the caller's question is
                about, if any. Facts reported by it come back with
                `from_referenced_filing` set, so the advisor can say "this
                filing reported" rather than only "the company reported"
                -- selection itself is symbol-wide, since a single
                filing's facts can't answer a question about a trend.

        Raises:
            ProviderNotFoundError: `symbol` isn't in SEC's ticker->CIK mapping.
            ProviderUnavailableError: SEC is failing and nothing is cached.
        """
        symbol = symbol.upper()
        cik = await self._edgar_service.resolve_cik(symbol)

        result = await fetch_with_cache(
            cache=self._cache,
            provider=_PROVIDER,
            cache_key=f"facts:{cik}",
            ttl_seconds=filings_ttl_seconds(),
            fetch_live=lambda: self._fetch_and_reduce(symbol, cik),
            clock=_utcnow,
        )

        snapshot = XbrlFacts.model_validate(result.payload)
        return SourcedValue(
            value=_flag_referenced_filing(snapshot, referenced_accession),
            source=_SOURCE_NAME,
            as_of=result.as_of,
            is_stale=result.is_stale,
        )

    async def _fetch_and_reduce(self, symbol: str, cik: str) -> dict[str, Any]:
        """Fetch `companyfacts`, reduce it to the allowlist, and return it JSON-ready.

        The reduction runs in a worker thread for the same reason
        `EdgarService` parses filings in one: deserializing and walking a
        multi-megabyte document is synchronous CPU work, and doing it
        inline would block the event loop -- and therefore every other
        in-flight request -- for its whole duration.
        """
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):0>10}.json"
        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderFetchError(f"SEC XBRL companyfacts request failed for {symbol}") from exc

        # `response.json()` is part of the CPU cost being moved off the
        # event loop, so it runs in the worker alongside the reduction
        # rather than here.
        selected = await anyio.to_thread.run_sync(_parse_and_select, response.content)
        return _to_schema(symbol, selected).model_dump(mode="json")


def _parse_and_select(raw: bytes) -> SelectedFacts:
    """Deserialize a `companyfacts` body and reduce it. Runs in a worker thread."""
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        # SEC returning a non-object here would be extraordinary, but an
        # empty selection is a better outcome than an AttributeError deep
        # inside the reduction.
        return SelectedFacts(facts=(), missing_labels=())
    return select_facts(payload)


def _to_schema(symbol: str, selected: SelectedFacts) -> XbrlFacts:
    """Map the domain layer's dataclasses onto the outward-facing schema."""
    return XbrlFacts(
        symbol=symbol,
        facts=[XbrlFact.model_validate(fact, from_attributes=True) for fact in selected.facts],
        missing_labels=list(selected.missing_labels),
    )


def _flag_referenced_filing(snapshot: XbrlFacts, referenced_accession: str | None) -> XbrlFacts:
    """Mark the facts reported by `referenced_accession`, if any.

    Applied post-cache deliberately: baking the flag into the stored
    payload would make the cache key depend on which filing the question
    referenced, so asking about two filings for one symbol would fetch
    `companyfacts` twice for identical data.
    """
    if referenced_accession is None:
        return snapshot
    return snapshot.model_copy(
        update={
            "facts": [
                fact.model_copy(
                    update={"from_referenced_filing": fact.accession_number == referenced_accession}
                )
                for fact in snapshot.facts
            ]
        }
    )
