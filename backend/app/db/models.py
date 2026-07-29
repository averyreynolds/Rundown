"""SQLAlchemy 2.0 declarative models -- the single place table schemas live.

Two tables ship in U3: a generic `cache_entries` table (CLAUDE.md's "one
caching module" instruction, and the Key Technical Decision to avoid
bespoke tables per provider) and `portfolio_snapshots` (R12's minimal
daily snapshot-write job, populated by U9's scheduled job, queried by
nothing yet -- comparison logic is deferred follow-up work). U4 adds a
third table, `snaptrade_connection`, to this same module.
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model in this module."""


class CacheEntry(Base):
    """One cached provider response, keyed by `(provider, cache_key)`.

    `payload_json` stores the cached value as an already-JSON-encoded
    string -- deliberately opaque to the schema, since this table has no
    business knowing FMP's ratio shape versus Finnhub's news-item shape.
    `CacheRepository` (de)serializes on behalf of every caller.
    """

    __tablename__ = "cache_entries"
    __table_args__ = (UniqueConstraint("provider", "cache_key", name="uq_cache_provider_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    cache_key: Mapped[str] = mapped_column(String(255), index=True)
    payload_json: Mapped[str] = mapped_column(String)
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    ttl_seconds: Mapped[int]


class PortfolioSnapshot(Base):
    """One holding's point-in-time snapshot, written once per day by U9.

    Write-only by design for this plan (R12): no comparison/trend query
    lives anywhere in this codebase yet. This table exists purely so
    historical data starts accumulating now, rather than a future
    trend-narrative feature being blocked behind months of data collection
    that could have started immediately.
    """

    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_date: Mapped[dt.date] = mapped_column(index=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    market_value: Mapped[Decimal] = mapped_column(Numeric)
    allocation_pct: Mapped[Decimal] = mapped_column(Numeric)
