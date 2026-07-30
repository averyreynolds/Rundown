"""Job functions and registration for the scheduler.

Jobs run outside any request context, so they can't use FastAPI's
`Depends` -- `api/dependencies.py`'s factories are request-scoped and
have nothing to inject through here. Each job instead constructs its
service/repository instances directly from the same constructors those
factories wrap, taking the shared resources (the session factory,
provider clients) straight off `app.state`, per the plan's Key Technical
Decisions.

Every job iterates the user's *current* holdings first (via
`SnapTradeService.list_positions`) and skips its run entirely if no
SnapTrade connection exists yet, rather than iterating zero holdings or
writing a meaningless empty snapshot. One symbol's failure during a batch
never aborts the rest of the batch -- CLAUDE.md's rate-limit discipline
rule and R12's minimal snapshot both depend on these jobs actually
running reliably, not silently dying on the first bad symbol.
"""

import datetime as dt
import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.cache.cache_repository import CacheRepository
from app.core.config import get_settings
from app.db.models import PortfolioSnapshot
from app.services.errors import ProviderNotFoundError, ProviderUnavailableError
from app.services.finnhub_service import FinnhubService
from app.services.fmp_service import FmpService
from app.services.snaptrade_service import SnapTradeService

logger = logging.getLogger(__name__)

FUNDAMENTALS_JOB_ID = "refresh_fundamentals"
NEWS_JOB_ID = "refresh_news"
SNAPSHOT_JOB_ID = "write_daily_snapshot"

# The schedule itself is the human-readable TTL policy (Key Technical
# Decisions): fundamentals and the snapshot refresh daily (FMP's free
# tier is ~250 requests/day; R12's snapshot is explicitly a once-daily
# write); news refreshes more often since Finnhub's free tier (60
# calls/min) comfortably allows it.
_FUNDAMENTALS_INTERVAL = IntervalTrigger(hours=24)
_NEWS_INTERVAL = IntervalTrigger(hours=4)
_SNAPSHOT_INTERVAL = IntervalTrigger(hours=24)


async def _current_holdings(app_state: Any) -> list[Any] | None:  # noqa: ANN401
    """Return the user's current `PositionView`s, or `None` if a run should be skipped.

    Shared by all three jobs: each needs the same "what do we currently
    hold" starting point.  Personal-key credentials come from settings
    (pre-provisioned at SnapTrade signup); no DB row is consulted.
    Returns `None` only when SnapTrade itself is unavailable -- an empty
    list (no brokerage linked yet) propagates through so the job loops
    over nothing rather than crashing.
    """
    settings = get_settings()
    async with app_state.session_factory() as session:
        snaptrade = SnapTradeService(
            client=app_state.snaptrade_client,
            cache=CacheRepository(session),
            user_id=settings.snaptrade_user_id.get_secret_value(),
            user_secret=settings.snaptrade_user_secret.get_secret_value(),
        )
        try:
            positions = await snaptrade.list_positions()
        except ProviderUnavailableError as exc:
            logger.warning("Skipping scheduled run: SnapTrade unavailable: %s", exc)
            return None
        return list(positions.value)


async def refresh_fundamentals(app_state: Any) -> None:  # noqa: ANN401
    """Refresh cached FMP fundamentals for every currently-held symbol."""
    holdings = await _current_holdings(app_state)
    if holdings is None:
        logger.info("refresh_fundamentals: no current holdings, skipping run.")
        return

    for symbol in sorted({holding.symbol for holding in holdings}):
        async with app_state.session_factory() as session:
            fmp = FmpService(client=app_state.fmp_client, cache=CacheRepository(session))
            try:
                await fmp.get_fundamentals(symbol)
            except (ProviderUnavailableError, ProviderNotFoundError) as exc:
                logger.warning("refresh_fundamentals: failed for %s: %s", symbol, exc)
                continue


async def refresh_news(app_state: Any) -> None:  # noqa: ANN401
    """Refresh cached Finnhub news for every currently-held symbol."""
    holdings = await _current_holdings(app_state)
    if holdings is None:
        logger.info("refresh_news: no current holdings, skipping run.")
        return

    for symbol in sorted({holding.symbol for holding in holdings}):
        async with app_state.session_factory() as session:
            finnhub = FinnhubService(
                client=app_state.finnhub_client, cache=CacheRepository(session)
            )
            try:
                await finnhub.get_news_for_symbols([symbol])
            except ProviderUnavailableError as exc:
                logger.warning("refresh_news: failed for %s: %s", symbol, exc)
                continue


async def write_daily_snapshot(app_state: Any) -> None:  # noqa: ANN401
    """Write one `portfolio_snapshots` row per currently-held symbol.

    Write-only (R12): reuses `market_value`/`allocation_pct` already
    computed by `SnapTradeService.list_positions` (via U2's own
    `compute_allocation`) rather than recomputing them -- no
    comparison/trend query exists anywhere in this codebase yet, see
    `db/models.py`'s `PortfolioSnapshot` docstring.
    """
    holdings = await _current_holdings(app_state)
    if holdings is None:
        logger.info("write_daily_snapshot: no current holdings, skipping run.")
        return

    today = dt.datetime.now(dt.UTC).date()
    async with app_state.session_factory() as session:
        for holding in holdings:
            session.add(
                PortfolioSnapshot(
                    snapshot_date=today,
                    symbol=holding.symbol,
                    market_value=holding.market_value,
                    allocation_pct=holding.allocation_pct,
                )
            )
        await session.commit()


def register_jobs(scheduler: AsyncIOScheduler, app_state: Any) -> None:  # noqa: ANN401
    """Register every scheduled job on `scheduler`, bound to `app_state`'s shared resources."""
    scheduler.add_job(
        refresh_fundamentals, _FUNDAMENTALS_INTERVAL, args=[app_state], id=FUNDAMENTALS_JOB_ID
    )
    scheduler.add_job(refresh_news, _NEWS_INTERVAL, args=[app_state], id=NEWS_JOB_ID)
    scheduler.add_job(
        write_daily_snapshot, _SNAPSHOT_INTERVAL, args=[app_state], id=SNAPSHOT_JOB_ID
    )
