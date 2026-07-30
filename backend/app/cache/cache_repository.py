"""Generic, provider-agnostic repository over the `cache_entries` table.

One repository class, shared by every provider service (U4-U7) and the
scheduler (U9) -- CLAUDE.md's "one caching module" instruction, applied
structurally rather than left as a convention to remember.
"""

import datetime as dt
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CacheEntry

Clock = Callable[[], dt.datetime]


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _as_aware_utc(value: dt.datetime) -> dt.datetime:
    """Attach a UTC tzinfo to `value` if it lacks one.

    SQLite has no native datetime type: SQLAlchemy's `DateTime(timezone=True)`
    column stores whatever it's given, but round-trips it back as a
    timezone-*naive* value regardless of what was written. Every
    `fetched_at` this repository ever writes is UTC (`_utcnow`), so a naive
    value read back is unambiguously UTC -- this normalizes it back to
    aware before it's compared against `self._clock()`, which is always
    aware, avoiding a `TypeError` from comparing naive and aware datetimes.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.UTC)
    return value


@dataclass(frozen=True, slots=True)
class CacheReadResult:
    """A cache entry read back, with staleness already evaluated.

    Distinguishes "cached but expired" from "not cached at all" (the
    latter is a bare `None` return from the repository methods below) --
    the stale-fallback-on-provider-error pattern (Key Technical Decisions)
    needs exactly this distinction to serve a labeled-stale value instead
    of a hard error only when *something* was ever cached.
    """

    payload: Any
    fetched_at: dt.datetime
    is_expired: bool


class CacheRepository:
    """Read/write access to `cache_entries` for one session.

    `clock` is injectable so tests can assert TTL-expiry behavior without
    depending on real wall-clock time (see the "Edge: get_or_none()
    returns None once the injectable clock advances past expiry" test
    scenario in the backend scaffold plan).
    """

    def __init__(self, session: AsyncSession, *, clock: Clock = _utcnow) -> None:
        self._session = session
        self._clock = clock

    async def get_or_none(self, provider: str, cache_key: str) -> Any | None:  # noqa: ANN401
        """Return the cached payload, or `None` if missing or expired.

        The common-path read: callers that don't need to distinguish a
        cold miss from an expired entry (i.e. anything not implementing
        the stale-fallback pattern) use this.
        """
        result = await self._read(provider, cache_key)
        if result is None or result.is_expired:
            return None
        return result.payload

    async def get_even_if_expired(self, provider: str, cache_key: str) -> CacheReadResult | None:
        """Return the cached entry regardless of expiry, or `None` if never written.

        Used for the stale-fallback pattern: on a provider failure, a
        service falls back to this entry's payload labeled with its true
        (past) `fetched_at`, rather than surfacing a hard error, as long
        as *something* was ever cached for this key.
        """
        return await self._read(provider, cache_key)

    async def set(
        self,
        provider: str,
        cache_key: str,
        payload: Any,  # noqa: ANN401
        ttl_seconds: int,
    ) -> None:
        """Upsert `payload` for `(provider, cache_key)`.

        A single atomic `INSERT ... ON CONFLICT DO UPDATE`, not a
        check-then-insert-or-update round trip, so two near-simultaneous
        writers targeting the same key (a scheduled refresh racing a
        request-triggered fetch-on-miss for the same symbol) can't both
        observe "no row" and both attempt an insert (Key Technical
        Decisions). This uses SQLite's dialect-specific upsert construct --
        the one deliberately non-portable line in this module; swapping to
        Postgres later means changing this import to
        `sqlalchemy.dialects.postgresql.insert`, which supports the same
        `on_conflict_do_update` shape, not a redesign.

        `payload` must be JSON-serializable as-is -- callers are
        responsible for converting provider-specific types (`Decimal`,
        `datetime`, etc.) to plain values before calling this, since this
        module has no business knowing every provider's payload shape.

        Raises:
            TypeError: if `payload` is not JSON-serializable.
        """
        try:
            payload_json = json.dumps(payload)
        except TypeError as exc:
            raise TypeError(
                f"Cache payload for {provider}:{cache_key} is not JSON-serializable."
            ) from exc

        fetched_at = self._clock()
        insert_stmt = sqlite_insert(CacheEntry).values(
            provider=provider,
            cache_key=cache_key,
            payload_json=payload_json,
            fetched_at=fetched_at,
            ttl_seconds=ttl_seconds,
        )
        upsert_stmt = insert_stmt.on_conflict_do_update(
            index_elements=[CacheEntry.provider, CacheEntry.cache_key],
            set_={
                "payload_json": payload_json,
                "fetched_at": fetched_at,
                "ttl_seconds": ttl_seconds,
            },
        )
        await self._session.execute(upsert_stmt)
        await self._session.commit()

    async def _read(self, provider: str, cache_key: str) -> CacheReadResult | None:
        stmt = select(CacheEntry).where(
            CacheEntry.provider == provider, CacheEntry.cache_key == cache_key
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None

        fetched_at = _as_aware_utc(row.fetched_at)
        expires_at = fetched_at + dt.timedelta(seconds=row.ttl_seconds)
        return CacheReadResult(
            payload=json.loads(row.payload_json),
            fetched_at=fetched_at,
            is_expired=self._clock() >= expires_at,
        )
