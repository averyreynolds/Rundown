"""Fixtures shared across `tests/api/` route-level tests."""

from collections.abc import Callable, Iterator
from typing import Any

import pytest

from app.api.dependencies import get_claude_client, get_snaptrade_client
from app.main import app
from tests.fixtures.synthetic_positions import build_fake_snaptrade_client


@pytest.fixture
def set_fake_snaptrade_client() -> Iterator[Callable[..., Any]]:
    """Override `get_snaptrade_client` for this test only, cleaned up after.

    Needed by any route test touching `/portfolio/*` (and the smoke
    suite) so the route never touches the real lifespan-constructed
    SnapTrade SDK client, which would otherwise attempt a live network
    call.
    """

    def _set(**kwargs: Any) -> Any:  # noqa: ANN401
        client = build_fake_snaptrade_client(**kwargs)
        app.dependency_overrides[get_snaptrade_client] = lambda: client
        return client

    yield _set
    app.dependency_overrides.pop(get_snaptrade_client, None)


@pytest.fixture
def set_fake_claude_client() -> Iterator[Callable[..., Any]]:
    """Override `get_claude_client` for this test only, cleaned up after.

    Needed by any route test touching `/advisor/*` so the route never
    touches the real lifespan-constructed Anthropic client, which would
    otherwise attempt a live API call.
    """

    def _set(client: Any) -> None:  # noqa: ANN401
        app.dependency_overrides[get_claude_client] = lambda: client

    yield _set
    app.dependency_overrides.pop(get_claude_client, None)
