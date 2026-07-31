"""Tests for `app.services.snaptrade_service.SnapTradeService`.

The SnapTrade SDK client is a fake built by
`tests.fixtures.synthetic_positions.build_fake_snaptrade_client` -- this
suite never touches the live network or the real SDK's `aiohttp`-based
transport.
"""

import pytest
from snaptrade_client.exceptions_base import OpenApiException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cache.cache_repository import CacheRepository
from app.services.errors import ProviderFetchError, ProviderUnavailableError
from app.services.snaptrade_service import SnapTradeService
from tests.fixtures.synthetic_positions import (
    build_fake_snaptrade_client,
    synthetic_account,
    synthetic_balance,
    synthetic_login_response,
    synthetic_option_position,
    synthetic_stock_position,
)


async def test_connect_returns_portal_url_without_registering_a_user(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """No local registration step: Personal-tier auth calls `login` directly.

    Unlike the partner/commercial flow, there's no `registerUser` call to
    dedupe or persist a secret from -- see the module docstring.
    """
    client = build_fake_snaptrade_client()

    async with db_session_factory() as session:
        service = SnapTradeService(client=client, cache=CacheRepository(session))
        first_url = await service.connect()
        second_url = await service.connect()

    assert first_url == synthetic_login_response()["redirectURI"]
    assert second_url == synthetic_login_response()["redirectURI"]
    assert client.authentication.alogin_snap_trade_user.call_count == 2


async def test_connect_when_snaptrade_login_fails_raises_provider_fetch_error(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_fake_snaptrade_client(login_error=OpenApiException("boom"))

    async with db_session_factory() as session:
        service = SnapTradeService(client=client, cache=CacheRepository(session))
        with pytest.raises(ProviderFetchError):
            await service.connect()


async def test_list_positions_with_no_linked_brokerage_returns_empty_list(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An empty accounts list (nothing linked yet) is a valid, successful response."""
    client = build_fake_snaptrade_client()

    async with db_session_factory() as session:
        service = SnapTradeService(client=client, cache=CacheRepository(session))
        result = await service.list_positions()

    assert result.source == "SnapTrade"
    assert result.value == []


async def test_list_positions_maps_holdings_and_filters_non_equity_kinds(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=[synthetic_stock_position(), synthetic_option_position()],
    )

    async with db_session_factory() as session:
        service = SnapTradeService(client=client, cache=CacheRepository(session))
        result = await service.list_positions()

    assert result.source == "SnapTrade"
    assert len(result.value) == 1
    view = result.value[0]
    assert view.symbol == "AAPL"
    assert view.market_value == view.quantity * view.current_price
    assert view.allocation_pct == 100
    assert view.unrealized_pnl_dollars == view.market_value - view.cost_basis


async def test_list_accounts_includes_balance(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_fake_snaptrade_client(
        accounts=[synthetic_account()], balance=synthetic_balance()
    )

    async with db_session_factory() as session:
        service = SnapTradeService(client=client, cache=CacheRepository(session))
        result = await service.list_accounts()

    assert len(result.value) == 1
    account = result.value[0]
    assert account.institution_name == "Synthetic Brokerage"
    assert account.cash == 1000
    assert account.buying_power == 2000


async def test_positions_cache_hit_within_ttl_does_not_trigger_second_sdk_call(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=[synthetic_stock_position()],
    )

    async with db_session_factory() as session:
        service = SnapTradeService(client=client, cache=CacheRepository(session))
        await service.list_positions()
    async with db_session_factory() as session:
        service = SnapTradeService(client=client, cache=CacheRepository(session))
        await service.list_positions()

    assert client.account_information.aget_all_account_positions.call_count == 1


async def test_provider_error_with_no_cache_raises_provider_unavailable(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions_error=OpenApiException("boom"),
    )

    async with db_session_factory() as session:
        service = SnapTradeService(client=client, cache=CacheRepository(session))
        with pytest.raises(ProviderUnavailableError):
            await service.list_positions()


async def test_provider_error_with_existing_cache_returns_stale_labeled_value(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client = build_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=[synthetic_stock_position()],
    )

    async with db_session_factory() as session:
        service = SnapTradeService(client=client, cache=CacheRepository(session))
        await service.list_positions()

        # Force the positions cache entry to be treated as expired.
        cache = CacheRepository(session)
        cached_payload = await cache.get_or_none("snaptrade", "positions:synthetic-account-1")
        await cache.set("snaptrade", "positions:synthetic-account-1", cached_payload, ttl_seconds=0)

    client.account_information.aget_all_account_positions.side_effect = OpenApiException("down")

    async with db_session_factory() as session:
        service = SnapTradeService(client=client, cache=CacheRepository(session))
        result = await service.list_positions()

    assert result.is_stale is True
    assert len(result.value) == 1


def test_service_module_never_imports_or_touches_trading_namespace() -> None:
    """Static, code-level enforcement of CLAUDE.md hard rule 7 (no trade execution).

    Parses the module's actual `import` statements and attribute accesses
    via `ast` rather than a naive substring search over the file text --
    the module's own docstring legitimately mentions "trading" in prose
    explaining *why* it's excluded, which a substring check would trip on.
    """
    import ast
    import inspect

    import app.services.snaptrade_service as module

    tree = ast.parse(inspect.getsource(module))

    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert not any("trading" in name.lower() for name in imported_modules)

    accessed_attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "trading" not in accessed_attributes
