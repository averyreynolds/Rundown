"""Tests for `app.services.fmp_service.FmpService`.

All FMP HTTP calls are mocked via `respx` -- this suite never touches the
live network, per CLAUDE.md's rule that tests never consume rate-limit
budget.
"""

import datetime as dt
from collections.abc import AsyncIterator
from decimal import Decimal

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cache.cache_repository import CacheRepository
from app.services.errors import ProviderNotFoundError, ProviderUnavailableError
from app.services.fmp_service import FmpService

_RATIOS_URL = "https://financialmodelingprep.com/stable/ratios"
_KEY_METRICS_URL = "https://financialmodelingprep.com/stable/key-metrics-ttm"


def _ratios_payload(symbol: str = "AAPL") -> list[dict[str, str | float]]:
    return [{"symbol": symbol, "priceToEarningsRatio": 25.5, "currentRatio": 1.5}]


def _key_metrics_payload(symbol: str = "AAPL") -> list[dict[str, str | float]]:
    return [{"symbol": symbol, "revenuePerShareTTM": 6.5}]


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url="https://financialmodelingprep.com") as c:
        yield c


@respx.mock
async def test_get_fundamentals_returns_sourced_snapshot(
    client: httpx.AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    respx.get(_RATIOS_URL).mock(return_value=httpx.Response(200, json=_ratios_payload()))
    respx.get(_KEY_METRICS_URL).mock(return_value=httpx.Response(200, json=_key_metrics_payload()))

    async with db_session_factory() as session:
        result = await FmpService(client=client, cache=CacheRepository(session)).get_fundamentals(
            "aapl"
        )

    assert result.source == "Financial Modeling Prep"
    assert result.is_stale is False
    assert isinstance(result.as_of, dt.datetime)
    assert result.value.symbol == "AAPL"
    assert result.value.price_to_earnings_ratio == Decimal("25.5")
    assert result.value.revenue_per_share_ttm == Decimal("6.5")


@respx.mock
async def test_second_call_within_ttl_does_not_trigger_second_http_call(
    client: httpx.AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ratios_route = respx.get(_RATIOS_URL).mock(
        return_value=httpx.Response(200, json=_ratios_payload())
    )
    key_metrics_route = respx.get(_KEY_METRICS_URL).mock(
        return_value=httpx.Response(200, json=_key_metrics_payload())
    )

    async with db_session_factory() as session:
        await FmpService(client=client, cache=CacheRepository(session)).get_fundamentals("AAPL")
    async with db_session_factory() as session:
        await FmpService(client=client, cache=CacheRepository(session)).get_fundamentals("AAPL")

    assert ratios_route.call_count == 1
    assert key_metrics_route.call_count == 1


@respx.mock
async def test_provider_error_with_no_cache_raises_provider_unavailable(
    client: httpx.AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    respx.get(_RATIOS_URL).mock(return_value=httpx.Response(500))
    respx.get(_KEY_METRICS_URL).mock(return_value=httpx.Response(500))

    async with db_session_factory() as session:
        with pytest.raises(ProviderUnavailableError):
            await FmpService(client=client, cache=CacheRepository(session)).get_fundamentals("AAPL")


@respx.mock
async def test_provider_error_with_existing_cache_returns_stale_labeled_value(
    client: httpx.AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    ratios_route = respx.get(_RATIOS_URL).mock(
        return_value=httpx.Response(200, json=_ratios_payload())
    )
    respx.get(_KEY_METRICS_URL).mock(return_value=httpx.Response(200, json=_key_metrics_payload()))

    async with db_session_factory() as session:
        await FmpService(client=client, cache=CacheRepository(session)).get_fundamentals("AAPL")

    # Force the cached entry to be treated as expired, then make FMP fail.
    async with db_session_factory() as session:
        repo = CacheRepository(session)
        cached_payload = await repo.get_or_none("fmp", "AAPL")
        await repo.set("fmp", "AAPL", cached_payload, ttl_seconds=0)

    ratios_route.mock(return_value=httpx.Response(503))

    async with db_session_factory() as session:
        result = await FmpService(client=client, cache=CacheRepository(session)).get_fundamentals(
            "AAPL"
        )

    assert result.is_stale is True
    assert result.value.symbol == "AAPL"


@respx.mock
async def test_unknown_symbol_raises_provider_not_found(
    client: httpx.AsyncClient,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    respx.get(_RATIOS_URL).mock(return_value=httpx.Response(200, json=[]))
    respx.get(_KEY_METRICS_URL).mock(return_value=httpx.Response(200, json=[]))

    async with db_session_factory() as session:
        with pytest.raises(ProviderNotFoundError):
            await FmpService(client=client, cache=CacheRepository(session)).get_fundamentals(
                "NOTREAL"
            )
