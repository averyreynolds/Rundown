"""Shared read-through-cache-with-stale-fallback control flow.

Every simple external-data service (FMP, EDGAR, Finnhub, and SnapTrade's
positions/balances) follows the exact same shape, per the plan's Key
Technical Decisions: try the cache, fetch live on a miss or expiry, cache
a successful fetch, and -- if the live fetch fails -- fall back to the
last cached value (even expired) labeled with its true as-of time, rather
than a hard error, as long as *something* was ever cached. Implementing
this once here rather than once per provider service means that behavior
stays uniform across all four services by construction, not by each
remembering to copy it correctly.
"""

import datetime as dt
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.cache.cache_repository import CacheRepository, Clock
from app.services.errors import ProviderFetchError, ProviderUnavailableError


@dataclass(frozen=True, slots=True)
class CachedResult:
    """A value plus whether it came from a live fetch/fresh cache hit or a stale fallback."""

    payload: Any
    as_of: dt.datetime
    is_stale: bool


async def fetch_with_cache(
    *,
    cache: CacheRepository,
    provider: str,
    cache_key: str,
    ttl_seconds: int,
    fetch_live: Callable[[], Awaitable[Any]],
    clock: Clock,
) -> CachedResult:
    """Read `cache_key` through `cache`, falling back to a live fetch on a miss or expiry.

    Only `ProviderFetchError` raised by `fetch_live` is treated as a
    transient failure eligible for stale-cache fallback -- any other
    exception (e.g. a service's own "invalid symbol" error) propagates
    straight through unchanged, since that's a bad-input case with
    nothing to do with cache freshness.

    Raises:
        ProviderUnavailableError: `fetch_live` raised `ProviderFetchError`
            and no cached value -- fresh or stale -- exists to fall back
            to. This is the only error this function itself raises.
    """
    cached = await cache.get_even_if_expired(provider, cache_key)
    if cached is not None and not cached.is_expired:
        return CachedResult(payload=cached.payload, as_of=cached.fetched_at, is_stale=False)

    try:
        live_payload = await fetch_live()
    except ProviderFetchError as exc:
        if cached is not None:
            return CachedResult(payload=cached.payload, as_of=cached.fetched_at, is_stale=True)
        raise ProviderUnavailableError(provider, cache_key, exc) from exc

    now = clock()
    await cache.set(provider, cache_key, live_payload, ttl_seconds)
    return CachedResult(payload=live_payload, as_of=now, is_stale=False)
