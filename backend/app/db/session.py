"""Async engine + session factory -- the only place a connection string or
SQL dialect is known outside `db/models.py`'s table definitions themselves.

`app/main.py`'s lifespan calls `create_engine()` and `init_models()` once
at startup and stores the resulting session factory on `app.state`;
`get_session` (a `Depends`-with-`yield` dependency) pulls that factory off
the current request to open/close one session per call. Swapping SQLite
for Postgres later is a `DATABASE_URL` + driver-dependency change, not a
rewrite -- provided nothing outside this module ever branches on dialect.
"""

from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import Base

# How long a writer waits for a lock held by another writer (e.g. the
# scheduler racing a request-triggered cache write) before raising
# "database is locked", rather than failing immediately.
_SQLITE_BUSY_TIMEOUT_MS = 5_000


def _enable_sqlite_wal_and_busy_timeout(engine: AsyncEngine) -> None:
    """Set WAL journal mode + a busy-timeout PRAGMA on every new SQLite connection.

    WAL lets request-serving reads proceed without blocking on a concurrent
    scheduler write (only writer-vs-writer is serialized); the busy-timeout
    is a retry-on-lock safety net for that remaining writer-vs-writer case.
    Without this, request handlers and the in-process scheduler (U9) both
    writing `cache_entries` on one SQLite file would intermittently raise
    "database is locked" on otherwise-healthy requests.

    Deliberately confined to this one function: these PRAGMAs are
    SQLite-specific and must not leak into any module that isn't allowed
    to know the dialect.
    """

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:  # noqa: ANN401
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}")
        cursor.close()


def create_engine(database_url: str) -> AsyncEngine:
    """Build the async engine for `database_url`, applying SQLite-only tuning when relevant."""
    engine = create_async_engine(database_url)
    if make_url(database_url).get_backend_name() == "sqlite":
        _enable_sqlite_wal_and_busy_timeout(engine)
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build a session factory bound to `engine`.

    `expire_on_commit=False` so objects a repository returns stay usable
    (e.g. read into a Pydantic response) after their session has committed
    and closed, rather than needing a fresh query to re-fetch every field.
    """
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    """Create every table declared on `Base.metadata` if it doesn't exist yet.

    Called once from the FastAPI lifespan at startup, before any request
    is served. Uses `create_all()`, not Alembic, per the plan's Key
    Technical Decisions: appropriate for a single-file, single-environment
    MVP. Re-running against an already-initialized database is a no-op.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield one request-scoped `AsyncSession`, closed when the request ends.

    Pulls the session factory `app.main`'s lifespan stored on
    `app.state.session_factory` -- this dependency has no request context
    of its own to construct one, and a scheduler job (U9) can't use this
    at all (no request exists), so jobs construct sessions directly from
    the same factory instead.
    """
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session
