"""Claude advisor service: grounded, cited, never-directive.

This is the highest-risk module in the codebase, both legally and in
terms of user trust (CLAUDE.md hard rules 1 and 2). Two independent
layers enforce the no-directive-advice boundary, per the plan's Key
Technical Decisions:

1. The system prompt (`_SYSTEM_PROMPT`) explicitly forbids directive
   language, instructs context-only grounding, instructs citing sources,
   and instructs reframing "what should I do" questions.
2. `contains_directive_language()` scans the model's *response* for a
   documented list of forbidden phrases before it ever reaches the
   client; on a match, a safe fallback message is substituted instead.

Layer 2 is a lexical guard, not a semantic one: it catches "you should
sell" but not semantically prescriptive, lexically-clean phrasing like
"this looks like an attractive entry point." That gap is an accepted,
documented MVP limitation (see `backend/README.md`), not something this
module claims to fully close -- escalate to a second-pass semantic check
(e.g. an extra classifier call) if real model outputs exhibit it.

Every claim the model makes must be grounded in data this service
explicitly assembled and passed in as context (CLAUDE.md hard rule 2) --
never the model's own training-data knowledge of a company. Filing
summarization specifically uses the Anthropic Citations API (a
`document` content block with `citations: {"enabled": true}`) so
filing-derived claims are structurally tied to exact source passages,
not just prompted to be.
"""

import datetime as dt
import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from anthropic import APIError, AsyncAnthropic
from anthropic.types import DocumentBlockParam, TextBlockParam

from app.domain.allocation import Allocation
from app.domain.concentration import flag_concentrated
from app.schemas.advisor import ChatResponse, Citation, ContextRefs
from app.services.edgar_service import EdgarService
from app.services.errors import (
    AdvisorUnavailableError,
    InsufficientContextError,
    ProviderNotFoundError,
    ProviderUnavailableError,
)
from app.services.finnhub_service import FinnhubService
from app.services.fmp_service import FmpService
from app.services.snaptrade_service import SnapTradeService

logger = logging.getLogger(__name__)

# A holding above this share of the portfolio is called out as
# concentrated in the advisor's context -- matches the >20% example
# threshold used in U2's own concentration tests.
_CONCENTRATION_THRESHOLD_PCT = Decimal(20)

# How many of the most recent news items to include per symbol -- keeps
# the context block (and therefore the request) bounded regardless of
# how much news a symbol has.
_MAX_NEWS_ITEMS_PER_SYMBOL = 5

_MAX_TOKENS = 1024

# CLAUDE.md's four required elements, near-verbatim: (1) forbid directive
# language, (2) context-only grounding -- say so when something isn't
# covered rather than inferring it, (3) cite the specific context item
# (and quote the line, for filing-derived claims) behind every claim,
# (4) reframe "what should I do" questions instead of refusing or
# complying with them.
_SYSTEM_PROMPT = """\
You are Rundown's portfolio data advisor. You explain what a user's own \
data shows. You do not give financial advice. Follow these rules without \
exception:

1. Never give directive or prescriptive investment advice. Do not say \
"you should buy," "you should sell," "I recommend," "consider adding," \
"now is a good time to," or any variation that tells the user what \
action to take with their money or portfolio. This is a hard legal \
boundary (the Investment Advisers Act), not a tone preference.

2. Ground every claim only in the data provided to you in this \
conversation's context. Never draw on general knowledge about a \
company, market, or security that isn't present in the provided \
context, even if you know it. If the user asks about something the \
provided context doesn't cover, say so explicitly instead of inferring \
or guessing.

3. For every factual claim, say which specific context item it comes \
from (a holding, a fundamentals ratio, a filing passage, a news item). \
For claims drawn from filing text, quote the specific line or sentence.

4. If the user asks "what should I do," "should I buy/sell," or \
anything else asking you to recommend an action, do not refuse to \
answer and do not comply with the request as asked. Reframe it: respond \
with what is relevant in their data to that question (e.g. "Here's \
what's relevant to that position: ...") without ever stating or \
implying a recommended action.
"""

# Lexical guard (Key Technical Decisions): catches known directive
# phrasing in the model's *response*, as defense-in-depth alongside the
# system prompt above. Deliberately phrase-based rather than single
# verbs like "buy"/"sell" alone, which would false-positive on ordinary
# financial vocabulary ("sell-side", "buyback", "sold shares last year").
_DIRECTIVE_PHRASE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\byou should (buy|sell|hold|add|trim|reduce|increase|exit|rebalance)\b",
        r"\byou (might|may|could) want to (buy|sell)\b",
        r"\byou (need|ought|have) to (buy|sell)\b",
        r"\bi(?:'d| would)? (recommend|suggest|advise)\b",
        r"\bmy (recommendation|advice|suggestion) (is|would be)\b",
        r"\bconsider (buying|selling|adding to|trimming|reducing|increasing)\b",
        r"\b(now|this) (is|would be|seems like) a good time to (buy|sell)\b",
        r"\b(buy|sell) (more|now|this|your)\b",
    )
)

_SAFE_FALLBACK_MESSAGE = (
    "I can't share that response as phrased -- it read as a directive recommendation "
    "rather than an explanation of your data. Rundown's advisor explains what your data "
    "shows; it doesn't tell you what to do with a position. Try rephrasing your question "
    "to ask about a specific holding, ratio, filing, or news item."
)


def contains_directive_language(text: str) -> bool:
    """`True` if `text` matches a known directive-advice phrase.

    A lexical check, not a semantic one -- see this module's docstring
    for the documented gap that leaves open.
    """
    return any(pattern.search(text) for pattern in _DIRECTIVE_PHRASE_PATTERNS)


@dataclass(frozen=True, slots=True)
class ContextItem:
    """One piece of grounding data assembled into the model's context, with provenance."""

    source: str
    as_of: dt.datetime
    text: str


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class ClaudeService:
    """Assembles grounded context, calls Claude, and filters the response.

    Depends on every other provider service (SnapTrade, FMP, EDGAR,
    Finnhub) directly rather than re-fetching their data independently --
    the advisor must never disagree with the dashboard about a holding's
    allocation or P&L (System-Wide Impact invariant), which only holds if
    it reuses the exact same U2 domain functions and provider services,
    not parallel copies of them.
    """

    def __init__(
        self,
        client: AsyncAnthropic,
        model_id: str,
        snaptrade_service: SnapTradeService,
        fmp_service: FmpService,
        edgar_service: EdgarService,
        finnhub_service: FinnhubService,
    ) -> None:
        self._client = client
        self._model_id = model_id
        self._snaptrade_service = snaptrade_service
        self._fmp_service = fmp_service
        self._edgar_service = edgar_service
        self._finnhub_service = finnhub_service

    async def chat(self, question: str, context_refs: ContextRefs) -> ChatResponse:
        """Answer `question`, grounded only in the data `context_refs` names.

        Raises:
            InsufficientContextError: no context is available at all (no
                symbols, no connected portfolio, and no filing reference,
                or the referenced filing doesn't exist).
            AdvisorUnavailableError: the Claude API call itself failed or
                timed out.
        """
        document_block, filing_source_label = await self._build_filing_document(context_refs)

        context_items: list[ContextItem] = []
        portfolio_item = await self._build_portfolio_context(context_refs.symbols or None)
        if portfolio_item is not None:
            context_items.append(portfolio_item)
        if context_refs.symbols:
            context_items.extend(await self._build_fundamentals_context(context_refs.symbols))
            news_item = await self._build_news_context(context_refs.symbols)
            if news_item is not None:
                context_items.append(news_item)

        if not context_items and document_block is None:
            raise InsufficientContextError(
                "No context is available for this question -- connect a brokerage "
                "account, specify symbols, or reference a specific filing."
            )

        user_content = _build_user_content(context_items, document_block, question)

        try:
            response = await self._client.messages.create(
                model=self._model_id,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
        except APIError as exc:
            raise AdvisorUnavailableError(exc) from exc

        answer, citations = _extract_answer_and_citations(response, filing_source_label)

        if contains_directive_language(answer):
            logger.warning(
                "Advisor response filtered: matched a forbidden directive-language pattern."
            )
            return ChatResponse(answer=_SAFE_FALLBACK_MESSAGE, citations=[])

        return ChatResponse(answer=answer, citations=citations)

    async def _build_filing_document(
        self, context_refs: ContextRefs
    ) -> tuple[DocumentBlockParam | None, str | None]:
        if context_refs.filing_ref is None:
            return None, None

        try:
            result = await self._edgar_service.get_filing_text(
                context_refs.filing_ref.symbol, context_refs.filing_ref.accession_number
            )
        except ProviderNotFoundError as exc:
            raise InsufficientContextError(
                f"No filing text is available for {context_refs.filing_ref.symbol} "
                f"accession {context_refs.filing_ref.accession_number}."
            ) from exc
        except ProviderUnavailableError as exc:
            raise AdvisorUnavailableError(exc) from exc

        filing = result.value
        symbol = context_refs.filing_ref.symbol
        document: DocumentBlockParam = {
            "type": "document",
            "source": {"type": "text", "media_type": "text/plain", "data": filing.text},
            "title": f"{symbol} {filing.form} filing ({filing.accession_number})",
            "citations": {"enabled": True},
        }
        source_label = f"SEC EDGAR filing ({symbol} {filing.form})"
        return document, source_label

    async def _build_portfolio_context(self, symbols: list[str] | None) -> ContextItem | None:
        """Current holdings, with allocation/concentration/P&L already computed by U2.

        `SnapTradeService.list_positions` already calls U2's
        `compute_allocation`/`compute_pnl` internally, so those numbers
        can never drift from what `/portfolio/positions` itself shows.
        `flag_concentrated` is called directly here, since concentration
        flagging isn't part of `PositionView` -- this is the one U2
        function the advisor's context assembly invokes on its own.
        """
        try:
            result = await self._snaptrade_service.list_positions()
        except ProviderUnavailableError:
            return None

        views = result.value
        if symbols:
            wanted = {symbol.upper() for symbol in symbols}
            views = [view for view in views if view.symbol.upper() in wanted]
        if not views:
            return None

        allocations = [
            Allocation(symbol=view.symbol, percent=view.allocation_pct) for view in views
        ]
        concentrated_symbols = {
            a.symbol for a in flag_concentrated(allocations, _CONCENTRATION_THRESHOLD_PCT)
        }

        lines = ["Current holdings:"]
        for view in views:
            pnl_pct = (
                f"{view.unrealized_pnl_percent:.1f}%"
                if view.unrealized_pnl_percent is not None
                else "n/a"
            )
            flag = " [over 20% of portfolio]" if view.symbol in concentrated_symbols else ""
            pnl_dollars = view.unrealized_pnl_dollars
            lines.append(
                f"- {view.symbol}: {view.quantity} shares, market value ${view.market_value}, "
                f"{view.allocation_pct:.1f}% of portfolio, unrealized P&L ${pnl_dollars} "
                f"({pnl_pct}){flag}"
            )

        return ContextItem(source="SnapTrade positions", as_of=result.as_of, text="\n".join(lines))

    async def _build_fundamentals_context(self, symbols: list[str]) -> list[ContextItem]:
        items: list[ContextItem] = []
        for symbol in symbols:
            try:
                result = await self._fmp_service.get_fundamentals(symbol)
            except (ProviderUnavailableError, ProviderNotFoundError):
                continue

            fields = result.value.model_dump(exclude={"symbol"}, exclude_none=True)
            if not fields:
                continue
            lines = [f"Fundamentals for {result.value.symbol}:"]
            lines.extend(f"- {name}: {value}" for name, value in fields.items())
            items.append(
                ContextItem(
                    source=f"FMP fundamentals ({result.value.symbol})",
                    as_of=result.as_of,
                    text="\n".join(lines),
                )
            )
        return items

    async def _build_news_context(self, symbols: list[str]) -> ContextItem | None:
        try:
            result = await self._finnhub_service.get_news_for_symbols(symbols)
        except ProviderUnavailableError:
            return None
        if not result.value:
            return None

        by_symbol: dict[str, int] = {}
        lines = ["Recent news:"]
        for item in result.value:
            if by_symbol.get(item.symbol, 0) >= _MAX_NEWS_ITEMS_PER_SYMBOL:
                continue
            by_symbol[item.symbol] = by_symbol.get(item.symbol, 0) + 1
            lines.append(
                f"- [{item.symbol}] {item.published_at.date().isoformat()} "
                f"({item.publisher}): {item.headline} -- {item.summary}"
            )

        return ContextItem(source="Finnhub news", as_of=result.as_of, text="\n".join(lines))


def _build_user_content(
    context_items: list[ContextItem],
    document_block: DocumentBlockParam | None,
    question: str,
) -> list[DocumentBlockParam | TextBlockParam]:
    content: list[DocumentBlockParam | TextBlockParam] = []
    if document_block is not None:
        content.append(document_block)

    context_text = "\n\n".join(item.text for item in context_items)
    prompt_text = (
        f"{context_text}\n\nQuestion: {question}" if context_text else f"Question: {question}"
    )
    content.append({"type": "text", "text": prompt_text})
    return content


def _extract_answer_and_citations(
    response: Any,  # noqa: ANN401 -- anthropic.types.Message; kept loose since only `.content` is used
    filing_source_label: str | None,
) -> tuple[str, list[Citation]]:
    """Pull the answer text and any Citations-API citations out of `response`.

    Anthropic's Citations API response shape (`TextBlock.citations`, each
    a `CitationCharLocation`-like object with a `cited_text` field) was
    verified by introspecting the installed `anthropic==0.120.2` SDK's
    type definitions directly -- no live API key is available in this
    environment to verify against a real response.
    """
    answer_parts: list[str] = []
    citations: list[Citation] = []
    now = _utcnow()

    for block in response.content:
        if getattr(block, "type", None) != "text":
            continue
        answer_parts.append(block.text)
        for citation in getattr(block, "citations", None) or []:
            cited_text = getattr(citation, "cited_text", None)
            if cited_text:
                citations.append(
                    Citation(
                        source=filing_source_label or "Claude citation",
                        quote=cited_text,
                        as_of=now,
                    )
                )

    return "".join(answer_parts), citations
