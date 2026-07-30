"""Tests for `app.services.finnhub_service.FinnhubService`.

All Finnhub HTTP calls are mocked via `respx` -- this suite never touches
the live network, per CLAUDE.md's rule that tests never consume
rate-limit budget.
"""

import datetime as dt
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cache.cache_repository import CacheRepository
from app.services.errors import ProviderUnavailableError
from app.services.finnhub_service import FinnhubService
from tests.fixtures.synthetic_news import synthetic_news_items

_NEWS_URL = "https://finnhub.io/api/v1/company-news"


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url="https://finnhub.io") as c:
        yield c


@respx.mock
async def test_get_news_returns_sourced_items_for_requested_symbols(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    respx.get(_NEWS_URL, params={"symbol": "AAPL"}).mock(
        return_value=httpx.Response(200, json=synthetic_news_items(2))
    )

    async with db_session_factory() as session:
        result = await FinnhubService(
            client=client, cache=CacheRepository(session)
        ).get_news_for_symbols(["aapl"])

    assert result.source == "Finnhub"
    assert result.is_stale is False
    assert isinstance(result.as_of, dt.datetime)
    assert len(result.value) == 2
    assert all(item.symbol == "AAPL" for item in result.value)
    assert result.value[0].publisher == "Synthetic Wire 0"


@respx.mock
async def test_second_call_within_ttl_does_not_trigger_second_http_call(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    route = respx.get(_NEWS_URL, params={"symbol": "AAPL"}).mock(
        return_value=httpx.Response(200, json=synthetic_news_items(1))
    )

    async with db_session_factory() as session:
        await FinnhubService(client=client, cache=CacheRepository(session)).get_news_for_symbols(
            ["AAPL"]
        )
    async with db_session_factory() as session:
        await FinnhubService(client=client, cache=CacheRepository(session)).get_news_for_symbols(
            ["AAPL"]
        )

    assert route.call_count == 1


@respx.mock
async def test_no_news_found_returns_empty_list_not_an_error(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    respx.get(_NEWS_URL, params={"symbol": "AAPL"}).mock(return_value=httpx.Response(200, json=[]))

    async with db_session_factory() as session:
        result = await FinnhubService(
            client=client, cache=CacheRepository(session)
        ).get_news_for_symbols(["AAPL"])

    assert result.value == []


@respx.mock
async def test_provider_error_with_no_cache_raises_provider_unavailable(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    respx.get(_NEWS_URL, params={"symbol": "AAPL"}).mock(return_value=httpx.Response(429))

    async with db_session_factory() as session:
        with pytest.raises(ProviderUnavailableError):
            await FinnhubService(
                client=client, cache=CacheRepository(session)
            ).get_news_for_symbols(["AAPL"])


@respx.mock
async def test_provider_error_with_existing_cache_returns_stale_labeled_value(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    route = respx.get(_NEWS_URL, params={"symbol": "AAPL"}).mock(
        return_value=httpx.Response(200, json=synthetic_news_items(1))
    )

    async with db_session_factory() as session:
        repo = CacheRepository(session)
        await FinnhubService(client=client, cache=repo).get_news_for_symbols(["AAPL"])
        cached_payload = await repo.get_or_none("finnhub", "AAPL")
        await repo.set("finnhub", "AAPL", cached_payload, ttl_seconds=0)

    route.mock(return_value=httpx.Response(503))

    async with db_session_factory() as session:
        result = await FinnhubService(
            client=client, cache=CacheRepository(session)
        ).get_news_for_symbols(["AAPL"])

    assert result.is_stale is True
    assert len(result.value) == 1


@respx.mock
async def test_multiple_symbols_each_fetched_and_merged(
    client: httpx.AsyncClient, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    respx.get(_NEWS_URL, params={"symbol": "AAPL"}).mock(
        return_value=httpx.Response(200, json=synthetic_news_items(1))
    )
    respx.get(_NEWS_URL, params={"symbol": "MSFT"}).mock(
        return_value=httpx.Response(200, json=synthetic_news_items(1))
    )

    async with db_session_factory() as session:
        result = await FinnhubService(
            client=client, cache=CacheRepository(session)
        ).get_news_for_symbols(["AAPL", "MSFT"])

    assert {item.symbol for item in result.value} == {"AAPL", "MSFT"}
