"""Integration tests for `POST /advisor/chat`.

Uses the shared `api_client` fixture (lifespan + DB isolation),
`set_fake_snaptrade_client` (portfolio context), and `set_fake_claude_client`
(so the route never touches the real Anthropic client).
"""

from collections.abc import Callable
from typing import Any

import httpx
from anthropic import APIError
from fastapi.testclient import TestClient

from tests.fixtures.synthetic_advisor import fake_anthropic_client
from tests.fixtures.synthetic_positions import (
    synthetic_account,
    synthetic_balance,
    synthetic_stock_position,
)


def test_chat_with_valid_token_returns_a_grounded_answer(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=[synthetic_stock_position()],
    )
    set_fake_claude_client(fake_anthropic_client("Your AAPL position is 100% of your portfolio."))

    connect_response = api_client.post("/portfolio/connect", headers=auth_headers)
    assert connect_response.status_code == 200

    response = api_client.post(
        "/advisor/chat",
        headers=auth_headers,
        json={"question": "How is my AAPL position doing?", "context_refs": {"symbols": ["AAPL"]}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Your AAPL position is 100% of your portfolio."
    assert body["citations"] == []


def test_chat_without_bearer_token_returns_401(api_client: TestClient) -> None:
    response = api_client.post("/advisor/chat", json={"question": "How is my portfolio doing?"})

    assert response.status_code == 401


def test_chat_with_no_context_available_returns_422(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client()  # never connected
    set_fake_claude_client(fake_anthropic_client())

    response = api_client.post(
        "/advisor/chat", headers=auth_headers, json={"question": "What's a P/E ratio?"}
    )

    assert response.status_code == 422


def test_chat_when_claude_is_unavailable_returns_502(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=[synthetic_stock_position()],
    )
    set_fake_claude_client(
        fake_anthropic_client(
            error=APIError(
                "boom",
                request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
                body=None,
            )
        )
    )

    connect_response = api_client.post("/portfolio/connect", headers=auth_headers)
    assert connect_response.status_code == 200

    response = api_client.post(
        "/advisor/chat", headers=auth_headers, json={"question": "How is my portfolio doing?"}
    )

    assert response.status_code == 502


def test_chat_with_directive_question_never_returns_directive_language(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    """End-to-end proof of the core legal boundary: even if the model
    responds with directive language, the client never sees it."""
    set_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=[synthetic_stock_position()],
    )
    set_fake_claude_client(fake_anthropic_client("You should sell your position now."))

    connect_response = api_client.post("/portfolio/connect", headers=auth_headers)
    assert connect_response.status_code == 200

    response = api_client.post(
        "/advisor/chat", headers=auth_headers, json={"question": "Should I sell NVDA?"}
    )

    assert response.status_code == 200
    assert "should sell" not in response.json()["answer"].lower()
