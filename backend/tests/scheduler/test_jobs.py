"""Tests for `app.scheduler.jobs`.

Job functions take a plain `app_state`-shaped object (see the module
docstring in `app/scheduler/jobs.py`), so these tests build a lightweight
`SimpleNamespace` fake rather than spinning up the real FastAPI app.
"""

import datetime as dt
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import respx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.cache.cache_repository import CacheRepository
from app.db.models import PortfolioSnapshot
from app.scheduler.jobs import (
    FUNDAMENTALS_JOB_ID,
    NEWS_JOB_ID,
    SNAPSHOT_JOB_ID,
    XBRL_FACTS_JOB_ID,
    refresh_fundamentals,
    refresh_news,
    refresh_xbrl_facts,
    register_jobs,
    write_daily_snapshot,
)
from tests.fixtures.synthetic_positions import (
    build_fake_snaptrade_client,
    synthetic_account,
    synthetic_balance,
    synthetic_stock_position,
)
from tests.fixtures.synthetic_xbrl import synthetic_company_facts

_RATIOS_URL = "https://financialmodelingprep.com/stable/ratios"
_KEY_METRICS_URL = "https://financialmodelingprep.com/stable/key-metrics-ttm"
_NEWS_URL = "https://finnhub.io/api/v1/company-news"
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"


def _connected_app_state(
    db_session_factory: async_sessionmaker[AsyncSession],
    *,
    positions: list[dict[str, Any]] | None = None,
) -> SimpleNamespace:
    """An `app_state` whose SnapTrade fake has one linked brokerage with holdings."""
    snaptrade_client = build_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=positions if positions is not None else [synthetic_stock_position()],
    )
    return SimpleNamespace(
        session_factory=db_session_factory,
        snaptrade_client=snaptrade_client,
        fmp_client=httpx.AsyncClient(base_url="https://financialmodelingprep.com"),
        finnhub_client=httpx.AsyncClient(base_url="https://finnhub.io"),
        edgar_client=httpx.AsyncClient(headers={"User-Agent": "Rundown Test (test@example.com)"}),
    )


def test_register_jobs_adds_expected_jobs_with_expected_intervals() -> None:
    scheduler = AsyncIOScheduler()
    fake_state = SimpleNamespace()

    register_jobs(scheduler, fake_state)

    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert set(jobs) == {FUNDAMENTALS_JOB_ID, NEWS_JOB_ID, XBRL_FACTS_JOB_ID, SNAPSHOT_JOB_ID}
    assert isinstance(jobs[FUNDAMENTALS_JOB_ID].trigger, IntervalTrigger)
    assert jobs[FUNDAMENTALS_JOB_ID].trigger.interval == dt.timedelta(hours=24)
    assert jobs[NEWS_JOB_ID].trigger.interval == dt.timedelta(hours=4)
    assert jobs[XBRL_FACTS_JOB_ID].trigger.interval == dt.timedelta(hours=24)
    assert jobs[SNAPSHOT_JOB_ID].trigger.interval == dt.timedelta(hours=24)


@respx.mock
async def test_refresh_fundamentals_writes_one_cache_entry_per_symbol(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    respx.get(_RATIOS_URL).mock(
        return_value=httpx.Response(200, json=[{"symbol": "AAPL", "priceToEarningsRatio": 20}])
    )
    respx.get(_KEY_METRICS_URL).mock(
        return_value=httpx.Response(200, json=[{"symbol": "AAPL", "revenuePerShareTTM": 5}])
    )
    app_state = _connected_app_state(db_session_factory)

    await refresh_fundamentals(app_state)

    async with db_session_factory() as session:
        cached = await CacheRepository(session).get_or_none("fmp", "AAPL")
    assert cached is not None


@respx.mock
async def test_refresh_fundamentals_one_symbol_failure_does_not_abort_batch(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    respx.get(_RATIOS_URL, params={"symbol": "AAPL"}).mock(return_value=httpx.Response(500))
    respx.get(_KEY_METRICS_URL, params={"symbol": "AAPL"}).mock(return_value=httpx.Response(500))
    respx.get(_RATIOS_URL, params={"symbol": "MSFT"}).mock(
        return_value=httpx.Response(200, json=[{"symbol": "MSFT", "priceToEarningsRatio": 30}])
    )
    respx.get(_KEY_METRICS_URL, params={"symbol": "MSFT"}).mock(
        return_value=httpx.Response(200, json=[{"symbol": "MSFT", "revenuePerShareTTM": 8}])
    )
    app_state = _connected_app_state(
        db_session_factory,
        positions=[
            synthetic_stock_position(symbol="AAPL"),
            synthetic_stock_position(symbol="MSFT"),
        ],
    )

    await refresh_fundamentals(app_state)  # must not raise despite AAPL failing

    async with db_session_factory() as session:
        cache = CacheRepository(session)
        assert await cache.get_or_none("fmp", "AAPL") is None
        assert await cache.get_or_none("fmp", "MSFT") is not None


@respx.mock
async def test_refresh_news_writes_one_cache_entry_per_symbol(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    respx.get(_NEWS_URL).mock(return_value=httpx.Response(200, json=[]))
    app_state = _connected_app_state(db_session_factory)

    await refresh_news(app_state)

    async with db_session_factory() as session:
        cached = await CacheRepository(session).get_or_none("finnhub", "AAPL")
    assert cached == []


async def test_write_daily_snapshot_writes_one_row_per_holding(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    app_state = _connected_app_state(db_session_factory)

    await write_daily_snapshot(app_state)

    async with db_session_factory() as session:
        rows = (await session.execute(select(PortfolioSnapshot))).scalars().all()
    assert len(rows) == 1
    assert rows[0].symbol == "AAPL"
    assert rows[0].allocation_pct == 100


async def test_write_daily_snapshot_skips_when_no_brokerage_linked(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """No linked brokerage yet -> zero holdings -> the run is skipped, not an empty write."""
    app_state = SimpleNamespace(
        session_factory=db_session_factory,
        snaptrade_client=build_fake_snaptrade_client(),
    )

    await write_daily_snapshot(app_state)  # must not raise

    async with db_session_factory() as session:
        rows = (await session.execute(select(PortfolioSnapshot))).scalars().all()
    assert rows == []


async def test_scheduler_shuts_down_before_engine_and_http_clients_torn_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies teardown order against the real app, not a fake -- this ordering
    guarantee only matters as a property of the actual lifespan wiring."""
    from app.main import app

    call_order: list[str] = []

    original_shutdown = AsyncIOScheduler.shutdown

    def _tracked_shutdown(self: AsyncIOScheduler, *args: object, **kwargs: object) -> None:
        call_order.append("scheduler_shutdown")
        original_shutdown(self, *args, **kwargs)

    monkeypatch.setattr(AsyncIOScheduler, "shutdown", _tracked_shutdown)

    original_aclose = httpx.AsyncClient.aclose

    async def _tracked_aclose(self: httpx.AsyncClient) -> None:
        call_order.append("http_client_aclose")
        await original_aclose(self)

    monkeypatch.setattr(httpx.AsyncClient, "aclose", _tracked_aclose)

    original_dispose = AsyncEngine.dispose

    async def _tracked_dispose(self: AsyncEngine, close: bool = True) -> None:
        call_order.append("engine_dispose")
        await original_dispose(self, close)

    monkeypatch.setattr(AsyncEngine, "dispose", _tracked_dispose)

    with TestClient(app):
        pass

    assert call_order[0] == "scheduler_shutdown"
    assert call_order.index("scheduler_shutdown") < call_order.index("engine_dispose")
    assert not app.state.scheduler.running


@respx.mock
async def test_refresh_xbrl_facts_warms_the_cache_for_each_held_symbol(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    respx.get(_TICKER_MAP_URL).mock(
        return_value=httpx.Response(200, json={"0": {"cik_str": 320193, "ticker": "AAPL"}})
    )
    respx.get(_COMPANY_FACTS_URL).mock(
        return_value=httpx.Response(200, json=synthetic_company_facts())
    )
    app_state = _connected_app_state(db_session_factory)

    await refresh_xbrl_facts(app_state)

    async with db_session_factory() as session:
        cached = await CacheRepository(session).get_or_none("xbrl", "facts:320193")
    assert cached is not None
    assert cached["symbol"] == "AAPL"
    assert cached["facts"]


@respx.mock
async def test_refresh_xbrl_facts_tolerates_a_holding_that_is_not_an_sec_filer(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An ETF or non-US listing simply isn't in SEC's ticker map. Expected
    steady state for such a holding, not a run-aborting failure."""
    respx.get(_TICKER_MAP_URL).mock(
        return_value=httpx.Response(200, json={"0": {"cik_str": 320193, "ticker": "AAPL"}})
    )
    respx.get(_COMPANY_FACTS_URL).mock(
        return_value=httpx.Response(200, json=synthetic_company_facts())
    )
    app_state = _connected_app_state(
        db_session_factory,
        positions=[
            synthetic_stock_position(symbol="VTI"),
            synthetic_stock_position(symbol="AAPL"),
        ],
    )

    await refresh_xbrl_facts(app_state)  # must not raise on VTI

    async with db_session_factory() as session:
        assert await CacheRepository(session).get_or_none("xbrl", "facts:320193") is not None


@respx.mock
async def test_refresh_xbrl_facts_one_symbol_outage_does_not_abort_the_batch(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    respx.get(_TICKER_MAP_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "0": {"cik_str": 320193, "ticker": "AAPL"},
                "1": {"cik_str": 789019, "ticker": "MSFT"},
            },
        )
    )
    respx.get("https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json").mock(
        return_value=httpx.Response(503)
    )
    respx.get(_COMPANY_FACTS_URL).mock(
        return_value=httpx.Response(200, json=synthetic_company_facts())
    )
    app_state = _connected_app_state(
        db_session_factory,
        positions=[
            synthetic_stock_position(symbol="MSFT"),
            synthetic_stock_position(symbol="AAPL"),
        ],
    )

    await refresh_xbrl_facts(app_state)  # must not raise despite MSFT 503ing

    async with db_session_factory() as session:
        cache = CacheRepository(session)
        assert await cache.get_or_none("xbrl", "facts:789019") is None
        assert await cache.get_or_none("xbrl", "facts:320193") is not None


async def test_refresh_xbrl_facts_skips_when_no_brokerage_linked(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    app_state = SimpleNamespace(
        session_factory=db_session_factory,
        snaptrade_client=build_fake_snaptrade_client(),
    )

    await refresh_xbrl_facts(app_state)  # must not raise, and must not touch the network
