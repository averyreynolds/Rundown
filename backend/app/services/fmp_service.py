"""Financial Modeling Prep integration: cached fundamental ratios per symbol.

Reads through `CacheRepository` via `cache_through.fetch_with_cache`, so
FMP's ~250-request/day free tier is only spent on a cache miss or expiry,
never on every dashboard load (CLAUDE.md's rate-limit discipline rule).
"""

import asyncio
import datetime as dt
from typing import Any

import httpx

from app.cache.cache_repository import CacheRepository
from app.cache.ttl_policy import fundamentals_ttl_seconds
from app.schemas.common import SourcedValue
from app.schemas.fundamentals import FundamentalsSnapshot
from app.services.cache_through import fetch_with_cache
from app.services.errors import ProviderFetchError, ProviderNotFoundError

_PROVIDER = "fmp"
_SOURCE_NAME = "Financial Modeling Prep"


class FmpService:
    """Fetches and caches FMP ratios + key metrics for one symbol at a time."""

    def __init__(self, client: httpx.AsyncClient, cache: CacheRepository) -> None:
        self._client = client
        self._cache = cache

    async def get_fundamentals(self, symbol: str) -> SourcedValue[FundamentalsSnapshot]:
        """Return `symbol`'s ratios + key metrics, cached per `ttl_policy`.

        Raises:
            ProviderUnavailableError: FMP is unreachable/erroring and no
                cached value (fresh or stale) exists for `symbol`.
            ProviderNotFoundError: FMP returns no data at all for `symbol`
                (an unknown/invalid ticker) -- checked before caching, so
                this is never masked as a stale-fallback-eligible failure.
        """
        symbol = symbol.upper()
        result = await fetch_with_cache(
            cache=self._cache,
            provider=_PROVIDER,
            cache_key=symbol,
            ttl_seconds=fundamentals_ttl_seconds(),
            fetch_live=lambda: self._fetch_live(symbol),
            clock=lambda: dt.datetime.now(dt.UTC),
        )
        snapshot = FundamentalsSnapshot.model_validate(result.payload)
        return SourcedValue(
            value=snapshot,
            source=_SOURCE_NAME,
            as_of=result.as_of,
            is_stale=result.is_stale,
        )

    async def _fetch_live(self, symbol: str) -> dict[str, Any]:
        try:
            ratios_response, key_metrics_response = await asyncio.gather(
                self._client.get("/stable/ratios", params={"symbol": symbol}),
                self._client.get("/stable/key-metrics-ttm", params={"symbol": symbol}),
            )
            ratios_response.raise_for_status()
            key_metrics_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderFetchError(f"FMP request failed for {symbol}") from exc

        ratios = ratios_response.json()
        key_metrics = key_metrics_response.json()
        if not ratios or not key_metrics:
            raise ProviderNotFoundError(_PROVIDER, symbol)

        return {"symbol": symbol, **ratios[0], **key_metrics[0]}
