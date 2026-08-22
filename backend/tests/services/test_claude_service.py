"""Tests for `app.services.claude_service.ClaudeService`.

The Anthropic client is a plain `SimpleNamespace`/`AsyncMock` matching
only the `.messages.create()` surface `ClaudeService` actually calls --
no live API key is used or required. This is the highest-risk module in
the codebase (CLAUDE.md hard rules 1 and 2), so this suite is organized
around the plan's explicit test scenarios for U8, not just line coverage.
"""

import datetime as dt
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import respx
from anthropic import APIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cache.cache_repository import CacheRepository
from app.schemas.advisor import ContextRefs, FilingRef
from app.schemas.xbrl import XbrlFact, XbrlFacts
from app.services.claude_service import (
    _MAX_FILING_CHARS,
    _SAFE_FALLBACK_MESSAGE,
    ClaudeService,
    contains_directive_language,
)
from app.services.edgar_service import EdgarService
from app.services.errors import (
    AdvisorUnavailableError,
    InsufficientContextError,
    ProviderFetchError,
)
from app.services.finnhub_service import FinnhubService
from app.services.fmp_service import FmpService
from app.services.snaptrade_service import SnapTradeService
from app.services.xbrl_service import XbrlService
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
from tests.fixtures.synthetic_xbrl import synthetic_company_facts

_RATIOS_URL = "https://financialmodelingprep.com/stable/ratios"
_KEY_METRICS_URL = "https://financialmodelingprep.com/stable/key-metrics-ttm"
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK0000320193.json"
_FILING_TEXT_URL = (
    "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/synthetic-10k.htm"
)
_NEWS_URL = "https://finnhub.io/api/v1/company-news"
_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"


def _mock_symbol_providers() -> None:
    """Mock every host a symbol-scoped chat reaches out to.

    Needed even by tests that assert nothing about fundamentals, news, or
    facts: without respx active those calls escape to the real network and
    only pass because the advisor tolerates provider failures, which is
    exactly the live-API dependency CLAUDE.md's testing rules forbid.

    `AAPL` is deliberately absent from `SYNTHETIC_TICKER_MAP`, so CIK
    resolution fails and no XBRL fetch follows -- these tests are about
    the advisor's boundaries, not its facts context.
    """
    respx.get(_RATIOS_URL).mock(return_value=httpx.Response(200, json=[{"symbol": "AAPL"}]))
    respx.get(_KEY_METRICS_URL).mock(return_value=httpx.Response(200, json=[{"symbol": "AAPL"}]))
    respx.get(_NEWS_URL).mock(return_value=httpx.Response(200, json=[]))
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))


def _mock_company_facts() -> None:
    respx.get(_COMPANY_FACTS_URL).mock(
        return_value=httpx.Response(200, json=synthetic_company_facts())
    )


async def _build_claude_service(
    session: AsyncSession,
    *,
    anthropic_client: SimpleNamespace,
    positions: list[dict[str, Any]] | None = None,
    connected: bool = True,
    positions_error: Exception | None = None,
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
        positions_error=positions_error,
    )
    snaptrade_service = SnapTradeService(client=snaptrade_client, cache=cache)
    # One EDGAR client shared by the filings and XBRL services, as the real
    # lifespan does -- SEC's XBRL API is the same host under the same
    # `User-Agent` requirement.
    edgar_client = httpx.AsyncClient(headers={"User-Agent": "Rundown Test (test@example.com)"})
    edgar_service = EdgarService(client=edgar_client, cache=cache)

    return ClaudeService(
        client=anthropic_client,  # type: ignore[arg-type]
        model_id="claude-sonnet-5",
        snaptrade_service=snaptrade_service,
        fmp_service=FmpService(
            client=httpx.AsyncClient(base_url="https://financialmodelingprep.com"), cache=cache
        ),
        edgar_service=edgar_service,
        finnhub_service=FinnhubService(
            client=httpx.AsyncClient(base_url="https://finnhub.io"), cache=cache
        ),
        xbrl_service=XbrlService(
            client=edgar_client,
            cache=cache,
            edgar_service=edgar_service,
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
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
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


# --- General questions: matching held symbols/names by text ----------------
# `ContextRefs()` (empty symbols, no filing_ref) is the shape the general
# "Ask about your portfolio" entry point always sends -- these scenarios
# are what closes the gap where that entry point never got fundamentals,
# news, or facts for anything (docs/plans/2026-08-20-001-fix-advisor-
# general-context-scoping-plan.md).


@respx.mock
async def test_general_question_naming_a_held_ticker_pulls_its_context(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    _mock_company_facts()
    respx.get(_RATIOS_URL, params={"symbol": "SYNT"}).mock(
        return_value=httpx.Response(200, json=[{"symbol": "SYNT", "priceToEarningsRatio": 25.5}])
    )
    respx.get(_KEY_METRICS_URL, params={"symbol": "SYNT"}).mock(
        return_value=httpx.Response(200, json=[{"symbol": "SYNT", "revenuePerShareTTM": 6.5}])
    )
    respx.get(_NEWS_URL, params={"symbol": "SYNT"}).mock(
        return_value=httpx.Response(200, json=synthetic_news_items(1))
    )
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session,
            anthropic_client=anthropic_client,
            positions=[synthetic_stock_position(symbol="SYNT")],
        )
        await service.chat("What's going on with SYNT?", ContextRefs())

    prompt_text = _prompt_text(anthropic_client)
    assert "Fundamentals for SYNT" in prompt_text
    assert "Recent news" in prompt_text


@respx.mock
async def test_general_question_naming_a_held_company_by_name_pulls_its_context(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """No ticker mentioned at all -- only the company's registered name
    (resolved from SEC's ticker map, per `EdgarService.resolve_company_names`)."""
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    _mock_company_facts()
    respx.get(_RATIOS_URL, params={"symbol": "SYNT"}).mock(
        return_value=httpx.Response(200, json=[{"symbol": "SYNT", "priceToEarningsRatio": 25.5}])
    )
    respx.get(_KEY_METRICS_URL, params={"symbol": "SYNT"}).mock(
        return_value=httpx.Response(200, json=[{"symbol": "SYNT", "revenuePerShareTTM": 6.5}])
    )
    respx.get(_NEWS_URL, params={"symbol": "SYNT"}).mock(
        return_value=httpx.Response(200, json=synthetic_news_items(1))
    )
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session,
            anthropic_client=anthropic_client,
            positions=[synthetic_stock_position(symbol="SYNT")],
        )
        # "SYNT" is deliberately absent -- only its registered name,
        # "Synthetic Test Co" (SYNTHETIC_TICKER_MAP), appears.
        await service.chat("What's relevant to my Synthetic Test Co position?", ContextRefs())

    prompt_text = _prompt_text(anthropic_client)
    assert "Fundamentals for SYNT" in prompt_text
    assert "Recent news" in prompt_text


@respx.mock
async def test_general_question_naming_nothing_held_gets_holdings_only(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Today's behavior, preserved: a question that matches no held symbol
    or name gets the holdings list and nothing else."""
    _mock_symbol_providers()
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session,
            anthropic_client=anthropic_client,
            positions=[synthetic_stock_position(symbol="SYNT")],
        )
        await service.chat("How is my portfolio balanced?", ContextRefs())

    prompt_text = _prompt_text(anthropic_client)
    assert "Current holdings:" in prompt_text
    assert "Fundamentals for" not in prompt_text
    assert "Recent news" not in prompt_text


@respx.mock
async def test_matched_symbol_does_not_narrow_the_holdings_list(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    _mock_company_facts()
    respx.get(_RATIOS_URL, params={"symbol": "SYNT"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(_KEY_METRICS_URL, params={"symbol": "SYNT"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(_NEWS_URL, params={"symbol": "SYNT"}).mock(return_value=httpx.Response(200, json=[]))
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session,
            anthropic_client=anthropic_client,
            positions=[
                synthetic_stock_position(symbol="SYNT"),
                synthetic_stock_position(symbol="MSFT"),
            ],
        )
        await service.chat("What's going on with SYNT?", ContextRefs())

    prompt_text = _prompt_text(anthropic_client)
    # Both holdings still show, even though only SYNT was matched/mentioned.
    assert "SYNT" in prompt_text
    assert "MSFT" in prompt_text


@respx.mock
async def test_explicit_scope_wins_over_a_different_mentioned_symbol(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Mirrors the "Ask about this position" flow: explicit `symbols` is
    never overridden by matching, even when the question names another
    held symbol."""
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    respx.get(_RATIOS_URL, params={"symbol": "AAPL"}).mock(
        return_value=httpx.Response(200, json=[{"symbol": "AAPL", "priceToEarningsRatio": 25.5}])
    )
    respx.get(_KEY_METRICS_URL, params={"symbol": "AAPL"}).mock(
        return_value=httpx.Response(200, json=[{"symbol": "AAPL", "revenuePerShareTTM": 6.5}])
    )
    respx.get(_NEWS_URL, params={"symbol": "AAPL"}).mock(
        return_value=httpx.Response(200, json=synthetic_news_items(1))
    )
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session,
            anthropic_client=anthropic_client,
            positions=[
                synthetic_stock_position(symbol="AAPL"),
                synthetic_stock_position(symbol="SYNT"),
            ],
        )
        await service.chat("How does AAPL compare to SYNT?", ContextRefs(symbols=["AAPL"]))

    prompt_text = _prompt_text(anthropic_client)
    assert "Fundamentals for AAPL" in prompt_text
    # SYNT was mentioned in the question but never explicitly scoped --
    # matching must not add it just because it's also held.
    assert "Fundamentals for SYNT" not in prompt_text


@respx.mock
async def test_filing_reference_with_no_symbols_never_triggers_matching(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Regression coverage: the original `effective_symbols` formula only
    short-circuited on `symbols`, not `filing_ref`, so a filing-only call
    naming a held symbol in its question text could still pull in
    fundamentals/news -- a flow this plan promises to leave untouched."""
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    _mock_company_facts()
    respx.get(_SUBMISSIONS_URL).mock(return_value=httpx.Response(200, json=synthetic_submissions()))
    respx.get(_FILING_TEXT_URL).mock(return_value=httpx.Response(200, text=synthetic_10k_html()))
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session,
            anthropic_client=anthropic_client,
            positions=[synthetic_stock_position(symbol="SYNT")],
        )
        await service.chat(
            "What does this filing say about SYNT's revenue?",
            ContextRefs(
                filing_ref=FilingRef(symbol="SYNT", accession_number="0000320193-24-000123")
            ),
        )

    prompt_text = _prompt_text(anthropic_client)
    assert "SEC XBRL structured facts for SYNT" in prompt_text
    assert "Fundamentals for SYNT" not in prompt_text
    assert "Recent news" not in prompt_text


@respx.mock
async def test_mixed_matched_and_non_held_company_does_not_leak_ungrounded_context(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A question naming one held (matched) symbol alongside a non-held
    company must not widen what gets sent beyond the matched symbol --
    the model is left to say the second company isn't covered, per the
    system prompt's existing grounding rule, not fed data for it."""
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    _mock_company_facts()
    respx.get(_RATIOS_URL, params={"symbol": "SYNT"}).mock(
        return_value=httpx.Response(200, json=[{"symbol": "SYNT", "priceToEarningsRatio": 25.5}])
    )
    respx.get(_KEY_METRICS_URL, params={"symbol": "SYNT"}).mock(
        return_value=httpx.Response(200, json=[{"symbol": "SYNT", "revenuePerShareTTM": 6.5}])
    )
    respx.get(_NEWS_URL, params={"symbol": "SYNT"}).mock(
        return_value=httpx.Response(200, json=synthetic_news_items(1))
    )
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session,
            anthropic_client=anthropic_client,
            positions=[synthetic_stock_position(symbol="SYNT")],
        )
        # NVDA isn't held -- no context for it should appear anywhere.
        await service.chat("How does SYNT compare to NVDA?", ContextRefs())

    prompt_text = _prompt_text(anthropic_client)
    assert "Fundamentals for SYNT" in prompt_text
    # NVDA appears only in the echoed question text, never as its own
    # data block -- it isn't held, so nothing was fetched for it.
    assert "Fundamentals for NVDA" not in prompt_text
    assert "[NVDA]" not in prompt_text


@respx.mock
async def test_general_question_with_brokerage_unavailable_degrades_to_no_match(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The matching lookup itself must not crash on a real
    `ProviderUnavailableError` -- not `connected=False`, which only
    yields an empty-but-successful account list and never exercises this
    path. With nothing else in context, `chat()` still correctly raises
    the ordinary `InsufficientContextError` -- same as any other
    no-context case -- rather than an unhandled exception."""
    anthropic_client = _fake_anthropic_client("Here's what I have on hand.")

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session,
            anthropic_client=anthropic_client,
            positions_error=ProviderFetchError("SnapTrade is down"),
        )
        with pytest.raises(InsufficientContextError):
            await service.chat("What's going on with my portfolio?", ContextRefs())


@respx.mock
async def test_general_question_with_edgar_unavailable_degrades_to_ticker_only(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Regression coverage: matching's company-name lookup previously had
    no failure handling of its own, so an EDGAR outage (unlike a
    SnapTrade outage) would crash a general question instead of degrading
    -- a new failure mode, since a general question never touched EDGAR
    at all before this feature existed."""
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(503))
    respx.get(_RATIOS_URL, params={"symbol": "SYNT"}).mock(
        return_value=httpx.Response(200, json=[{"symbol": "SYNT", "priceToEarningsRatio": 25.5}])
    )
    respx.get(_KEY_METRICS_URL, params={"symbol": "SYNT"}).mock(
        return_value=httpx.Response(200, json=[{"symbol": "SYNT", "revenuePerShareTTM": 6.5}])
    )
    respx.get(_NEWS_URL, params={"symbol": "SYNT"}).mock(
        return_value=httpx.Response(200, json=synthetic_news_items(1))
    )
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session,
            anthropic_client=anthropic_client,
            positions=[synthetic_stock_position(symbol="SYNT")],
        )
        # No company name can be resolved with EDGAR down, but the ticker
        # itself still matches -- matching degrades to ticker-only, it
        # doesn't fail outright.
        await service.chat("What's going on with SYNT?", ContextRefs())

    prompt_text = _prompt_text(anthropic_client)
    assert "Fundamentals for SYNT" in prompt_text


# --- Filing summarization via the Citations API -----------------------------


@respx.mock
async def test_filing_summarization_returns_citations_from_the_source_filing(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    _mock_company_facts()
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
    _mock_company_facts()
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
    assert "fabricated interest expense" in data  # Item 7A, market risk
    assert "long and static" not in data  # Item 1, never extracted
    # Both extracted, both out of the default scope: Risk Factors because it
    # is the largest and lowest-signal Item, Item 8 because it exists to be
    # mined for referenced notes rather than sent whole.
    assert "single fabricated supplier" not in data  # Item 1A
    assert "Segment Information" not in data  # Item 8
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
@respx.mock
async def test_directive_questions_are_sent_with_the_no_directive_system_prompt(
    db_session_factory: async_sessionmaker[AsyncSession], question: str
) -> None:
    _mock_symbol_providers()
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
@respx.mock
async def test_directive_model_response_is_replaced_with_the_safe_fallback(
    db_session_factory: async_sessionmaker[AsyncSession], directive_response: str
) -> None:
    _mock_symbol_providers()
    anthropic_client = _fake_anthropic_client(directive_response)

    async with db_session_factory() as session:
        service = await _build_claude_service(session, anthropic_client=anthropic_client)
        response = await service.chat("Should I sell NVDA?", ContextRefs(symbols=["AAPL"]))

    assert response.answer == _SAFE_FALLBACK_MESSAGE
    assert response.citations == []


@respx.mock
async def test_neutral_model_response_is_passed_through_unmodified(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _mock_symbol_providers()
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
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    anthropic_client = _fake_anthropic_client(
        "Recent news: analysts say consider buying more shares."
    )

    async with db_session_factory() as session:
        service = await _build_claude_service(session, anthropic_client=anthropic_client)
        response = await service.chat("Any news on AAPL?", ContextRefs(symbols=["AAPL"]))

    assert response.answer == _SAFE_FALLBACK_MESSAGE


# --- Structured XBRL facts as grounding ------------------------------------


def _prompt_text(anthropic_client: SimpleNamespace) -> str:
    content = anthropic_client.messages.create.await_args.kwargs["messages"][0]["content"]
    return str(content[-1]["text"])


def _document_block(anthropic_client: SimpleNamespace) -> dict[str, Any]:
    content = anthropic_client.messages.create.await_args.kwargs["messages"][0]["content"]
    return next(block for block in content if block["type"] == "document")


@respx.mock
async def test_facts_reach_the_advisor_with_accession_provenance(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The definition of done for this work: numbers in context, each
    traceable to the filing that reported it."""
    _mock_symbol_providers()
    _mock_company_facts()
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(session, anthropic_client=anthropic_client)
        await service.chat("How has revenue trended?", ContextRefs(symbols=["SYNT"]))

    prompt = _prompt_text(anthropic_client)
    assert "SEC XBRL structured facts for SYNT" in prompt
    assert "Revenue (USD):" in prompt
    assert "accession 0000000000-25-000001" in prompt


@respx.mock
async def test_facts_context_reports_which_line_items_were_unavailable(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Hard rule 2: without this the model reports that the company never
    disclosed a figure, when only this allowlist came back empty."""
    _mock_symbol_providers()
    _mock_company_facts()
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(session, anthropic_client=anthropic_client)
        await service.chat("What was R&D spend?", ContextRefs(symbols=["SYNT"]))

    prompt = _prompt_text(anthropic_client)
    assert "No values were available in SEC's structured data" in prompt
    assert "R&D expense" in prompt
    assert "not as figures the company failed to report" in prompt


@respx.mock
async def test_a_referenced_filing_pulls_in_its_own_symbols_facts(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Asking about a 10-K is asking about that company, even when the
    caller listed no symbols."""
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    _mock_company_facts()
    respx.get(_SUBMISSIONS_URL).mock(return_value=httpx.Response(200, json=synthetic_submissions()))
    respx.get(_FILING_TEXT_URL).mock(return_value=httpx.Response(200, text=synthetic_10k_html()))
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(session, anthropic_client=anthropic_client)
        await service.chat(
            "What does this filing say about revenue?",
            ContextRefs(
                filing_ref=FilingRef(symbol="SYNT", accession_number="0000320193-24-000123")
            ),
        )

    prompt = _prompt_text(anthropic_client)
    assert "SEC XBRL structured facts for SYNT" in prompt
    # None of the synthetic facts came from the referenced accession, so
    # nothing should claim to have.
    assert "[reported by the filing in question]" not in prompt


def test_rendered_facts_mark_the_ones_the_referenced_filing_reported() -> None:
    """Selection is symbol-wide, so the model needs the marker to tell
    "this filing reported" from "the company has reported"."""
    from app.services.claude_service import _render_xbrl_facts

    def fact(accession: str, *, referenced: bool) -> XbrlFact:
        return XbrlFact(
            label="Revenue",
            concept="Revenues",
            taxonomy="us-gaap",
            value=Decimal("500"),
            unit="USD",
            period_start=dt.date(2024, 9, 29),
            period_end=dt.date(2025, 9, 27),
            fiscal_year=2025,
            fiscal_period="FY",
            form="10-K",
            accession_number=accession,
            filed=dt.date(2025, 10, 31),
            from_referenced_filing=referenced,
        )

    text = _render_xbrl_facts(
        XbrlFacts(
            symbol="SYNT",
            facts=[fact("acc-referenced", referenced=True), fact("acc-other", referenced=False)],
            missing_labels=[],
        ),
        dt.datetime(2026, 7, 31, tzinfo=dt.UTC),
    )

    referenced_line = next(line for line in text.splitlines() if "acc-referenced" in line)
    other_line = next(line for line in text.splitlines() if "acc-other" in line)
    assert "[reported by the filing in question]" in referenced_line
    assert "[reported by the filing in question]" not in other_line


@respx.mock
async def test_facts_are_skipped_when_the_symbol_has_none(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An all-absent snapshot is context that says nothing; it should not
    crowd out the narrative excerpt."""
    _mock_symbol_providers()
    respx.get(_COMPANY_FACTS_URL).mock(return_value=httpx.Response(200, json={"facts": {}}))
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session,
            anthropic_client=anthropic_client,
            positions=[synthetic_stock_position(symbol="SYNT")],
        )
        await service.chat("How has revenue trended?", ContextRefs(symbols=["SYNT"]))

    assert "SEC XBRL structured facts" not in _prompt_text(anthropic_client)


@respx.mock
async def test_an_xbrl_outage_does_not_take_down_the_advisor(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _mock_symbol_providers()
    respx.get(_COMPANY_FACTS_URL).mock(return_value=httpx.Response(503))
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(
            session,
            anthropic_client=anthropic_client,
            positions=[synthetic_stock_position(symbol="SYNT")],
        )
        response = await service.chat("How is SYNT doing?", ContextRefs(symbols=["SYNT"]))

    assert response.answer
    assert "SEC XBRL structured facts" not in _prompt_text(anthropic_client)


async def test_system_prompt_distinguishes_the_two_filing_grounding_modes() -> None:
    """Facts cite an accession number; prose cites a quoted line. The model
    has to be told which is which, or it paraphrases a verifiable figure
    into an approximation."""
    from app.services.claude_service import _SYSTEM_PROMPT

    assert "quote the specific line or sentence" in _SYSTEM_PROMPT
    assert "accession" in _SYSTEM_PROMPT
    assert "do not round, rescale, or restate it" in _SYSTEM_PROMPT


def test_system_prompt_instructs_synthesis_over_recitation() -> None:
    """R3-R5: the model already has trend and cross-source data in context
    on most questions -- the gap this closes is instructional, not a
    missing data source. Regression guard for the requirements doc at
    docs/brainstorms/advisor-synthesis-and-formatting-requirements.md."""
    from app.services.claude_service import _SYSTEM_PROMPT

    prompt = _SYSTEM_PROMPT.lower()
    assert "most notable or distinctive" in prompt  # R3: lead, don't recite in order
    assert "trend or change across those periods" in prompt  # R4: multi-period trends
    assert "connect them" in prompt  # R5: cross-source connections


def test_system_prompt_ties_synthesis_back_to_the_non_directive_rule() -> None:
    """R6: synthesis instructions must reinforce, not loosen, rule 1 --
    the prompt has to say so explicitly next to the new instructions, not
    just rely on rule 1 existing elsewhere in the text."""
    from app.services.claude_service import _SYSTEM_PROMPT

    assert "violate rule 1" in _SYSTEM_PROMPT
    assert "never characterize" in _SYSTEM_PROMPT.lower()


# --- Prompt caching ---------------------------------------------------------


@respx.mock
async def test_filing_document_block_is_prompt_cached(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A published filing is immutable and is the largest thing in the
    request, so it's re-sent byte-identical on every follow-up question."""
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    _mock_company_facts()
    respx.get(_SUBMISSIONS_URL).mock(return_value=httpx.Response(200, json=synthetic_submissions()))
    respx.get(_FILING_TEXT_URL).mock(return_value=httpx.Response(200, text=synthetic_10k_html()))
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(session, anthropic_client=anthropic_client)
        await service.chat(
            "Summarize this filing.",
            ContextRefs(
                filing_ref=FilingRef(symbol="SYNT", accession_number="0000320193-24-000123")
            ),
        )

    assert _document_block(anthropic_client)["cache_control"] == {"type": "ephemeral"}


@respx.mock
async def test_the_cache_breakpoint_precedes_every_volatile_block(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Caching is a prefix match, so the cached document has to sit ahead
    of the question and the assembled context or nothing is reusable."""
    respx.get(_TICKER_MAP_URL).mock(return_value=httpx.Response(200, json=SYNTHETIC_TICKER_MAP))
    _mock_company_facts()
    respx.get(_SUBMISSIONS_URL).mock(return_value=httpx.Response(200, json=synthetic_submissions()))
    respx.get(_FILING_TEXT_URL).mock(return_value=httpx.Response(200, text=synthetic_10k_html()))
    anthropic_client = _fake_anthropic_client()

    async with db_session_factory() as session:
        service = await _build_claude_service(session, anthropic_client=anthropic_client)
        await service.chat(
            "Summarize this filing.",
            ContextRefs(
                filing_ref=FilingRef(symbol="SYNT", accession_number="0000320193-24-000123")
            ),
        )

    content = anthropic_client.messages.create.await_args.kwargs["messages"][0]["content"]
    cached = [index for index, block in enumerate(content) if "cache_control" in block]
    assert cached == [0]
    assert content[-1]["type"] == "text"


def test_lexical_filter_documented_gap_semantic_but_not_lexical_phrasing() -> None:
    """Documents the accepted MVP limitation (Key Technical Decisions): a
    lexical guard cannot catch semantically prescriptive phrasing that uses
    none of the known directive phrases. This is an accepted gap, not a bug
    this test expects fixed here."""
    assert not contains_directive_language(
        "This looks like an attractive entry point given the current valuation."
    )


# --- Claude API failures never produce a partial/garbled response ----------


@respx.mock
async def test_claude_api_failure_raises_advisor_unavailable(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _mock_symbol_providers()
    api_error = APIError(
        "boom", request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"), body=None
    )
    anthropic_client = _fake_anthropic_client(error=api_error)

    async with db_session_factory() as session:
        service = await _build_claude_service(session, anthropic_client=anthropic_client)
        with pytest.raises(AdvisorUnavailableError):
            await service.chat("How is my AAPL position doing?", ContextRefs(symbols=["AAPL"]))


@respx.mock
async def test_empty_answer_text_raises_advisor_unavailable_instead_of_blank_response(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Regression coverage: a 200 from the SDK whose text content is empty
    (observed in practice -- Claude occasionally returns no usable text)
    previously passed straight through as `ChatResponse(answer="")`, which
    renders as a blank chat bubble instead of surfacing any error. That's
    the same never-partial/garbled-response guarantee this module already
    enforces for outright API failures, just for a different failure
    shape."""
    _mock_symbol_providers()
    anthropic_client = _fake_anthropic_client(text="")

    async with db_session_factory() as session:
        service = await _build_claude_service(session, anthropic_client=anthropic_client)
        with pytest.raises(AdvisorUnavailableError):
            await service.chat("How is my AAPL position doing?", ContextRefs(symbols=["AAPL"]))


# --- Parity with U2's own domain functions ----------------------------------


@respx.mock
async def test_portfolio_context_flags_concentrated_holdings_via_u2_directly(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _mock_symbol_providers()
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
