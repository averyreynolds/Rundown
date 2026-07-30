"""Tests for `app.cache.cache_repository.CacheRepository` and DB lifecycle.

Uses the `db_engine` / `db_session_factory` fixtures from the root
`conftest.py` -- a real temp-file SQLite database per test, not mocks,
since this module's whole job is to get SQLite's concurrency/TTL
behavior right.
"""

import asyncio
import datetime as dt

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.cache.cache_repository import CacheRepository
from app.db.models import CacheEntry, PortfolioSnapshot
from app.db.session import init_models


class FakeClock:
    """A mutable, injectable clock so TTL-expiry tests don't depend on real time."""

    def __init__(self, now: dt.datetime) -> None:
        self.now = now

    def __call__(self) -> dt.datetime:
        return self.now


async def test_set_then_get_or_none_returns_payload_before_ttl_expiry(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    clock = FakeClock(dt.datetime(2026, 1, 1, tzinfo=dt.UTC))
    async with db_session_factory() as session:
        repo = CacheRepository(session, clock=clock)
        await repo.set("fmp", "AAPL", {"pe_ratio": 25}, ttl_seconds=60)

        result = await repo.get_or_none("fmp", "AAPL")

    assert result == {"pe_ratio": 25}


async def test_get_or_none_returns_none_once_clock_advances_past_ttl(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    clock = FakeClock(dt.datetime(2026, 1, 1, tzinfo=dt.UTC))
    async with db_session_factory() as session:
        repo = CacheRepository(session, clock=clock)
        await repo.set("fmp", "AAPL", {"pe_ratio": 25}, ttl_seconds=60)

        clock.now += dt.timedelta(seconds=61)
        result = await repo.get_or_none("fmp", "AAPL")

    assert result is None


async def test_get_or_none_cold_miss_returns_none(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repo = CacheRepository(session)

        assert await repo.get_or_none("fmp", "NEVER_WRITTEN") is None


async def test_get_even_if_expired_distinguishes_expired_from_never_cached(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    clock = FakeClock(dt.datetime(2026, 1, 1, tzinfo=dt.UTC))
    async with db_session_factory() as session:
        repo = CacheRepository(session, clock=clock)

        assert await repo.get_even_if_expired("fmp", "AAPL") is None

        await repo.set("fmp", "AAPL", {"pe_ratio": 25}, ttl_seconds=60)
        clock.now += dt.timedelta(seconds=61)
        stale = await repo.get_even_if_expired("fmp", "AAPL")

    assert stale is not None
    assert stale.payload == {"pe_ratio": 25}
    assert stale.is_expired is True


async def test_set_with_non_json_serializable_payload_raises_type_error(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repo = CacheRepository(session)

        with pytest.raises(TypeError):
            await repo.set("fmp", "AAPL", {"bad": object()}, ttl_seconds=60)


async def test_concurrent_set_calls_for_same_key_do_not_raise_integrity_error(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Two near-simultaneous writers targeting the same key never both insert."""

    async def _write(value: int) -> None:
        async with db_session_factory() as session:
            await CacheRepository(session).set("fmp", "AAPL", {"value": value}, ttl_seconds=60)

    await asyncio.gather(_write(1), _write(2))

    async with db_session_factory() as session:
        result = await CacheRepository(session).get_or_none("fmp", "AAPL")

    # Last-write-wins is acceptable per the plan's Key Technical Decisions --
    # what matters is that exactly one of the two writes survived cleanly.
    assert result in ({"value": 1}, {"value": 2})


def _table_names(conn: Connection) -> list[str]:
    return inspect(conn).get_table_names()


async def test_init_models_creates_cache_entries_and_portfolio_snapshots_tables(
    db_engine: AsyncEngine,
) -> None:
    async with db_engine.connect() as conn:
        table_names = await conn.run_sync(_table_names)

    assert CacheEntry.__tablename__ in table_names
    assert PortfolioSnapshot.__tablename__ in table_names


async def test_init_models_is_a_no_op_against_an_already_initialized_database(
    db_engine: AsyncEngine,
) -> None:
    # db_engine already ran init_models() once via the fixture; a second
    # call against the same engine must not raise.
    await init_models(db_engine)


async def test_sqlite_wal_mode_is_active(db_engine: AsyncEngine) -> None:
    async with db_engine.connect() as conn:
        result = await conn.execute(text("PRAGMA journal_mode"))
        mode = result.scalar_one()

    assert mode.lower() == "wal"
