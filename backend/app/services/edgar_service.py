"""SEC EDGAR integration: filing metadata and full text.

Every request goes through one shared `httpx.AsyncClient` constructed in
the lifespan with SEC's required descriptive `User-Agent` header baked in
at the client level -- `data.sec.gov` returns 403 without one (see
`app/main.py`). This service calls both `www.sec.gov` (ticker mapping,
raw filing archives) and `data.sec.gov` (the submissions API) through
that same client; the header applies to every request regardless of
host, since it's set once at client construction rather than per-call.

Everything here is cached via `cache_through.fetch_with_cache` with a
long TTL, since published filing text and filing lists never change once
filed (only the ticker->CIK mapping can drift, and even that rarely).
"""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import anyio.to_thread
import httpx

from app.cache.cache_repository import CacheRepository
from app.cache.ttl_policy import filings_ttl_seconds
from app.domain.filing_sections import SegmentedFiling, segment_filing
from app.schemas.common import SourcedValue
from app.schemas.filings import FilingMetadata, FilingText
from app.services.cache_through import CachedResult, fetch_with_cache
from app.services.errors import ProviderFetchError, ProviderNotFoundError

_PROVIDER = "edgar"
_SOURCE_NAME = "SEC EDGAR"
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"

# The plan scopes this to 10-K/10-Q/8-K specifically; SEC's `filings.recent`
# feed includes every form type a company has ever filed.
_TRACKED_FORMS = ("10-K", "10-Q", "8-K")

# "Recent" per the plan's own framing, not an exhaustive filing history --
# capping keeps the response small for a company with decades of filings.
_MAX_RECENT_FILINGS = 20


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@dataclass(frozen=True, slots=True)
class _LocatedFiling:
    """One filing pinned down to a fetchable archive URL."""

    form: str
    archive_url: str
    submissions: CachedResult


class EdgarService:
    """Resolves tickers to CIKs and fetches filing metadata/text, all cached."""

    def __init__(self, client: httpx.AsyncClient, cache: CacheRepository) -> None:
        self._client = client
        self._cache = cache

    async def list_filings(self, symbol: str) -> SourcedValue[list[FilingMetadata]]:
        """Return `symbol`'s most recent 10-K/10-Q/8-K filings.

        Raises:
            ProviderNotFoundError: `symbol` isn't in SEC's ticker->CIK mapping.
            ProviderUnavailableError: EDGAR is failing and nothing is cached.
        """
        cik = await self.resolve_cik(symbol)
        submissions = await self._fetch_submissions(cik)
        recent = submissions.payload["filings"]["recent"]

        filings = [
            FilingMetadata(
                form=recent["form"][i],
                filing_date=recent["filingDate"][i],
                accession_number=recent["accessionNumber"][i],
                primary_document=recent["primaryDocument"][i],
            )
            for i in range(len(recent["form"]))
            if recent["form"][i] in _TRACKED_FORMS
        ][:_MAX_RECENT_FILINGS]

        return SourcedValue(
            value=filings,
            source=_SOURCE_NAME,
            as_of=submissions.as_of,
            is_stale=submissions.is_stale,
        )

    async def get_filing_text(self, symbol: str, accession_number: str) -> SourcedValue[FilingText]:
        """Return the raw text/HTML of one specific filing.

        Raises:
            ProviderNotFoundError: `symbol` isn't known, or
                `accession_number` doesn't match any of `symbol`'s filings.
            ProviderUnavailableError: EDGAR is failing and nothing is cached.
        """
        located = await self._locate_filing(symbol, accession_number)

        text_result = await fetch_with_cache(
            cache=self._cache,
            provider=_PROVIDER,
            cache_key=f"text:{accession_number}",
            ttl_seconds=filings_ttl_seconds(),
            fetch_live=lambda: self._fetch_text(located.archive_url),
            clock=_utcnow,
        )

        return SourcedValue(
            value=FilingText(
                accession_number=accession_number, form=located.form, text=text_result.payload
            ),
            source=_SOURCE_NAME,
            as_of=text_result.as_of,
            is_stale=text_result.is_stale,
        )

    async def get_filing_sections(
        self, symbol: str, accession_number: str
    ) -> SourcedValue[SegmentedFiling]:
        """Return one filing's portfolio-relevant Item sections, parsed and cached.

        Cached as the *parsed* result, separately from `text:` -- parsing
        a large inline-XBRL 10-K is seconds of CPU, and the advisor would
        otherwise pay it on every question about the same filing. Filing
        text never changes once published, so the parse is cacheable for
        exactly as long as the text is.

        The parse itself runs in a worker thread: BeautifulSoup is
        synchronous CPU work, and doing it inline would block the event
        loop (and therefore every other in-flight request) for its whole
        duration.

        Raises:
            ProviderNotFoundError: `symbol` isn't known, or
                `accession_number` doesn't match any of `symbol`'s filings.
            ProviderUnavailableError: EDGAR is failing and nothing is cached.
        """
        located = await self._locate_filing(symbol, accession_number)

        result = await fetch_with_cache(
            cache=self._cache,
            provider=_PROVIDER,
            cache_key=f"sections:{accession_number}",
            ttl_seconds=filings_ttl_seconds(),
            fetch_live=lambda: self._fetch_and_segment(located.archive_url, located.form),
            clock=_utcnow,
        )

        return SourcedValue(
            value=SegmentedFiling.from_cacheable(result.payload),
            source=_SOURCE_NAME,
            as_of=result.as_of,
            is_stale=result.is_stale,
        )

    async def _locate_filing(self, symbol: str, accession_number: str) -> _LocatedFiling:
        cik = await self.resolve_cik(symbol)
        submissions = await self._fetch_submissions(cik)
        recent = submissions.payload["filings"]["recent"]

        try:
            index = recent["accessionNumber"].index(accession_number)
        except ValueError as exc:
            raise ProviderNotFoundError(_PROVIDER, accession_number) from exc

        primary_document = recent["primaryDocument"][index]
        return _LocatedFiling(
            form=recent["form"][index],
            archive_url=(
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                f"{accession_number.replace('-', '')}/{primary_document}"
            ),
            submissions=submissions,
        )

    async def _fetch_and_segment(self, archive_url: str, form: str) -> dict[str, Any]:
        raw = await self._fetch_text(archive_url)
        segmented = await anyio.to_thread.run_sync(segment_filing, raw, form)
        return segmented.to_cacheable()

    async def resolve_cik(self, symbol: str) -> str:
        """Map a ticker to its SEC CIK, via the cached ticker->CIK mapping.

        Public because `XbrlService` needs the same mapping: SEC's XBRL
        endpoints are keyed by CIK, not ticker. Sharing this method rather
        than duplicating the lookup means both services read one cache
        entry under one key, so a symbol resolved for a filing costs
        nothing to resolve again for its facts.

        Raises:
            ProviderNotFoundError: `symbol` isn't in SEC's ticker->CIK mapping.
            ProviderUnavailableError: EDGAR is failing and nothing is cached.
        """
        symbol = symbol.upper()
        ticker_map = await self._ticker_map()
        entry = ticker_map.get(symbol)
        if entry is None:
            raise ProviderNotFoundError(_PROVIDER, symbol)
        return entry["cik"]

    async def resolve_company_names(self, symbols: Sequence[str]) -> dict[str, str]:
        """Best-effort company-name lookup for `symbols`, from the same cache `resolve_cik` reads.

        Unlike `resolve_cik`, a symbol absent from SEC's mapping (some
        ETFs, for instance) is silently omitted rather than raised --
        callers use this to enrich question-matching
        (`app.domain.symbol_matching`), where a missing name just means
        that symbol matches on its ticker alone, not an error.

        Returns:
            `{symbol: title}` for every symbol found, keyed by the symbol
            exactly as passed in `symbols` (not upper-cased). Symbols not
            found in SEC's mapping are omitted, not raised.
        """
        if not symbols:
            return {}
        ticker_map = await self._ticker_map()
        names: dict[str, str] = {}
        for symbol in symbols:
            entry = ticker_map.get(symbol.upper())
            if entry is not None:
                names[symbol] = entry["title"]
        return names

    async def _ticker_map(self) -> dict[str, dict[str, str]]:
        # Deliberately doesn't propagate this fetch's own `is_stale` into
        # the caller's overall result: a CIK or registered name, once
        # assigned to a public company, effectively never changes, so a
        # stale-fallback ticker map is functionally identical to a fresh
        # one for any symbol it already contains. `list_filings`/
        # `get_filing_text` report staleness from the submissions/text
        # fetch instead, which is where a real, user-visible staleness
        # difference (an outdated filing list) could actually occur.
        result = await fetch_with_cache(
            cache=self._cache,
            provider=_PROVIDER,
            # "_v2": the cached payload shape changed from `dict[str, str]`
            # (ticker -> CIK) to `dict[str, dict[str, str]]` (ticker ->
            # {"cik", "title"}). A bumped key means a pre-existing cache row
            # in the old shape is a clean miss -- triggering a fresh live
            # fetch -- rather than being read back and indexed as a dict
            # when it's actually a plain string.
            cache_key="ticker_cik_map_v2",
            ttl_seconds=filings_ttl_seconds(),
            fetch_live=self._fetch_ticker_map,
            clock=_utcnow,
        )
        payload: dict[str, dict[str, str]] = result.payload
        return payload

    async def _fetch_ticker_map(self) -> dict[str, dict[str, str]]:
        """Ticker -> `{"cik": ..., "title": ...}`.

        A plain-dict payload, not a dataclass: `CacheRepository.set` requires
        a JSON-serializable payload as-is, and a dataclass instance isn't.
        """
        try:
            response = await self._client.get(_TICKER_MAP_URL)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderFetchError("EDGAR ticker mapping request failed") from exc

        raw = response.json()
        return {
            entry["ticker"].upper(): {"cik": str(entry["cik_str"]), "title": entry["title"]}
            for entry in raw.values()
        }

    async def _fetch_submissions(self, cik: str) -> CachedResult:
        return await fetch_with_cache(
            cache=self._cache,
            provider=_PROVIDER,
            cache_key=f"submissions:{cik}",
            ttl_seconds=filings_ttl_seconds(),
            fetch_live=lambda: self._fetch_submissions_live(cik),
            clock=_utcnow,
        )

    async def _fetch_submissions_live(self, cik: str) -> dict[str, Any]:
        url = f"https://data.sec.gov/submissions/CIK{int(cik):0>10}.json"
        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderFetchError(f"EDGAR submissions request failed for CIK {cik}") from exc
        return response.json()  # type: ignore[no-any-return]

    async def _fetch_text(self, url: str) -> str:
        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderFetchError(f"EDGAR filing text request failed for {url}") from exc
        return response.text
