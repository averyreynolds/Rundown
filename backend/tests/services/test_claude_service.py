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
    _MAX_FILING_CHARS,
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
    synthetic_10k_html,
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
    # The advisor sends extracted plain text, never raw markup -- a filing
    # with no recognizable Item headings still comes through as text
    # rather than being dropped (`mode="unsegmented"`).
    assert "<html>" not in document_blocks[0]["source"]["data"]
    assert "Synthetic filing text for testing only." in document_blocks[0]["source"]["data"]


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


# --- Only portfolio-relevant filing sections reach Claude ------------------
# Regression coverage for two real bugs. First: a large 10-K's raw,
# unstripped inline-XBRL HTML pushed a single advisor request past the
# model's 1M-token prompt limit (400 invalid_request_error). Second, and
# subtler: the head-truncation that fixed it spent the whole character
# budget on the cover page and table of contents, cutting off before
# MD&A -- so the advisor stayed under the limit while being grounded in
# the least relevant part of the filing. See `app.domain.filing_sections`.


async def _document_block_for_filing(
    db_session_factory: async_sessionmaker[AsyncSession],
    filing_html: str,
    anthropic_client: SimpleNamespace,
) -> tuple[dict[str, Any], str]:
    """Run one filing through `chat` and return `(document_block, prompt_text)`."""
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    respx.get(_SUBMISSIONS_URL).mock(return_value=httpx.Response(200, json=synthetic_submissions()))
    respx.get(_FILING_TEXT_URL).mock(return_value=httpx.Response(200, text=filing_html))

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session, anthropic_client=anthropic_client, connected=False
        )
        await service.chat(
            "Summarize this filing.",
            ContextRefs(
                filing_ref=FilingRef(symbol="SYNT", accession_number="0000320193-24-000123")
            ),
        )

    sent_content = anthropic_client.messages.create.await_args.kwargs["messages"][0]["content"]
    document_block = next(block for block in sent_content if block.get("type") == "document")
    return document_block, sent_content[-1]["text"]


@respx.mock
async def test_only_portfolio_relevant_sections_are_sent(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    document_block, _ = await _document_block_for_filing(
        db_session_factory, synthetic_10k_html(), _fake_anthropic_client()
    )
    data = document_block["source"]["data"]

    assert "Revenue increased to $1,234 million" in data  # Item 7, MD&A
    assert "single fabricated supplier" in data  # Item 1A, Risk Factors
    assert "long and static" not in data  # Item 1, excluded
    assert "audited synthetic financial" not in data  # Item 8, excluded
    assert "XBRL-ONLY-FACT-DO-NOT-SURFACE" not in data  # hidden iXBRL fact
    assert "[section excerpt]" in document_block["title"]


@respx.mock
async def test_oversized_filing_keeps_mdna_and_stays_within_budget(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    oversized = synthetic_10k_html(mdna_body="Revenue grew. " * (_MAX_FILING_CHARS // 10))
    document_block, _ = await _document_block_for_filing(
        db_session_factory, oversized, _fake_anthropic_client("The filing shows revenue growth.")
    )
    data = document_block["source"]["data"]

    assert len(data) <= _MAX_FILING_CHARS
    assert "[truncated excerpt]" in document_block["title"]
    # The whole point: MD&A survives an over-budget filing.
    assert "Management's Discussion and Analysis" in data
    assert "Revenue grew." in data


@respx.mock
async def test_prompt_tells_the_model_which_sections_it_did_not_get(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Otherwise hard rule 2's "say so when the context doesn't cover it"
    makes the model report that the *filing* is silent on a topic when in
    fact only the *excerpt* is -- an authoritative-sounding wrong answer."""
    _, prompt_text = await _document_block_for_filing(
        db_session_factory, synthetic_10k_html(), _fake_anthropic_client()
    )

    assert "contains these sections only" in prompt_text
    assert "Item 7." in prompt_text
    assert "Item 1. Business" in prompt_text
    assert "outside this excerpt" in prompt_text


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
