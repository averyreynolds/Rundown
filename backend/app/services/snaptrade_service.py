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
verified here -- treat the code-level import restriction above as the
guarantee that's actually enforced.

**Personal-key auth flow.**  This app uses a SnapTrade *personal* API key
(not the commercial/partner key).  Personal keys come with a userId and
userSecret pre-provisioned for the account owner at signup -- the
`registerUser` endpoint (partner-only, code 1012) is neither called nor
imported.  Credentials come from `.env` via `Settings` and are passed in
at construction time; no DB row is written or read for authentication.

The SDK client must be constructed with
`auth=SnapTradeAuth.personal_api_key(...)` so that `request_after_hook`
sets `configuration.auth_mode` and actually attaches the HMAC `Signature`
header.  Without an explicit auth mode the SDK sends every request
unsigned, producing a 403.

Field names for the SDK's response objects below (`redirectURI`, an
account's `id`/`name`/`institution_name`, a position's
`units`/`price`/`cost_basis`/`instrument.kind`/`instrument.symbol`) were
verified by introspecting the installed `snaptrade-python-sdk==12.0.3`
package's generated schema classes directly -- re-verify against a real
account once credentials are wired up.
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


class SnapTradeService:
    """Generates a Connect Portal URL and syncs accounts + positions.

    `client` is a shared `SnapTrade` SDK instance constructed once in the
    lifespan with `auth=SnapTradeAuth.personal_api_key(...)`.  Unlike the
    httpx-based provider clients, it needs no explicit teardown: its async
    methods open a fresh `aiohttp` session per call rather than holding
    one open (see the SDK's `rest.py`).

    `user_id` / `user_secret` are the personal-key account owner's
    pre-provisioned SnapTrade credentials, sourced from `Settings` and
    passed in at construction time rather than looked up in the DB.

    Typed as `Any` here rather than `SnapTrade[Any]`: the installed
    `snaptrade-python-sdk`'s generated, multiply-inherited API classes
    don't resolve their own methods under mypy strict mode even though
    they exist at runtime, so a precise annotation would need a
    `type: ignore` at every call site below for no real type-safety
    benefit.  This also lets tests substitute a structurally-compatible
    fake instead of the real SDK class.
    """

    def __init__(
        self,
        client: Any,  # noqa: ANN401
        cache: CacheRepository,
        user_id: str,
        user_secret: str,
    ) -> None:
        self._client = client
        self._cache = cache
        self._user_id = user_id
        self._user_secret = user_secret

    async def connect(self) -> str:
        """Return a fresh read-only Connection Portal URL for this personal-key user.

        Personal-key users are pre-provisioned by SnapTrade at signup, so
        there is no registration step -- we call `alogin_snap_trade_user`
        directly every time to get a fresh (single-use) portal URL.
        `connection_type="read"` requests a read-only consent scope at the
        OAuth-consent level.
        """
        try:
            response = await self._client.authentication.alogin_snap_trade_user(
                user_id=self._user_id,
                user_secret=self._user_secret,
                connection_type="read",
            )
        except OpenApiException as exc:
            raise ProviderFetchError("SnapTrade login (portal URL) request failed") from exc
        return str(response.body["redirectURI"])

    async def list_accounts(self) -> SourcedValue[list[AccountSummary]]:
        """Return every brokerage account known to SnapTrade, with its balance.

        Returns an empty list if no brokerage accounts are linked yet
        (user hasn't completed a Connect Portal flow).

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
        whether that field is a total or per-share figure.

        Returns an empty list if no brokerage accounts are linked yet.

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
                user_id=self._user_id,
                user_secret=self._user_secret,
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

    async def _fetch_balance_live(self, account_id: str) -> dict[str, Any]:
        try:
            response = await self._client.account_information.aget_user_account_balance(
                account_id=account_id,
                user_id=self._user_id,
                user_secret=self._user_secret,
            )
        except OpenApiException as exc:
            raise ProviderFetchError(
                f"SnapTrade get_user_account_balance failed for {account_id}"
            ) from exc
        return dict(response.body)

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
                user_id=self._user_id,
                user_secret=self._user_secret,
            )
        except OpenApiException as exc:
            raise ProviderFetchError(
                f"SnapTrade get_all_account_positions failed for {account_id}"
            ) from exc
        return [dict(position) for position in response.body]


def _optional_decimal(value: Any) -> Decimal | None:  # noqa: ANN401
    return None if value is None else Decimal(str(value))
