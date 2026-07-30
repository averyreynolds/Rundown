"""Tests for `app.services.edgar_service.EdgarService`.

All EDGAR HTTP calls are mocked via `respx` -- this suite never touches
the live network.
"""

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cache.cache_repository import CacheRepository
from app.services.edgar_service import EdgarService
from app.services.errors import ProviderNotFoundError, ProviderUnavailableError
from tests.fixtures.synthetic_filing import (
    SYNTHETIC_FILING_TEXT,
    SYNTHETIC_TICKER_MAP,
    synthetic_submissions,
)

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK0000320193.json"
_FILING_TEXT_URL = (
    "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/synthetic-10k.htm"
)


@pytest.fixture
async def client():
    async with httpx.AsyncClient(headers={"User-Agent": "Rundown Test (test@example.com)"}) as c:
        yield c


def _mock_ticker_map_and_submissions() -> None:
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    respx.get(_SUBMISSIONS_URL).mock(return_value=httpx.Response(200, json=synthetic_submissions()))


@respx.mock
async def test_list_filings_returns_tracked_forms_only(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _mock_ticker_map_and_submissions()

    async with db_session_factory() as session:
        result = await EdgarService(client=client, cache=CacheRepository(session)).list_filings(
            "synt"
        )

    forms = [f.form for f in result.value]
    assert forms == ["10-K", "10-Q", "8-K"]  # S-8 filtered out
    assert result.source == "SEC EDGAR"
    assert result.value[0].accession_number == "0000320193-24-000123"


@respx.mock
async def test_get_filing_text_returns_raw_text(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _mock_ticker_map_and_submissions()
    respx.get(_FILING_TEXT_URL).mock(return_value=httpx.Response(200, text=SYNTHETIC_FILING_TEXT))

    async with db_session_factory() as session:
        result = await EdgarService(client=client, cache=CacheRepository(session)).get_filing_text(
            "SYNT", "0000320193-24-000123"
        )

    assert result.value.text == SYNTHETIC_FILING_TEXT
    assert result.value.form == "10-K"


@respx.mock
async def test_unknown_ticker_raises_provider_not_found(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))

    async with db_session_factory() as session:
        with pytest.raises(ProviderNotFoundError):
            await EdgarService(client=client, cache=CacheRepository(session)).list_filings(
                "NOTREAL"
            )


@respx.mock
async def test_unknown_accession_number_raises_provider_not_found(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _mock_ticker_map_and_submissions()

    async with db_session_factory() as session:
        with pytest.raises(ProviderNotFoundError):
            await EdgarService(client=client, cache=CacheRepository(session)).get_filing_text(
                "SYNT", "0000000000-00-000000"
            )


@respx.mock
async def test_every_request_carries_the_required_user_agent_header(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    ticker_route = respx.get(_TICKER_MAP_URL).mock(
        return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP)
    )
    submissions_route = respx.get(_SUBMISSIONS_URL).mock(
        return_value=httpx.Response(200, json=synthetic_submissions())
    )

    async with db_session_factory() as session:
        await EdgarService(client=client, cache=CacheRepository(session)).list_filings("SYNT")

    for route in (ticker_route, submissions_route):
        assert route.calls.last.request.headers["User-Agent"] == "Rundown Test (test@example.com)"


@respx.mock
async def test_provider_error_with_no_cache_raises_provider_unavailable(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(403))

    async with db_session_factory() as session:
        with pytest.raises(ProviderUnavailableError):
            await EdgarService(client=client, cache=CacheRepository(session)).list_filings("SYNT")


@respx.mock
async def test_provider_error_with_existing_cache_returns_stale_labeled_value(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A submissions-fetch failure with a cached (now-expired) entry falls back to it.

    Targets the *submissions* cache specifically, not the ticker map: the
    ticker map's own staleness deliberately isn't propagated into
    `is_stale` (see `EdgarService._resolve_cik`'s docstring comment) since
    a CIK never changes once assigned, so that cache layer would never
    flip this flag.
    """
    _mock_ticker_map_and_submissions()

    async with db_session_factory() as session:
        repo = CacheRepository(session)
        await EdgarService(client=client, cache=repo).list_filings("SYNT")
        # Force the submissions cache entry to be treated as expired.
        cached_payload = await repo.get_or_none("edgar", "submissions:320193")
        await repo.set("edgar", "submissions:320193", cached_payload, ttl_seconds=0)

    respx.get(_SUBMISSIONS_URL).mock(return_value=httpx.Response(503))

    async with db_session_factory() as session:
        result = await EdgarService(client=client, cache=CacheRepository(session)).list_filings(
            "SYNT"
        )

    assert result.is_stale is True
