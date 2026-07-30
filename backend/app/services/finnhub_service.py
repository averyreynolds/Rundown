"""Finnhub integration: cached, holdings-filtered news per symbol.

Reads through `CacheRepository` via `cache_through.fetch_with_cache`, one
symbol at a time, so Finnhub's 60-calls/min free tier is only spent on a
cache miss or expiry -- never on every dashboard load.
"""

import datetime as dt
from typing import Any

import httpx

from app.cache.cache_repository import CacheRepository
from app.cache.ttl_policy import news_ttl_seconds
from app.schemas.common import SourcedValue
from app.schemas.news import NewsItem
from app.services.cache_through import CachedResult, fetch_with_cache
from app.services.errors import ProviderFetchError

_PROVIDER = "finnhub"
_SOURCE_NAME = "Finnhub"

# How far back to search for news per request -- Finnhub's `company-news`
# endpoint requires an explicit `from`/`to` date range rather than
# defaulting to "recent".
_LOOKBACK_DAYS = 7


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class FinnhubService:
    """Fetches and caches recent company news for one symbol at a time."""

    def __init__(self, client: httpx.AsyncClient, cache: CacheRepository) -> None:
        self._client = client
        self._cache = cache

    async def get_news_for_symbols(self, symbols: list[str]) -> SourcedValue[list[NewsItem]]:
        """Return recent news across `symbols`, each cached independently.

        A symbol with no news in the lookback window contributes an empty
        list, not an error -- "nothing published recently" is a normal
        outcome, distinct from a provider failure.

        Raises:
            ProviderUnavailableError: Finnhub is failing for some symbol
                and nothing (fresh or stale) is cached for it yet.
        """
        results = [await self._get_news_for_symbol(symbol) for symbol in symbols]

        items = [NewsItem.model_validate(raw) for result in results for raw in result.payload]
        as_of = min((result.as_of for result in results), default=_utcnow())
        is_stale = any(result.is_stale for result in results)

        return SourcedValue(value=items, source=_SOURCE_NAME, as_of=as_of, is_stale=is_stale)

    async def _get_news_for_symbol(self, symbol: str) -> CachedResult:
        symbol = symbol.upper()
        return await fetch_with_cache(
            cache=self._cache,
            provider=_PROVIDER,
            cache_key=symbol,
            ttl_seconds=news_ttl_seconds(),
            fetch_live=lambda: self._fetch_live(symbol),
            clock=_utcnow,
        )

    async def _fetch_live(self, symbol: str) -> list[dict[str, Any]]:
        today = _utcnow().date()
        params = {
            "symbol": symbol,
            "from": (today - dt.timedelta(days=_LOOKBACK_DAYS)).isoformat(),
            "to": today.isoformat(),
        }
        try:
            response = await self._client.get("/api/v1/company-news", params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderFetchError(f"Finnhub request failed for {symbol}") from exc

        raw_items: list[dict[str, Any]] = response.json()
        return [{**item, "symbol": symbol} for item in raw_items]
