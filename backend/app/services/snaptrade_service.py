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

**Personal-tier auth, not partner/commercial.** CLAUDE.md's free-tier
table calls out "Personal tier, 5 connections", and this service is built
for exactly that: a Personal SnapTrade API key is provisioned with its
one brokerage-linkable identity automatically at signup (verified live
against SnapTrade's API -- `POST /snapTrade/registerUser` responds `400
"Personal SnapTrade keys are provisioned with their user automatically at
signup... registerUser is not available for personal keys"` under a
Personal key). There is deliberately no local user-registration step
here, unlike the partner/commercial flow this SDK also supports: every
call below passes `_PLACEHOLDER_USER_ID`/`_PLACEHOLDER_USER_SECRET`,
which SnapTrade's API ignores for Personal keys (also verified live: an
arbitrary, never-registered `user_id`/`user_secret` pair returns the
same real linked-brokerage data as any other value) -- the account is
resolved entirely from which `client_id`/`consumer_key` pair signed the
request, set once in `app/main.py`'s `SnapTradeAuth.personal_api_key(...)`.
The SDK's method signatures still require *some* string for these two
parameters (they're shared with the partner/commercial code path), so
fixed placeholders are passed to satisfy that shape, not because their
content matters.

Field names for the SDK's response objects below (`redirectURI`, an
account's `id`/`name`/`institution_name`, a position's
`units`/`price`/`cost_basis`/`instrument.kind`/`instrument.symbol`) were
verified by introspecting the installed `snaptrade-python-sdk==12.0.3`
package's generated schema classes and by live calls against a real
Personal-tier SnapTrade account.
"""

import datetime as dt
from decimal import Decimal
from typing import Any

from snaptrade_client.exceptions_base import OpenApiException

from app.cache.cache_repository import CacheRepository
from app.cache.ttl_policy import positions_ttl_seconds
from app.domain.allocation import compute_allocation
from app.domain.pnl import compute_pnl
from app.domain.types import Holding
from app.schemas.common import SourcedValue
from app.schemas.portfolio import AccountSummary, PositionView
from app.services.cache_through import CachedResult, fetch_with_cache
from app.services.errors import ProviderFetchError

_PROVIDER = "snaptrade"
_SOURCE_NAME = "SnapTrade"


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# Personal-tier SnapTrade ignores these two values entirely (see module
# docstring) -- fixed placeholders, not real credentials, satisfying the
# SDK method signatures shared with the partner/commercial auth mode.
_PLACEHOLDER_USER_ID = "rundown-personal-tier-unused"
_PLACEHOLDER_USER_SECRET = "rundown-personal-tier-unused"  # noqa: S105

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


class SnapTradeService:
    """Generates connection-portal URLs and syncs accounts + positions for the one
    Personal-tier SnapTrade identity this app's `client_id`/`consumer_key` resolve to.

    `client` is a shared `SnapTrade` SDK instance constructed once in the
    lifespan, authenticated via `SnapTradeAuth.personal_api_key(...)`
    (`app/main.py`). Unlike the httpx-based provider clients, it needs no
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

    def __init__(self, client: Any, cache: CacheRepository) -> None:  # noqa: ANN401
        self._client = client
        self._cache = cache

    async def connect(self) -> str:
        """Return a fresh, short-lived SnapTrade connection portal URL.

        No local registration step (see module docstring): this always
        asks SnapTrade directly for a portal URL the user can open to
        link (or re-link/add another) brokerage account, read-only
        (`connection_type="read"`).
        """
        try:
            login_response = await self._client.authentication.alogin_snap_trade_user(
                user_id=_PLACEHOLDER_USER_ID,
                user_secret=_PLACEHOLDER_USER_SECRET,
                connection_type="read",
            )
        except OpenApiException as exc:
            raise ProviderFetchError("SnapTrade login (portal URL) request failed") from exc

        return str(login_response.body["redirectURI"])

    async def list_accounts(self) -> SourcedValue[list[AccountSummary]]:
        """Return every brokerage account known to SnapTrade, with its balance.

        An empty list is a valid, successful response (no brokerage
        linked yet) -- there is no "not connected" error state for a
        Personal-tier identity that always exists once configured.

        Raises:
            ProviderUnavailableError: SnapTrade is failing and nothing is cached.
        """
        accounts_result = await self._fetch_accounts()

        summaries: list[AccountSummary] = []
        as_of = accounts_result.as_of
        is_stale = accounts_result.is_stale
        for account in accounts_result.payload:
            balance_result = await self._fetch_balance(account["id"])
            as_of = min(as_of, balance_result.as_of)
            is_stale = is_stale or balance_result.is_stale
            # `get_user_account_balance` returns a *list* of per-currency
            # balance entries (verified live: `[{"currency": {"code":
            # "USD", ...}, "cash": ..., "buying_power": ...}]`), not a
            # single dict -- `AccountSummary` has one cash/buying_power/
            # currency triple, so this takes the first (primary) entry.
            # Multi-currency accounts would need this reconsidered; not a
            # concern for this single-user MVP.
            balances = balance_result.payload
            primary_balance = balances[0] if balances else {}
            currency = primary_balance.get("currency") or {}
            summaries.append(
                AccountSummary(
                    account_id=account["id"],
                    name=account["name"],
                    institution_name=account["institution_name"],
                    cash=_optional_decimal(primary_balance.get("cash")),
                    buying_power=_optional_decimal(primary_balance.get("buying_power")),
                    currency=currency.get("code"),
                )
            )

        return SourcedValue(value=summaries, source=_SOURCE_NAME, as_of=as_of, is_stale=is_stale)

    async def list_positions(self) -> SourcedValue[list[PositionView]]:
        """Return every equity-like holding across all accounts, with computed math.

        Kept account-scoped rather than merged across accounts by symbol:
        the same symbol held at two brokerages stays two rows. For a
        single-brokerage-account MVP user that's equivalent, and it's the
        smaller surface to extend later.

        An empty list is a valid, successful response (no brokerage
        linked yet) -- see `list_accounts`.

        Raises:
            ProviderUnavailableError: SnapTrade is failing and nothing is cached.
        """
        accounts_result = await self._fetch_accounts()

        holdings: list[Holding] = []
        account_ids: list[str] = []
        as_of = accounts_result.as_of
        is_stale = accounts_result.is_stale

        for account in accounts_result.payload:
            positions_result = await self._fetch_positions(account["id"])
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
                # SnapTrade reports `cost_basis` per share; `Holding.cost_basis`
                # is the position total.
                cost_basis_per_share = Decimal(str(raw_position["cost_basis"]))
                holdings.append(
                    Holding(
                        symbol=symbol,
                        quantity=units,
                        cost_basis=cost_basis_per_share * units,
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

    async def _fetch_accounts(self) -> CachedResult:
        return await fetch_with_cache(
            cache=self._cache,
            provider=_PROVIDER,
            cache_key="accounts",
            ttl_seconds=positions_ttl_seconds(),
            fetch_live=self._fetch_accounts_live,
            clock=_utcnow,
        )

    async def _fetch_accounts_live(self) -> list[dict[str, Any]]:
        try:
            response = await self._client.account_information.alist_user_accounts(
                user_id=_PLACEHOLDER_USER_ID, user_secret=_PLACEHOLDER_USER_SECRET
            )
        except OpenApiException as exc:
            raise ProviderFetchError("SnapTrade list_user_accounts failed") from exc
        return [dict(account) for account in response.body]

    async def _fetch_balance(self, account_id: str) -> CachedResult:
        return await fetch_with_cache(
            cache=self._cache,
            provider=_PROVIDER,
            cache_key=f"balance:{account_id}",
            ttl_seconds=positions_ttl_seconds(),
            fetch_live=lambda: self._fetch_balance_live(account_id),
            clock=_utcnow,
        )

    async def _fetch_balance_live(self, account_id: str) -> list[dict[str, Any]]:
        try:
            response = await self._client.account_information.aget_user_account_balance(
                account_id=account_id,
                user_id=_PLACEHOLDER_USER_ID,
                user_secret=_PLACEHOLDER_USER_SECRET,
            )
        except OpenApiException as exc:
            raise ProviderFetchError(
                f"SnapTrade get_user_account_balance failed for {account_id}"
            ) from exc
        return [dict(entry) for entry in response.body]

    async def _fetch_positions(self, account_id: str) -> CachedResult:
        return await fetch_with_cache(
            cache=self._cache,
            provider=_PROVIDER,
            cache_key=f"positions:{account_id}",
            ttl_seconds=positions_ttl_seconds(),
            fetch_live=lambda: self._fetch_positions_live(account_id),
            clock=_utcnow,
        )

    async def _fetch_positions_live(self, account_id: str) -> list[dict[str, Any]]:
        try:
            response = await self._client.account_information.aget_all_account_positions(
                account_id=account_id,
                user_id=_PLACEHOLDER_USER_ID,
                user_secret=_PLACEHOLDER_USER_SECRET,
            )
        except OpenApiException as exc:
            raise ProviderFetchError(
                f"SnapTrade get_all_account_positions failed for {account_id}"
            ) from exc
        # Unlike `list_user_accounts`/`get_user_account_balance` (bare
        # lists), this endpoint wraps its positions in `{"results": [...],
        # "data_freshness": {...}}` (verified live) -- each `results` entry
        # is otherwise shaped as assumed (`instrument`/`units`/`price`/
        # `cost_basis`).
        return [dict(position) for position in response.body["results"]]


def _optional_decimal(value: Any) -> Decimal | None:  # noqa: ANN401
    return None if value is None else Decimal(str(value))
