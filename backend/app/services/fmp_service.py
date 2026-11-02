"""Financial Modeling Prep integration: cached fundamental ratios per symbol.

Reads through `CacheRepository` via `cache_through.fetch_with_cache`, so
FMP's ~250-request/day free tier is only spent on a cache miss or expiry,
never on every dashboard load (CLAUDE.md's rate-limit discipline rule).
"""

import asyncio
import datetime as dt
from decimal import Decimal
from typing import Any

import httpx

from app.cache.cache_repository import CacheRepository
from app.cache.ttl_policy import fundamentals_ttl_seconds, price_history_ttl_seconds
from app.domain.price_windows import PriceWindow, compute_window_change, slice_window
from app.domain.types import PricePoint as DomainPricePoint
from app.schemas.common import SourcedValue
from app.schemas.fundamentals import FundamentalsSnapshot
from app.schemas.prices import PriceHistoryWindow, PricePoint
from app.services.cache_through import fetch_with_cache
from app.services.errors import ProviderFetchError, ProviderNotFoundError

_PRICE_HISTORY_LOOKBACK_DAYS = 730
"""~2 years: covers every selectable chart window up to "1Y" with room for
YTD, and "All" is deliberately capped here for the MVP rather than fetching
a symbol's full listed history -- FMP's free-tier rate limit charges the
same one request either way, so there's no budget reason not to extend this
later if a longer lookback turns out to matter."""

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

    async def get_price_history(
        self, symbol: str, window: PriceWindow = PriceWindow.ALL
    ) -> SourcedValue[PriceHistoryWindow]:
        """Return `symbol`'s daily closes sliced to `window`, plus that window's price
        change, both computed by `app.domain.price_windows` over the cached trailing-
        two-year series (see `_fetch_price_history_live`).

        The cache itself always holds the full ~2-year series regardless of
        `window` -- only the slicing/change math varies per call -- so
        switching windows on an already-loaded symbol never costs another
        FMP request.

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
            cache_key=f"price-history:{symbol}",
            ttl_seconds=price_history_ttl_seconds(),
            fetch_live=lambda: self._fetch_price_history_live(symbol),
            clock=lambda: dt.datetime.now(dt.UTC),
        )
        full_series = [
            DomainPricePoint(date=dt.date.fromisoformat(p["date"]), close=Decimal(str(p["close"])))
            for p in result.payload
        ]
        today = dt.datetime.now(dt.UTC).date()
        sliced = slice_window(full_series, window, today=today)
        change = compute_window_change(full_series, window, today=today)

        payload = PriceHistoryWindow(
            points=[PricePoint(date=p.date, close=p.close) for p in sliced],
            price_change_dollars=change.price_dollars if change else None,
            price_change_percent=change.price_percent if change else None,
        )
        return SourcedValue(
            value=payload, source=_SOURCE_NAME, as_of=result.as_of, is_stale=result.is_stale
        )

    async def _fetch_price_history_live(self, symbol: str) -> list[dict[str, Any]]:
        today = dt.datetime.now(dt.UTC).date()
        start = today - dt.timedelta(days=_PRICE_HISTORY_LOOKBACK_DAYS)
        try:
            response = await self._client.get(
                "/stable/historical-price-eod/full",
                params={"symbol": symbol, "from": start.isoformat(), "to": today.isoformat()},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderFetchError(f"FMP historical price request failed for {symbol}") from exc

        raw = response.json()
        if not raw:
            raise ProviderNotFoundError(_PROVIDER, symbol)

        # FMP reports most-recent-first; callers (domain window-slicing,
        # the chart) want chronological order.
        return sorted(
            ({"date": p["date"], "close": p["close"]} for p in raw),
            key=lambda p: p["date"],
        )
