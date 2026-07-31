"""Tests for `app.services.xbrl_service.XbrlService`.

Every SEC call is mocked via `respx`; this suite never touches the live
network or spends any rate-limit budget (CLAUDE.md's testing rules).

Two behaviours here matter more than the happy path. The first is that a
`Decimal` survives the JSON cache round-trip intact -- these are the
numbers a user reads as their own money, and a float detour would corrupt
them silently. The second is that the cache key depends on the CIK alone:
asking about two different filings for one symbol must not fetch a 3.8 MB
document twice.
"""

from decimal import Decimal

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cache.cache_repository import CacheRepository
from app.schemas.xbrl import XbrlFacts
from app.services.edgar_service import EdgarService
from app.services.errors import ProviderNotFoundError, ProviderUnavailableError
from app.services.xbrl_service import XbrlService
from tests.fixtures.synthetic_filing import SYNTHETIC_TICKER_MAP
from tests.fixtures.synthetic_xbrl import (
    ACCN_FY2025_10K,
    ACCN_Q2_10Q,
    synthetic_company_facts,
)

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
_CACHE_KEY = "facts:320193"


@pytest.fixture
async def client():
    async with httpx.AsyncClient(headers={"User-Agent": "Rundown Test (test@example.com)"}) as c:
        yield c


def _mock_ticker_map() -> None:
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))


def _mock_company_facts() -> respx.Route:
    return respx.get(_COMPANY_FACTS_URL).mock(
        return_value=httpx.Response(200, json=synthetic_company_facts())
    )


def _service(client: httpx.AsyncClient, session: AsyncSession) -> XbrlService:
    cache = CacheRepository(session)
    return XbrlService(
        client=client,
        cache=cache,
        edgar_service=EdgarService(client=client, cache=cache),
    )


# --- Happy path -------------------------------------------------------------


@respx.mock
async def test_returns_allowlisted_facts_for_the_resolved_cik(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _mock_ticker_map()
    facts_route = _mock_company_facts()

    async with db_session_factory() as session:
        result = await _service(client, session).get_facts("SYNT")

    assert facts_route.called
    assert result.source == "SEC XBRL company facts"
    assert result.is_stale is False
    assert result.value.symbol == "SYNT"
    assert {fact.label for fact in result.value.facts} >= {"Revenue", "Total assets"}


@respx.mock
async def test_symbol_is_normalized_before_resolution(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _mock_ticker_map()
    _mock_company_facts()

    async with db_session_factory() as session:
        result = await _service(client, session).get_facts("synt")

    assert result.value.symbol == "SYNT"


@respx.mock
async def test_every_fact_carries_its_own_filing_provenance(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The whole reason to prefer XBRL over quoted prose: an accession
    number is checkable, a located passage is only as good as the model's
    aim."""
    _mock_ticker_map()
    _mock_company_facts()

    async with db_session_factory() as session:
        result = await _service(client, session).get_facts("SYNT")

    assert result.value.facts
    for fact in result.value.facts:
        assert fact.accession_number
        assert fact.form
        assert fact.filed


@respx.mock
async def test_absences_survive_the_cache_round_trip(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Hard rule 2 depends on these: losing `missing_labels` in
    serialization would make the advisor claim the company never disclosed
    a figure nobody asked for."""
    _mock_ticker_map()
    _mock_company_facts()

    async with db_session_factory() as session:
        result = await _service(client, session).get_facts("SYNT")

    assert "R&D expense" in result.value.missing_labels


@respx.mock
async def test_decimal_precision_survives_the_cache_round_trip(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A float detour would turn 0.1 into 0.1000000000000000055..."""
    _mock_ticker_map()
    _mock_company_facts()

    async with db_session_factory() as session:
        result = await _service(client, session).get_facts("SYNT")

    eps = [fact for fact in result.value.facts if fact.label == "EPS (diluted)"]
    assert [str(fact.value) for fact in eps] == ["0.1"]
    assert all(isinstance(fact.value, Decimal) for fact in result.value.facts)


# --- Caching ----------------------------------------------------------------


@respx.mock
async def test_second_call_reads_the_cache_instead_of_refetching(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _mock_ticker_map()
    facts_route = _mock_company_facts()

    async with db_session_factory() as session:
        service = _service(client, session)
        await service.get_facts("SYNT")
        await service.get_facts("SYNT")

    assert facts_route.call_count == 1


@respx.mock
async def test_differing_referenced_filings_do_not_fragment_the_cache(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The reason `from_referenced_filing` is applied after the read: two
    questions about two filings for one symbol are one fetch."""
    _mock_ticker_map()
    facts_route = _mock_company_facts()

    async with db_session_factory() as session:
        service = _service(client, session)
        first = await service.get_facts("SYNT", referenced_accession=ACCN_FY2025_10K)
        second = await service.get_facts("SYNT", referenced_accession=ACCN_Q2_10Q)

    assert facts_route.call_count == 1
    assert {fact.accession_number for fact in first.value.facts if fact.from_referenced_filing} == {
        ACCN_FY2025_10K
    }
    assert {
        fact.accession_number for fact in second.value.facts if fact.from_referenced_filing
    } == {ACCN_Q2_10Q}


@respx.mock
async def test_expired_cache_falls_back_to_stale_facts(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _mock_ticker_map()
    respx.get(_COMPANY_FACTS_URL).mock(return_value=httpx.Response(500))
    cached = XbrlFacts(symbol="SYNT", facts=[], missing_labels=["Revenue"]).model_dump(mode="json")

    async with db_session_factory() as session:
        repo = CacheRepository(session)
        await repo.set("xbrl", _CACHE_KEY, cached, ttl_seconds=0)
        result = await XbrlService(
            client=client,
            cache=repo,
            edgar_service=EdgarService(client=client, cache=repo),
        ).get_facts("SYNT")

    assert result.is_stale is True
    assert result.value.missing_labels == ["Revenue"]


# --- Failure modes ----------------------------------------------------------


@respx.mock
async def test_unknown_symbol_raises_not_found_without_fetching_facts(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _mock_ticker_map()
    facts_route = _mock_company_facts()

    async with db_session_factory() as session:
        with pytest.raises(ProviderNotFoundError):
            await _service(client, session).get_facts("NOPE")

    assert not facts_route.called


@respx.mock
async def test_failed_fetch_with_nothing_cached_raises_unavailable(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _mock_ticker_map()
    respx.get(_COMPANY_FACTS_URL).mock(return_value=httpx.Response(503))

    async with db_session_factory() as session:
        with pytest.raises(ProviderUnavailableError):
            await _service(client, session).get_facts("SYNT")


@respx.mock
async def test_a_non_object_response_body_yields_no_facts_rather_than_raising(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _mock_ticker_map()
    respx.get(_COMPANY_FACTS_URL).mock(return_value=httpx.Response(200, json=[]))

    async with db_session_factory() as session:
        result = await _service(client, session).get_facts("SYNT")

    assert result.value.facts == []
    assert result.value.missing_labels == []
