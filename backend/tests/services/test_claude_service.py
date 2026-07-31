"""Tests for `app.services.claude_service.ClaudeService`.

The Anthropic client is a plain `SimpleNamespace`/`AsyncMock` matching
only the `.messages.create()` surface `ClaudeService` actually calls --
no live API key is used or required. This is the highest-risk module in
the codebase (CLAUDE.md hard rules 1 and 2), so this suite is organized
around the plan's explicit test scenarios for U8, not just line coverage.
"""

from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import respx
from anthropic import APIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cache.cache_repository import CacheRepository
from app.schemas.advisor import ContextRefs, FilingRef
from app.services.claude_service import (
    _SAFE_FALLBACK_MESSAGE,
    ClaudeService,
    contains_directive_language,
)
from app.services.edgar_service import EdgarService
from app.services.errors import AdvisorUnavailableError, InsufficientContextError
from app.services.finnhub_service import FinnhubService
from app.services.fmp_service import FmpService
from app.services.snaptrade_service import SnapTradeService
from tests.fixtures.synthetic_advisor import fake_anthropic_client as _fake_anthropic_client
from tests.fixtures.synthetic_filing import (
    SYNTHETIC_FILING_TEXT,
    SYNTHETIC_TICKER_MAP,
    synthetic_submissions,
)
from tests.fixtures.synthetic_news import synthetic_news_items
from tests.fixtures.synthetic_positions import (
    build_fake_snaptrade_client,
    synthetic_account,
    synthetic_balance,
    synthetic_stock_position,
)

_RATIOS_URL = "https://financialmodelingprep.com/stable/ratios"
_KEY_METRICS_URL = "https://financialmodelingprep.com/stable/key-metrics-ttm"
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK0000320193.json"
_FILING_TEXT_URL = (
    "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/synthetic-10k.htm"
)
_NEWS_URL = "https://finnhub.io/api/v1/company-news"


async def _build_claude_service(
    session: AsyncSession,
    *,
    anthropic_client: SimpleNamespace,
    positions: list[dict[str, Any]] | None = None,
    connected: bool = True,
) -> ClaudeService:
    """Wire a `ClaudeService` to real sub-services sharing one DB session.

    Safe because `ClaudeService.chat()` awaits its sub-service calls
    sequentially, never concurrently, so one shared session/cache is fine
    for the lifetime of a single `chat()` call in these tests.
    """
    cache = CacheRepository(session)
    snaptrade_client = build_fake_snaptrade_client(
        accounts=[synthetic_account()] if connected else [],
        balance=synthetic_balance(),
        positions=positions if positions is not None else [synthetic_stock_position()],
    )
    snaptrade_service = SnapTradeService(client=snaptrade_client, cache=cache)

    return ClaudeService(
        client=anthropic_client,  # type: ignore[arg-type]
        model_id="claude-sonnet-5",
        snaptrade_service=snaptrade_service,
        fmp_service=FmpService(
            client=httpx.AsyncClient(base_url="https://financialmodelingprep.com"), cache=cache
        ),
        edgar_service=EdgarService(
            client=httpx.AsyncClient(headers={"User-Agent": "Rundown Test (test@example.com)"}),
            cache=cache,
        ),
        finnhub_service=FinnhubService(
            client=httpx.AsyncClient(base_url="https://finnhub.io"), cache=cache
        ),
    )


# --- Happy path: grounded only in injected context -------------------------


@respx.mock
async def test_chat_grounds_answer_only_in_the_symbols_asked_about(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    respx.get(_RATIOS_URL, params={"symbol": "AAPL"}).mock(
        return_value=httpx.Response(200, json=[{"symbol": "AAPL", "priceToEarningsRatio": 25.5}])
    )
    respx.get(_KEY_METRICS_URL, params={"symbol": "AAPL"}).mock(
        return_value=httpx.Response(200, json=[{"symbol": "AAPL", "revenuePerShareTTM": 6.5}])
    )
    respx.get(_NEWS_URL, params={"symbol": "AAPL"}).mock(
        return_value=httpx.Response(200, json=synthetic_news_items(1))
    )
    anthropic_client = _fake_anthropic_client("Your AAPL position is 100% of your portfolio.")

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session,
            anthropic_client=anthropic_client,
            positions=[
                synthetic_stock_position(symbol="AAPL"),
                synthetic_stock_position(symbol="MSFT"),
            ],
        )
        await service.chat("What does my AAPL position look like?", ContextRefs(symbols=["AAPL"]))

    sent = anthropic_client.messages.create.await_args.kwargs
    prompt_text = sent["messages"][0]["content"][-1]["text"]
    assert "AAPL" in prompt_text
    assert "Fundamentals for AAPL" in prompt_text
    assert "Recent news" in prompt_text
    # Only the requested symbol's holding is in context -- MSFT was never asked about.
    assert "MSFT" not in prompt_text
    assert "directive or prescriptive investment advice" in sent["system"].lower()


async def test_chat_with_no_context_available_raises_insufficient_context(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    anthropic_client = _fake_anthropic_client()
    async with db_session_factory() as session:
        service = await _build_claude_service(
            session, anthropic_client=anthropic_client, connected=False
        )
        with pytest.raises(InsufficientContextError):
            await service.chat("What's a P/E ratio?", ContextRefs())


# --- Filing summarization via the Citations API -----------------------------


@respx.mock
async def test_filing_summarization_returns_citations_from_the_source_filing(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    respx.get(_SUBMISSIONS_URL).mock(return_value=httpx.Response(200, json=synthetic_submissions()))
    respx.get(_FILING_TEXT_URL).mock(return_value=httpx.Response(200, text=SYNTHETIC_FILING_TEXT))
    citation = SimpleNamespace(cited_text="Synthetic filing text for testing only.")
    anthropic_client = _fake_anthropic_client(
        "The filing states: Synthetic filing text for testing only.", citations=[citation]
    )

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session, anthropic_client=anthropic_client, connected=False
        )
        response = await service.chat(
            "Summarize this filing.",
            ContextRefs(
                filing_ref=FilingRef(symbol="SYNT", accession_number="0000320193-24-000123")
            ),
        )

    assert len(response.citations) == 1
    assert response.citations[0].quote == "Synthetic filing text for testing only."
    assert "SEC EDGAR filing" in response.citations[0].source

    sent_content = anthropic_client.messages.create.await_args.kwargs["messages"][0]["content"]
    document_blocks = [block for block in sent_content if block.get("type") == "document"]
    assert len(document_blocks) == 1
    assert document_blocks[0]["citations"] == {"enabled": True}
    assert document_blocks[0]["source"]["data"] == SYNTHETIC_FILING_TEXT


@respx.mock
async def test_filing_summarization_for_unknown_symbol_raises_insufficient_context(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session, anthropic_client=anthropic_client, connected=False
        )
        with pytest.raises(InsufficientContextError):
            await service.chat(
                "Summarize this filing.",
                ContextRefs(filing_ref=FilingRef(symbol="NOTREAL", accession_number="000-00")),
            )


# --- The no-directive-advice boundary: the core legal requirement ----------

_DIRECTIVE_QUESTIONS = [
    "Should I sell NVDA?",
    "Should I buy more?",
    "Is now a good time to add to this position?",
    "What would you do here?",
]


@pytest.mark.parametrize("question", _DIRECTIVE_QUESTIONS)
async def test_directive_questions_are_sent_with_the_no_directive_system_prompt(
    db_session_factory: async_sessionmaker[AsyncSession], question: str
) -> None:
    anthropic_client = _fake_anthropic_client(
        "Here's what's relevant to that position based on your data."
    )

    async with db_session_factory() as session:
        service = await _build_claude_service(session, anthropic_client=anthropic_client)
        # Empty ContextRefs: relies on the connected portfolio alone, so no
        # FMP/Finnhub calls are needed just to check what was sent to Claude.
        await service.chat(question, ContextRefs())

    system_prompt = anthropic_client.messages.create.await_args.kwargs["system"].lower()
    assert "directive or prescriptive investment advice" in system_prompt
    assert "reframe it" in system_prompt


@pytest.mark.parametrize(
    "directive_response",
    [
        "You should sell your position now.",
        "I recommend buying more shares.",
        "Consider selling to lock in gains.",
        "Now is a good time to buy more.",
    ],
)
async def test_directive_model_response_is_replaced_with_the_safe_fallback(
    db_session_factory: async_sessionmaker[AsyncSession], directive_response: str
) -> None:
    anthropic_client = _fake_anthropic_client(directive_response)

    async with db_session_factory() as session:
        service = await _build_claude_service(session, anthropic_client=anthropic_client)
        response = await service.chat("Should I sell NVDA?", ContextRefs(symbols=["AAPL"]))

    assert response.answer == _SAFE_FALLBACK_MESSAGE
    assert response.citations == []


async def test_neutral_model_response_is_passed_through_unmodified(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    anthropic_client = _fake_anthropic_client(
        "Your AAPL position has an unrealized gain of $500, per the provided data."
    )

    async with db_session_factory() as session:
        service = await _build_claude_service(session, anthropic_client=anthropic_client)
        response = await service.chat(
            "How is my AAPL position doing?", ContextRefs(symbols=["AAPL"])
        )

    assert (
        response.answer
        == "Your AAPL position has an unrealized gain of $500, per the provided data."
    )


@respx.mock
async def test_output_filter_catches_directive_language_reflected_from_context(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Documents the filter's behavior when directive-style text originates from
    ingested third-party content (a news headline) rather than the model's own
    initiative -- the filter scans the model's final answer regardless of where
    the phrasing came from, so this case is still caught."""
    news_item = {**synthetic_news_items(1)[0], "headline": "Analysts say consider buying more"}
    respx.get(_NEWS_URL, params={"symbol": "AAPL"}).mock(
        return_value=httpx.Response(200, json=[news_item])
    )
    respx.get(_RATIOS_URL, params={"symbol": "AAPL"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(_KEY_METRICS_URL, params={"symbol": "AAPL"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    anthropic_client = _fake_anthropic_client(
        "Recent news: analysts say consider buying more shares."
    )

    async with db_session_factory() as session:
        service = await _build_claude_service(session, anthropic_client=anthropic_client)
        response = await service.chat("Any news on AAPL?", ContextRefs(symbols=["AAPL"]))

    assert response.answer == _SAFE_FALLBACK_MESSAGE


def test_lexical_filter_documented_gap_semantic_but_not_lexical_phrasing() -> None:
    """Documents the accepted MVP limitation (Key Technical Decisions): a
    lexical guard cannot catch semantically prescriptive phrasing that uses
    none of the known directive phrases. This is an accepted gap, not a bug
    this test expects fixed here."""
    assert not contains_directive_language(
        "This looks like an attractive entry point given the current valuation."
    )


# --- Claude API failures never produce a partial/garbled response ----------


async def test_claude_api_failure_raises_advisor_unavailable(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    api_error = APIError(
        "boom", request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"), body=None
    )
    anthropic_client = _fake_anthropic_client(error=api_error)

    async with db_session_factory() as session:
        service = await _build_claude_service(session, anthropic_client=anthropic_client)
        with pytest.raises(AdvisorUnavailableError):
            await service.chat("How is my AAPL position doing?", ContextRefs(symbols=["AAPL"]))


# --- Parity with U2's own domain functions ----------------------------------


async def test_portfolio_context_flags_concentrated_holdings_via_u2_directly(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A single 100%-allocated holding must be flagged as concentrated --
    proves `flag_concentrated` (U2) is actually invoked, not just referenced."""
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session,
            anthropic_client=anthropic_client,
            positions=[synthetic_stock_position(symbol="AAPL")],
        )
        await service.chat("Tell me about my holdings.", ContextRefs())

    prompt_text = anthropic_client.messages.create.await_args.kwargs["messages"][0]["content"][-1][
        "text"
    ]
    assert "AAPL" in prompt_text
    assert "over 20% of portfolio" in prompt_text
