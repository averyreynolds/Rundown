"""SnapTrade integration: read-only brokerage connection and holdings sync.

Read-only by construction at the code level: this module imports only the
SnapTrade SDK's `authentication` and `account_information` API
namespaces, never `trading` -- CLAUDE.md hard rule 7 forbids any
trade/order/transfer code path, and this is the one place that guarantee
is enforced structurally rather than left as a convention to remember
(checked in code review, per the plan's Verification criteria for this
unit -- a static property, not something a runtime test can prove).

Whether SnapTrade/the brokerage also enforces `connection_type="read"` at
the OAuth-consent level (a hard platform-side boundary) or treats it only
as a request-shape hint to the connection portal is *not* independently
verified here -- this plan's research couldn't confirm it without a live
SnapTrade account or sandbox, and `backend/README.md` flags this
explicitly. Treat the code-level import restriction above as the
guarantee that's actually enforced until that's confirmed.

Field names for the SDK's response objects below (`userId`/`userSecret`,
`redirectURI`, an account's `id`/`name`/`institution_name`, a position's
`units`/`price`/`cost_basis`/`instrument.kind`/`instrument.symbol`) were
verified by introspecting the installed `snaptrade-python-sdk==12.0.3`
package's generated schema classes directly (no live API key is
available in this environment to verify against a real response) --
re-verify against a real account once credentials exist, per this plan's
Risks & Dependencies.
"""

import asyncio
import datetime as dt
from decimal import Decimal
from typing import Any

from snaptrade_client.exceptions_base import OpenApiException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.cache_repository import CacheRepository
from app.cache.ttl_policy import positions_ttl_seconds
from app.db.models import SnaptradeConnection
from app.domain.allocation import compute_allocation
from app.domain.pnl import compute_pnl
from app.domain.types import Holding
from app.schemas.common import SourcedValue
from app.schemas.portfolio import AccountSummary, PositionView
from app.services.cache_through import CachedResult, fetch_with_cache
from app.services.errors import NotConnectedError, ProviderFetchError

_PROVIDER = "snaptrade"
_SOURCE_NAME = "SnapTrade"

# Single-user MVP (CLAUDE.md: "single-user, greenfield"): one fixed local
# user id rather than a multi-user id scheme.
_LOCAL_USER_ID = "rundown-local-user"

# SnapTrade instrument "kind" values this dashboard treats as ordinary,
# priced-per-share equity holdings. Options/crypto/futures/mutual
# funds/CFDs are a different asset class than CLAUDE.md's "equity
# holdings" framing and are excluded here rather than mapped into
# `Holding`. Checked case-insensitively since the discriminator's wire
# value (lowercase "stock" vs the class name "StockInstrument") isn't
# independently confirmed without a live response.
_EQUITY_LIKE_KINDS = {
    "stock",
    "stockinstrument",
    "etf",
    "etfinstrument",
    "adr",
    "adrinstrument",
    "cef",
    "cefinstrument",
}


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# Guards the check-then-register-then-persist sequence in `connect()`.
# Module-level (not per-instance) because a fresh `SnapTradeService` is
# constructed per request (see `api/dependencies.py`), so a per-instance
# lock would never actually contend across two concurrent requests. This
# is a single-process, single-worker app throughout the plan (APScheduler
# carries the same constraint in U9), so an `asyncio.Lock` fully closes
# the race within that one process -- without it, two near-simultaneous
# `POST /portfolio/connect` calls could each see "no connection yet" and
# both call SnapTrade's registration endpoint, not just both attempt a
# local insert.
_registration_lock = asyncio.Lock()


class SnapTradeService:
    """Registers/logs in a local user (read-only) and syncs accounts + positions.

    `client` is a shared `SnapTrade` SDK instance constructed once in the
    lifespan. Unlike the httpx-based provider clients, it needs no
    explicit teardown: its async methods open a fresh `aiohttp` session
    per call rather than holding one open (see the SDK's `rest.py`), so
    there is no connection pool for this service to close.

    Typed as `Any` here rather than `SnapTrade[Any]`: the installed
    `snaptrade-python-sdk`'s generated, multiply-inherited API classes
    (`AuthenticationApi`, `AccountInformationApi`) don't resolve their own
    methods under mypy strict mode even though they exist at runtime
    (verified directly against the installed package -- see this module's
    top docstring), so a precise annotation would need a `type: ignore` at
    every call site below for no real type-safety benefit. This also lets
    tests substitute a structurally-compatible fake instead of the real
    SDK class.
    """

    def __init__(self, client: Any, cache: CacheRepository, session: AsyncSession) -> None:  # noqa: ANN401
        self._client = client
        self._cache = cache
        self._session = session

    async def connect(self) -> str:
        """Ensure the local user is registered with SnapTrade; return a portal URL.

        Registers once (persisting the returned `user_secret`) if no
        connection exists yet; reuses the persisted secret otherwise.
        Always calls `alogin_snap_trade_user(..., connection_type="read")`
        for a fresh portal URL, since those are short-lived/single-use.
        """
        connection = await self._get_connection()
        if connection is None:
            async with _registration_lock:
                # Re-check after acquiring the lock: another task may have
                # registered and committed while this one was waiting.
                connection = await self._get_connection()
                if connection is None:
                    try:
                        response = await self._client.authentication.aregister_snap_trade_user(
                            user_id=_LOCAL_USER_ID
                        )
                    except OpenApiException as exc:
                        raise ProviderFetchError("SnapTrade user registration failed") from exc
                    connection = await self._save_connection(
                        user_id=response.body["userId"],
                        user_secret=response.body["userSecret"],
                    )

        try:
            login_response = await self._client.authentication.alogin_snap_trade_user(
                user_id=connection.user_id,
                user_secret=connection.user_secret,
                connection_type="read",
            )
        except OpenApiException as exc:
            raise ProviderFetchError("SnapTrade login (portal URL) request failed") from exc

        return str(login_response.body["redirectURI"])

    async def list_accounts(self) -> SourcedValue[list[AccountSummary]]:
        """Return every brokerage account known to SnapTrade, with its balance.

        Raises:
            NotConnectedError: no SnapTrade connection exists yet.
            ProviderUnavailableError: SnapTrade is failing and nothing is cached.
        """
        connection = await self._require_connection()
        accounts_result = await self._fetch_accounts(connection)

        summaries: list[AccountSummary] = []
        as_of = accounts_result.as_of
        is_stale = accounts_result.is_stale
        for account in accounts_result.payload:
            balance_result = await self._fetch_balance(connection, account["id"])
            as_of = min(as_of, balance_result.as_of)
            is_stale = is_stale or balance_result.is_stale
            balance = balance_result.payload
            summaries.append(
                AccountSummary(
                    account_id=account["id"],
                    name=account["name"],
                    institution_name=account["institution_name"],
                    cash=_optional_decimal(balance.get("cash")),
                    buying_power=_optional_decimal(balance.get("buying_power")),
                    currency=balance.get("currency"),
                )
            )

        return SourcedValue(value=summaries, source=_SOURCE_NAME, as_of=as_of, is_stale=is_stale)

    async def list_positions(self) -> SourcedValue[list[PositionView]]:
        """Return every equity-like holding across all accounts, with computed math.

        Kept account-scoped rather than merged across accounts by symbol:
        merging would require weighted-averaging `cost_basis` across
        accounts, and this plan has no live SnapTrade response to confirm
        whether that field is a total or per-share figure. Getting that
        wrong would silently produce an incorrect cost basis (CLAUDE.md
        rule 6) -- for a single-brokerage-account MVP user this is
        equivalent anyway, and it's a smaller, safer surface to extend
        later once a live response confirms the field's units.

        Raises:
            NotConnectedError: no SnapTrade connection exists yet.
            ProviderUnavailableError: SnapTrade is failing and nothing is cached.
        """
        connection = await self._require_connection()
        accounts_result = await self._fetch_accounts(connection)

        holdings: list[Holding] = []
        account_ids: list[str] = []
        as_of = accounts_result.as_of
        is_stale = accounts_result.is_stale

        for account in accounts_result.payload:
            positions_result = await self._fetch_positions(connection, account["id"])
            as_of = min(as_of, positions_result.as_of)
            is_stale = is_stale or positions_result.is_stale

            for raw_position in positions_result.payload:
                instrument = raw_position["instrument"]
                kind = str(instrument.get("kind", "")).lower()
                if kind not in _EQUITY_LIKE_KINDS:
                    continue

                symbol = instrument.get("symbol") or instrument.get("raw_symbol")
                units = Decimal(str(raw_position["units"]))
                price = Decimal(str(raw_position["price"]))
                holdings.append(
                    Holding(
                        symbol=symbol,
                        quantity=units,
                        cost_basis=Decimal(str(raw_position["cost_basis"])),
                        current_price=price,
                        market_value=units * price,
                    )
                )
                account_ids.append(account["id"])

        allocations = compute_allocation(holdings) if holdings else []
        views = [
            PositionView(
                symbol=holding.symbol,
                account_id=account_id,
                quantity=holding.quantity,
                cost_basis=holding.cost_basis,
                current_price=holding.current_price,
                market_value=holding.market_value,
                allocation_pct=allocation.percent,
                unrealized_pnl_dollars=compute_pnl(holding).dollars,
                unrealized_pnl_percent=compute_pnl(holding).percent,
            )
            for holding, allocation, account_id in zip(
                holdings, allocations, account_ids, strict=True
            )
        ]

        return SourcedValue(value=views, source=_SOURCE_NAME, as_of=as_of, is_stale=is_stale)

    async def _require_connection(self) -> SnaptradeConnection:
        connection = await self._get_connection()
        if connection is None:
            raise NotConnectedError()
        return connection

    async def _get_connection(self) -> SnaptradeConnection | None:
        stmt = select(SnaptradeConnection).where(SnaptradeConnection.user_id == _LOCAL_USER_ID)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def _save_connection(self, user_id: str, user_secret: str) -> SnaptradeConnection:
        """Insert the new connection row, or return the existing one on a race.

        Two concurrent `connect()` calls against an empty table could both
        reach this method; whichever commits first wins, and the loser's
        `IntegrityError` on the `user_id` unique constraint is caught here
        and turned into a re-read of the winning row, rather than
        surfacing as an unhandled error or leaving an orphaned SnapTrade
        registration unrecorded locally.
        """
        connection = SnaptradeConnection(
            user_id=user_id, user_secret=user_secret, connected_at=_utcnow()
        )
        self._session.add(connection)
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            existing = await self._get_connection()
            if existing is None:
                raise  # pragma: no cover -- conflict implies a row exists
            return existing
        return connection

    async def _fetch_accounts(self, connection: SnaptradeConnection) -> CachedResult:
        return await fetch_with_cache(
            cache=self._cache,
            provider=_PROVIDER,
            cache_key="accounts",
            ttl_seconds=positions_ttl_seconds(),
            fetch_live=lambda: self._fetch_accounts_live(connection),
            clock=_utcnow,
        )

    async def _fetch_accounts_live(self, connection: SnaptradeConnection) -> list[dict[str, Any]]:
        try:
            response = await self._client.account_information.alist_user_accounts(
                user_id=connection.user_id, user_secret=connection.user_secret
            )
        except OpenApiException as exc:
            raise ProviderFetchError("SnapTrade list_user_accounts failed") from exc
        return [dict(account) for account in response.body]

    async def _fetch_balance(
        self, connection: SnaptradeConnection, account_id: str
    ) -> CachedResult:
        return await fetch_with_cache(
            cache=self._cache,
            provider=_PROVIDER,
            cache_key=f"balance:{account_id}",
            ttl_seconds=positions_ttl_seconds(),
            fetch_live=lambda: self._fetch_balance_live(connection, account_id),
            clock=_utcnow,
        )

    async def _fetch_balance_live(
        self, connection: SnaptradeConnection, account_id: str
    ) -> dict[str, Any]:
        try:
            response = await self._client.account_information.aget_user_account_balance(
                account_id=account_id,
                user_id=connection.user_id,
                user_secret=connection.user_secret,
            )
        except OpenApiException as exc:
            raise ProviderFetchError(
                f"SnapTrade get_user_account_balance failed for {account_id}"
            ) from exc
        return dict(response.body)

    async def _fetch_positions(
        self, connection: SnaptradeConnection, account_id: str
    ) -> CachedResult:
        return await fetch_with_cache(
            cache=self._cache,
            provider=_PROVIDER,
            cache_key=f"positions:{account_id}",
            ttl_seconds=positions_ttl_seconds(),
            fetch_live=lambda: self._fetch_positions_live(connection, account_id),
            clock=_utcnow,
        )

    async def _fetch_positions_live(
        self, connection: SnaptradeConnection, account_id: str
    ) -> list[dict[str, Any]]:
        try:
            response = await self._client.account_information.aget_all_account_positions(
                account_id=account_id,
                user_id=connection.user_id,
                user_secret=connection.user_secret,
            )
        except OpenApiException as exc:
            raise ProviderFetchError(
                f"SnapTrade get_all_account_positions failed for {account_id}"
            ) from exc
        return [dict(position) for position in response.body]


def _optional_decimal(value: Any) -> Decimal | None:  # noqa: ANN401
    return None if value is None else Decimal(str(value))
