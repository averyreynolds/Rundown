"""Integration tests for `POST /advisor/chat`.

Uses the shared `api_client` fixture (lifespan + DB isolation),
`set_fake_snaptrade_client` (portfolio context), and `set_fake_claude_client`
(so the route never touches the real Anthropic client).
"""

import json
import logging
from collections.abc import Callable
from typing import Any

import httpx
import pytest
import respx
from anthropic import APIError
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services.claude_service import _SAFE_FALLBACK_MESSAGE
from tests.fixtures.synthetic_advisor import (
    citation_event,
    fake_anthropic_client,
    fake_streaming_anthropic_client,
)
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


# --- POST /advisor/chat/stream ---------------------------------------------------

_STREAM_URL = "/advisor/chat/stream"
_NEWS_URL = "https://finnhub.io/api/v1/company-news"
_RATIOS_URL = "https://financialmodelingprep.com/stable/ratios"
_KEY_METRICS_URL = "https://financialmodelingprep.com/stable/key-metrics-ttm"
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"


def _api_error() -> APIError:
    return APIError(
        "boom",
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        body=None,
    )


def _mock_providers(news: httpx.Response | None = None) -> None:
    respx.get(_RATIOS_URL).mock(return_value=httpx.Response(200, json=[{"symbol": "AAPL"}]))
    respx.get(_KEY_METRICS_URL).mock(return_value=httpx.Response(200, json=[{"symbol": "AAPL"}]))
    respx.get(_NEWS_URL).mock(return_value=news or httpx.Response(200, json=[]))
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json={}))


def _events(response: httpx.Response) -> list[tuple[str, dict[str, Any]]]:
    """Parse a server-sent event stream, checking each frame's name matches its payload."""
    parsed: list[tuple[str, dict[str, Any]]] = []
    for frame in response.text.split("\n\n"):
        if not frame.strip():
            continue
        name, data = frame.split("\n", 1)
        payload = json.loads(data.removeprefix("data: "))
        assert name.removeprefix("event: ") == payload["type"]
        parsed.append((payload["type"], payload))
    return parsed


def _names(events: list[tuple[str, dict[str, Any]]]) -> list[str]:
    return [name for name, _ in events]


def _sentences(events: list[tuple[str, dict[str, Any]]]) -> list[str]:
    return [payload["text"] for name, payload in events if name == "sentence"]


def _ask(
    api_client: TestClient,
    auth_headers: dict[str, str],
    question: str = "How is my portfolio doing?",
    symbols: list[str] | None = None,
) -> httpx.Response:
    return api_client.post(
        _STREAM_URL,
        headers=auth_headers,
        json={"question": question, "context_refs": {"symbols": symbols or []}},
    )


@pytest.fixture
def connected(set_fake_snaptrade_client: Callable[..., Any]) -> None:
    set_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=[
            synthetic_stock_position("AAPL", units=10, price=150.0, cost_basis_per_share=100.0),
            synthetic_stock_position("UNH", units=10, price=50.0, cost_basis_per_share=100.0),
        ],
    )


# Guard and reframe paths come first: this is the legal boundary (CLAUDE.md hard rule 1).


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_directive_text_never_appears_and_retracts_earlier_sentences(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    _mock_providers()
    client = fake_streaming_anthropic_client(
        "AAPL is 75% of your portfolio. ",
        "UNH is 25% of it. ",
        "You should sell your UNH position. ",
        "And another sentence after it.",
    )
    set_fake_claude_client(client)

    with caplog.at_level(logging.WARNING):
        response = _ask(api_client, auth_headers)

    assert response.status_code == 200
    assert "should sell" not in response.text.lower()
    events = _events(response)
    assert _sentences(events) == ["AAPL is 75% of your portfolio.", "UNH is 25% of it."]
    assert events[-1] == ("retract", {"type": "retract", "message": _SAFE_FALLBACK_MESSAGE})
    assert "done" not in _names(events)
    assert "forbidden directive-language" in caplog.text
    assert client.answer_stream.closed is True


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_catches_directive_phrasing_split_across_a_boundary(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    _mock_providers()
    set_fake_claude_client(
        fake_streaming_anthropic_client(
            "Given all this, you should\n", "\n", "sell your position.\n"
        )
    )

    response = _ask(api_client, auth_headers)

    assert "sell your position" not in response.text
    events = _events(response)
    assert _names(events)[-1] == "retract"


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_catches_directive_phrasing_hidden_by_markdown(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    _mock_providers()
    set_fake_claude_client(fake_streaming_anthropic_client("You **should** sell it."))

    response = _ask(api_client, auth_headers)

    assert "sell it" not in response.text
    assert _names(_events(response))[-1] == "retract"


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_directive_in_an_unterminated_final_fragment_is_still_caught(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    _mock_providers()
    set_fake_claude_client(fake_streaming_anthropic_client("AAPL is up. You should sell it"))

    response = _ask(api_client, auth_headers)

    assert "should sell" not in response.text
    assert _names(_events(response))[-1] == "retract"


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_should_i_sell_question_reframes_grounded_in_data(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    """Covers R10: not a refusal and not a recommendation."""
    _mock_providers()
    client = fake_streaming_anthropic_client(
        "Here's what's relevant to your UNH position. ", "It is 25% of your portfolio."
    )
    set_fake_claude_client(client)

    events = _events(_ask(api_client, auth_headers, "Should I sell UNH?"))

    assert _sentences(events) == [
        "Here's what's relevant to your UNH position.",
        "It is 25% of your portfolio.",
    ]
    assert _names(events)[-1] == "done"
    system = client.messages.stream.call_args.kwargs["system"]
    assert "should i buy/sell" in system.lower()
    assert "reframe it" in system.lower()
    assert "never give directive or prescriptive investment advice" in system.lower()


# The happy path and what each event carries.


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_sends_scope_reading_sentence_and_done_in_order(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    _mock_providers()
    set_fake_claude_client(
        fake_streaming_anthropic_client(
            "UNH makes up all of your loss. ",
            "The position cost $1,000. ",
            "AAPL is at today's value.",
        )
    )

    events = _events(_ask(api_client, auth_headers, "How is UNH?"))
    names = _names(events)

    assert names[0] == "scope"
    assert dict(events)["scope"]["symbols"] == ["UNH"]
    assert names[1:].index("sentence") > 0
    assert set(names[1 : names.index("sentence")]) == {"reading"}
    assert names[-1] == "done"

    sentences = [payload for name, payload in events if name == "sentence"]
    assert [(s["focus"], s["sizing"]) for s in sentences] == [
        (["UNH"], "gain"),
        (["UNH"], "cost"),
        (["AAPL"], "value"),
    ]


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_scope_is_every_position_when_a_question_names_none(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    _mock_providers()
    set_fake_claude_client(fake_streaming_anthropic_client("Your portfolio grew."))

    events = _events(_ask(api_client, auth_headers))

    assert dict(events)["scope"]["symbols"] == ["AAPL", "UNH"]


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_reports_each_source_with_its_as_of(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    _mock_providers(httpx.Response(200, json=[]))
    set_fake_claude_client(fake_streaming_anthropic_client("All good."))

    events = _events(_ask(api_client, auth_headers))

    readings = [payload for name, payload in events if name == "reading"]
    assert readings[0]["source"] == "SnapTrade positions"
    assert readings[0]["status"] == "used"
    assert readings[0]["as_of"]


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_shows_an_unreachable_source_as_unavailable_and_still_answers(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    _mock_providers(httpx.Response(500))
    set_fake_claude_client(fake_streaming_anthropic_client("Here is what the data shows."))

    events = _events(_ask(api_client, auth_headers, "How is UNH?"))

    readings = {p["source"]: p for name, p in events if name == "reading"}
    assert readings["Finnhub news"]["status"] == "unavailable"
    assert readings["Finnhub news"]["as_of"] is None
    assert _sentences(events) == ["Here is what the data shows."]
    assert _names(events)[-1] == "done"


@respx.mock
def test_stream_labels_stale_positions(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
    set_fake_claude_client: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from snaptrade_client.exceptions_base import OpenApiException

    _mock_providers()
    client = set_fake_snaptrade_client(
        accounts=[synthetic_account()],
        balance=synthetic_balance(),
        positions=[synthetic_stock_position()],
    )
    monkeypatch.setattr("app.services.snaptrade_service.positions_ttl_seconds", lambda: 0)
    api_client.get("/portfolio/positions", headers=auth_headers)
    client.account_information.aget_all_account_positions.side_effect = OpenApiException("down")
    set_fake_claude_client(fake_streaming_anthropic_client("All good."))

    events = _events(_ask(api_client, auth_headers))

    readings = {p["source"]: p for name, p in events if name == "reading"}
    assert readings["SnapTrade positions"]["status"] == "stale"


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_done_lists_sources_and_complete_follow_up_questions(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    _mock_providers()
    set_fake_claude_client(fake_streaming_anthropic_client("UNH is down."))

    done = dict(_events(_ask(api_client, auth_headers, "How is UNH?")))["done"]

    assert "SnapTrade positions" in [source["source"] for source in done["sources"]]
    assert done["follow_ups"] == [
        "How much of my gain comes from UNH?",
        "What's in the news about UNH?",
        "What's relevant to my AAPL position?",
    ]


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_attaches_each_citation_to_the_next_sentence_released(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    _mock_providers()
    set_fake_claude_client(
        fake_streaming_anthropic_client(
            citation_event("Quoted first."),
            "Margins fell. ",
            "Revenue rose.",
            citation_event("Quoted last."),
        )
    )

    events = _events(_ask(api_client, auth_headers))

    sentences = [payload for name, payload in events if name == "sentence"]
    assert [c["quote"] for c in sentences[0]["citations"]] == ["Quoted first."]
    assert [c["quote"] for c in sentences[1]["citations"]] == ["Quoted last."]
    assert dict(events)["done"]["citations"] == []


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_keeps_a_citation_with_no_sentence_at_the_answer_level(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    _mock_providers()
    set_fake_claude_client(
        fake_streaming_anthropic_client(
            "A whole sentence. ",
            "Next one is cut",
            citation_event("Quoted."),
            mid_error=httpx.ReadError("connection lost"),
        )
    )

    interrupted = dict(_events(_ask(api_client, auth_headers)))["interrupted"]

    assert [c["quote"] for c in interrupted["citations"]] == ["Quoted."]


# Failures before and during the answer.


def test_stream_without_bearer_token_returns_401(api_client: TestClient) -> None:
    assert api_client.post(_STREAM_URL, json={"question": "How?"}).status_code == 401


def test_stream_with_no_context_returns_422_before_streaming(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_snaptrade_client: Callable[..., Any],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    set_fake_snaptrade_client()
    client = fake_streaming_anthropic_client("Never sent.")
    set_fake_claude_client(client)

    response = _ask(api_client, auth_headers)

    assert response.status_code == 422
    client.messages.stream.assert_not_called()


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_claude_failure_before_any_text_returns_502(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    _mock_providers()
    set_fake_claude_client(fake_streaming_anthropic_client(open_error=_api_error()))

    assert _ask(api_client, auth_headers).status_code == 502


@pytest.mark.usefixtures("connected")
@respx.mock
@pytest.mark.parametrize("error_type", ["api", "transport"])
def test_stream_claude_failure_mid_answer_sends_interrupted_and_drops_the_fragment(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
    error_type: str,
) -> None:
    _mock_providers()
    error = _api_error() if error_type == "api" else httpx.ReadError("connection lost")
    client = fake_streaming_anthropic_client(
        "A whole sentence. ", "Another whole one. ", "A half-writ", mid_error=error
    )
    set_fake_claude_client(client)

    events = _events(_ask(api_client, auth_headers))

    assert _sentences(events) == ["A whole sentence.", "Another whole one."]
    assert "half-writ" not in str(events)
    assert dict(events)["interrupted"]["reason"] == "unavailable"
    assert _names(events)[-1] == "interrupted"
    assert client.answer_stream.closed is True


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_token_limit_sends_incomplete_and_keeps_what_was_written(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    _mock_providers()
    set_fake_claude_client(
        fake_streaming_anthropic_client(
            "A whole sentence. ", "A cut-off one", stop_reason="max_tokens"
        )
    )

    events = _events(_ask(api_client, auth_headers))

    assert _sentences(events) == ["A whole sentence.", "A cut-off one"]
    assert _names(events)[-1] == "incomplete"


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_refusal_sends_interrupted_without_the_fragment(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    _mock_providers()
    set_fake_claude_client(
        fake_streaming_anthropic_client("A whole sentence. Next", stop_reason="refusal")
    )

    events = _events(_ask(api_client, auth_headers))

    assert _sentences(events) == ["A whole sentence."]
    assert dict(events)["interrupted"]["reason"] == "declined"


@pytest.mark.usefixtures("connected")
@respx.mock
@pytest.mark.parametrize("chunks", [(), ("   ", "\n")])
def test_stream_empty_completion_is_treated_as_unavailable(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
    chunks: tuple[str, ...],
) -> None:
    _mock_providers()
    set_fake_claude_client(fake_streaming_anthropic_client(*chunks))

    events = _events(_ask(api_client, auth_headers))

    assert _sentences(events) == []
    assert dict(events)["interrupted"]["reason"] == "unavailable"


@pytest.mark.usefixtures("connected")
@respx.mock
def test_stream_is_server_sent_events_and_leaks_no_key(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    _mock_providers()
    set_fake_claude_client(fake_streaming_anthropic_client("All good."))

    with caplog.at_level(logging.DEBUG):
        response = _ask(api_client, auth_headers)

    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    settings = get_settings()
    for secret in (
        settings.anthropic_api_key.get_secret_value(),
        settings.api_bearer_token.get_secret_value(),
    ):
        assert secret not in response.text
        assert secret not in caplog.text


@pytest.mark.usefixtures("connected")
@respx.mock
def test_chat_and_stream_ground_the_model_in_the_same_context(
    api_client: TestClient,
    auth_headers: dict[str, str],
    set_fake_claude_client: Callable[..., Any],
) -> None:
    """One assembly path, so what each endpoint is grounded in can't drift."""
    _mock_providers()
    chat_client = fake_anthropic_client("Fine.")
    set_fake_claude_client(chat_client)
    api_client.post(
        "/advisor/chat", headers=auth_headers, json={"question": "How is my portfolio?"}
    )
    stream_client = fake_streaming_anthropic_client("Fine.")
    set_fake_claude_client(stream_client)
    _ask(api_client, auth_headers, "How is my portfolio?")

    sent_to_chat = chat_client.messages.create.await_args.kwargs
    sent_to_stream = stream_client.messages.stream.call_args.kwargs
    assert sent_to_stream["messages"] == sent_to_chat["messages"]
    assert sent_to_stream["system"] == sent_to_chat["system"]
    assert sent_to_stream["max_tokens"] == sent_to_chat["max_tokens"]
    assert sent_to_stream["model"] == sent_to_chat["model"]
