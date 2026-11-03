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
   `chat()` checks the whole answer. The streaming path checks each sentence
   and everything released so far before releasing it, so nothing unchecked
   ever reaches the client, and a failure retracts what came before. A
   streamed answer that stops early is labeled as partial.

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
from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx
from anthropic import APIError, AsyncAnthropic
from anthropic.lib.streaming import AsyncMessageStream, AsyncMessageStreamManager
from anthropic.types import DocumentBlockParam, TextBlockParam

from app.domain.allocation import Allocation
from app.domain.concentration import flag_concentrated
from app.domain.filing_sections import build_filing_document
from app.domain.followups import suggested_follow_ups
from app.domain.map_hints import derive_map_hint
from app.domain.sentence_stream import SentenceSegmenter
from app.domain.symbol_matching import HeldSymbol, match_held_symbols
from app.schemas.advisor import (
    AdvisorStreamEvent,
    ChatResponse,
    Citation,
    ContextRefs,
    DoneEvent,
    FilingRef,
    IncompleteEvent,
    InterruptedEvent,
    ReadingEvent,
    RetractEvent,
    ScopeEvent,
    SentenceEvent,
    SourceReading,
)
from app.schemas.xbrl import XbrlFact, XbrlFacts
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
from app.services.xbrl_service import XbrlService

logger = logging.getLogger(__name__)

# A holding above this share of the portfolio is called out as
# concentrated in the advisor's context -- matches the >20% example
# threshold used in U2's own concentration tests.
_CONCENTRATION_THRESHOLD_PCT = Decimal(20)

# How many of the most recent news items to include per symbol -- keeps
# the context block (and therefore the request) bounded regardless of
# how much news a symbol has.
_MAX_NEWS_ITEMS_PER_SYMBOL = 5

# 1024 was routinely too tight for a multi-position, multi-period answer
# with citations -- real responses were observed cutting off mid-sentence
# (a dangling "**" from an unclosed bold span, a truncated dollar figure).
_MAX_TOKENS = 2048

# SEC's inline-XBRL filing HTML is mostly markup -- tags, inline styles,
# table structure, XBRL contextRefs -- routinely 5-10x the size of the
# actual filing text. Sending it to Claude raw, unstripped, is what
# pushed a single large 10-K's document block past the model's 1M-token
# prompt limit (the fetched EDGAR text itself is left untouched --
# `/filings/{symbol}/{accession}` still returns the raw text/HTML it
# always has -- this budget applies only to what the advisor sends).
#
# `app.domain.filing_sections` spends this budget on the sections that
# bear on a position (MD&A, market risk, legal, dividends/buybacks) in
# priority order, plus any financial-statement note those sections defer
# to. The previous head-truncation spent it on whatever came first in the
# document, which on a large 10-K meant the cover page and table of
# contents, cutting off before MD&A.
#
# Lowered from 300K now that Risk Factors is out of the default scope.
# Across 14 real filings it was the largest Item in the old allowlist and
# roughly 40% of the assembled excerpt, so the default payload is much
# smaller than the old ceiling assumed. This leaves headroom for a large
# MD&A plus resolved notes without leaving room for the excerpt to drift
# back to a size nobody chose.
_MAX_FILING_CHARS = 120_000

# Rules 1-4 are CLAUDE.md's four required elements, near-verbatim: (1)
# forbid directive language, (2) context-only grounding -- say so when
# something isn't covered rather than inferring it, (3) cite the specific
# context item (and quote the line, for filing-derived claims) behind
# every claim, (4) reframe "what should I do" questions instead of
# refusing or complying with them. Rules 5-6 instruct synthesis --
# prioritize and connect what's already in context rather than reciting
# it -- and formatting, without loosening 1-4: rule 5 explicitly
# reiterates the no-evaluative-language boundary from rule 1. Rule 7 keeps the
# portfolio shares the backend computed from being recomputed by the model, so
# the assistant can't disagree with the map.
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
from (a holding, a fundamentals ratio, a reported financial figure, a \
filing passage, a news item). Filing-derived data comes to you in two \
distinct forms and they are cited differently. For a claim drawn from \
filing text, quote the specific line or sentence. For a claim drawn from \
a reported financial figure, name the period it covers and the accession \
number of the filing that reported it, and state the figure as given -- \
do not round, rescale, or restate it, and never combine figures into a \
derived number the filings do not themselves report.

4. If the user asks "what should I do," "should I buy/sell," or \
anything else asking you to recommend an action, do not refuse to \
answer and do not comply with the request as asked. Reframe it: respond \
with what is relevant in their data to that question (e.g. "Here's \
what's relevant to that position: ...") without ever stating or \
implying a recommended action.

5. Prioritize and connect what you say instead of listing context items \
in the order they were assembled. Lead with whatever is most notable or \
distinctive in the provided data for this question -- a concentration \
flag, an outsized profit/loss swing, a figure that stands out relative \
to the other periods provided -- rather than working through every \
context item in sequence. When the provided context includes more than \
one period for the same reported figure, describe the trend or change \
across those periods rather than only stating the most recent one. When \
two or more context items (a holding, a filing passage, a fundamentals \
ratio, a news item) bear on the same topic, say so explicitly and \
connect them instead of presenting them as unrelated facts. Do all of \
this only by describing what the data shows -- never characterize a \
trend, connection, or standout figure as good, bad, risky, or a reason \
to act. That would violate rule 1.

6. Use markdown formatting -- bold for the figure or fact you lead with, \
short bullet lists when covering more than one point -- wherever it \
makes an answer easier to scan. Formatting is a presentation choice; it \
never substitutes for the citation and grounding rules above.

7. The holdings context gives portfolio totals and each position's share of \
portfolio value, total cost, and net unrealized gain, already computed. State \
those figures as given. Do not compute your own shares or percentages from \
them, and if a share isn't provided, say it isn't available.
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

_PORTFOLIO_SOURCE = "SnapTrade positions"
_NEWS_SOURCE = "Finnhub news"

_MARKDOWN_EMPHASIS = re.compile(r"[*_`]")

_SAFE_FALLBACK_MESSAGE = (
    "I can't share that response as phrased -- it read as a directive recommendation "
    "rather than an explanation of your data. Rundown's advisor explains what your data "
    "shows; it doesn't tell you what to do with a position. Try rephrasing your question "
    "to ask about a specific holding, ratio, filing, or news item."
)


def contains_directive_language(text: str) -> bool:
    """`True` if `text` matches a known directive-advice phrase.

    A lexical check, not a semantic one -- see this module's docstring
    for the documented gap that leaves open. Markdown markers and line breaks
    are removed first, so "you **should** sell" and a phrase split across two
    lines can't slip past a pattern looking for "you should sell".
    """
    plain = " ".join(_MARKDOWN_EMPHASIS.sub("", text).split())
    return any(pattern.search(plain) for pattern in _DIRECTIVE_PHRASE_PATTERNS)


@dataclass(frozen=True, slots=True)
class ContextItem:
    """One piece of grounding data assembled into the model's context, with provenance."""

    source: str
    as_of: dt.datetime
    text: str


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _reading(source: str, as_of: dt.datetime, is_stale: bool) -> SourceReading:
    return SourceReading(source=source, as_of=as_of, status="stale" if is_stale else "used")


def _unavailable(source: str) -> SourceReading:
    return SourceReading(source=source, as_of=None, status="unavailable")


@dataclass(frozen=True, slots=True)
class _FilingAttachment:
    """A filing excerpt prepared for the request, with its scope described."""

    document: DocumentBlockParam
    source_label: str
    provenance_note: str


@dataclass(frozen=True, slots=True)
class _AssembledContext:
    """Everything an answer is grounded in, shared by both advisor endpoints."""

    user_content: list[DocumentBlockParam | TextBlockParam]
    readings: list[SourceReading]
    scope_symbols: list[str]
    filing_source_label: str | None


class AnswerStream:
    """An open Claude stream, turned into checked sentences by `events()`.

    Already connected when created, so a Claude failure to connect surfaces as an
    error before any response starts. `events()` owns the connection from there and
    releases it however it ends, including when a client disconnect cancels it.
    """

    def __init__(
        self,
        manager: AsyncMessageStreamManager[Any],
        stream: AsyncMessageStream[Any],
        context: _AssembledContext,
        held: list[HeldSymbol],
    ) -> None:
        self._manager = manager
        self._stream = stream
        self._context = context
        self._held = held

    async def events(self) -> AsyncIterator[AdvisorStreamEvent]:
        try:
            async for event in self._answer_events():
                yield event
        finally:
            await self._manager.__aexit__(None, None, None)

    async def _answer_events(self) -> AsyncIterator[AdvisorStreamEvent]:
        yield ScopeEvent(symbols=self._context.scope_symbols)
        for reading in self._context.readings:
            yield ReadingEvent(**reading.model_dump())

        sentences = _SentenceReleaser(self._held)
        citations: list[Citation] = []
        segmenter = SentenceSegmenter()

        try:
            async for event in self._stream:
                if event.type == "citation":
                    citation = _to_citation(event.citation, self._context.filing_source_label)
                    if citation is not None:
                        citations.append(citation)
                elif event.type == "text":
                    for sentence in segmenter.feed(event.text):
                        released = sentences.release(sentence, citations)
                        yield released
                        if isinstance(released, RetractEvent):
                            return
                        citations = []
            final_message = await self._stream.get_final_message()
        except (APIError, httpx.HTTPError):
            logger.warning("Advisor stream failed mid-answer.", exc_info=True)
            yield InterruptedEvent(reason="unavailable", citations=citations)
            return

        if final_message.stop_reason == "refusal":
            logger.warning("Advisor stream ended with a model refusal.")
            yield InterruptedEvent(reason="declined", citations=citations)
            return

        for sentence in segmenter.flush():
            released = sentences.release(sentence, citations)
            yield released
            if isinstance(released, RetractEvent):
                return
            citations = []

        if not sentences.any_released:
            # The streaming form of `chat()`'s empty-completion case.
            yield InterruptedEvent(reason="unavailable", citations=citations)
            return

        sources = [r for r in self._context.readings if r.status != "unavailable"]
        if final_message.stop_reason == "max_tokens":
            yield IncompleteEvent(sources=sources, citations=citations)
            return
        yield DoneEvent(
            sources=sources,
            citations=citations,
            follow_ups=suggested_follow_ups(sentences.focus, [h.symbol for h in self._held]),
        )


class _SentenceReleaser:
    """Checks each sentence against the guard and works out what the map should show."""

    def __init__(self, held: list[HeldSymbol]) -> None:
        self._held = held
        self._released: list[str] = []
        self.focus: tuple[str, ...] = ()

    @property
    def any_released(self) -> bool:
        return bool(self._released)

    def release(self, sentence: str, citations: list[Citation]) -> SentenceEvent | RetractEvent:
        # The accumulated check catches directive phrasing split across two sentences.
        if contains_directive_language(" ".join([*self._released, sentence])):
            logger.warning(
                "Advisor response filtered: matched a forbidden directive-language pattern."
            )
            return RetractEvent(message=_SAFE_FALLBACK_MESSAGE)

        hint = derive_map_hint(sentence, self._held, self.focus)
        self.focus = hint.focus
        self._released.append(sentence)
        return SentenceEvent(
            text=sentence, focus=list(hint.focus), sizing=hint.sizing, citations=citations
        )


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
        xbrl_service: XbrlService,
    ) -> None:
        self._client = client
        self._model_id = model_id
        self._snaptrade_service = snaptrade_service
        self._fmp_service = fmp_service
        self._edgar_service = edgar_service
        self._finnhub_service = finnhub_service
        self._xbrl_service = xbrl_service

    async def chat(self, question: str, context_refs: ContextRefs) -> ChatResponse:
        """Answer `question`, grounded only in the data `context_refs` names.

        When the caller supplies neither `symbols` nor `filing_ref` --
        the shape the general "Ask about your portfolio" entry point
        always sends -- `question`'s text is matched against the
        connected portfolio's held tickers and company names
        (`_match_symbols_in_question`) to find `effective_symbols`, so a
        general question can still pull fundamentals/news/facts for a
        position it clearly names. Explicit `symbols` always wins, and a
        filing reference always suppresses matching entirely, regardless
        of question wording -- filing summarization is unaffected by this.

        Raises:
            InsufficientContextError: no context is available at all (no
                symbols, no connected portfolio, and no filing reference,
                or the referenced filing doesn't exist).
            AdvisorUnavailableError: the Claude API call itself failed or
                timed out.
        """
        context = await self._assemble_context(question, context_refs)

        try:
            response = await self._client.messages.create(
                model=self._model_id,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": context.user_content}],
            )
        except APIError as exc:
            raise AdvisorUnavailableError(exc) from exc

        answer, citations = _extract_answer_and_citations(response, context.filing_source_label)

        if not answer.strip():
            # Observed in practice: Claude occasionally returns a response
            # with no usable text content (e.g. an empty completion) even
            # on a 200 from the SDK, so `APIError` alone doesn't catch it.
            # Silently returning "" would render as a blank chat bubble --
            # indistinguishable from a broken UI -- rather than the never-
            # partial/garbled-response guarantee this module documents for
            # every other Claude-side failure.
            raise AdvisorUnavailableError(
                RuntimeError("Claude returned no text content for this question.")
            )

        if contains_directive_language(answer):
            logger.warning(
                "Advisor response filtered: matched a forbidden directive-language pattern."
            )
            return ChatResponse(answer=_SAFE_FALLBACK_MESSAGE, citations=[])

        return ChatResponse(answer=answer, citations=citations)

    async def open_answer_stream(self, question: str, context_refs: ContextRefs) -> AnswerStream:
        """Connect to Claude for `question`, grounded the same way as `chat()`.

        Raises:
            InsufficientContextError: no context is available at all.
            AdvisorUnavailableError: Claude couldn't be reached.
        """
        context = await self._assemble_context(question, context_refs)
        held = await self._load_held()
        scope_symbols = context.scope_symbols or [entry.symbol for entry in held]

        manager = self._client.messages.stream(
            model=self._model_id,
            max_tokens=_MAX_TOKENS,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context.user_content}],
        )
        try:
            stream = await manager.__aenter__()
        except APIError as exc:
            raise AdvisorUnavailableError(exc) from exc

        return AnswerStream(
            manager,
            stream,
            _AssembledContext(
                user_content=context.user_content,
                readings=context.readings,
                scope_symbols=scope_symbols,
                filing_source_label=context.filing_source_label,
            ),
            held,
        )

    async def _assemble_context(
        self, question: str, context_refs: ContextRefs
    ) -> _AssembledContext:
        """Gather what an answer may draw on, recording each source that was read.

        The one assembly path for both endpoints, so what they're grounded in
        can't drift. See `chat()` for how `effective_symbols` is chosen.

        Raises:
            InsufficientContextError: no context is available at all.
            AdvisorUnavailableError: the referenced filing couldn't be fetched.
        """
        readings: list[SourceReading] = []
        attachment = await self._build_filing_attachment(context_refs)
        if attachment is not None:
            readings.append(
                SourceReading(source=attachment.source_label, as_of=_utcnow(), status="used")
            )

        effective_symbols = context_refs.symbols
        if not effective_symbols and context_refs.filing_ref is None:
            effective_symbols = await self._match_symbols_in_question(question)

        context_items: list[ContextItem] = []
        portfolio_item = await self._build_portfolio_context(context_refs.symbols or None, readings)
        if portfolio_item is not None:
            context_items.append(portfolio_item)
        # Ahead of fundamentals and news deliberately: these are figures
        # the company itself reported, each traceable to the filing that
        # reported it, so they are the most authoritative numbers in the
        # context and should be what the model reaches for first.
        context_items.extend(
            await self._build_facts_context(effective_symbols, context_refs.filing_ref, readings)
        )
        if effective_symbols:
            context_items.extend(
                await self._build_fundamentals_context(effective_symbols, readings)
            )
            news_item = await self._build_news_context(effective_symbols, readings)
            if news_item is not None:
                context_items.append(news_item)

        if not context_items and attachment is None:
            raise InsufficientContextError(
                "No context is available for this question -- connect a brokerage "
                "account, specify symbols, or reference a specific filing."
            )

        scope_symbols = list(effective_symbols)
        if context_refs.filing_ref is not None and not scope_symbols:
            scope_symbols = [context_refs.filing_ref.symbol]

        return _AssembledContext(
            user_content=_build_user_content(context_items, attachment, question),
            readings=readings,
            scope_symbols=scope_symbols,
            filing_source_label=attachment.source_label if attachment is not None else None,
        )

    async def _build_filing_attachment(self, context_refs: ContextRefs) -> _FilingAttachment | None:
        """Attach the portfolio-relevant sections of the referenced filing.

        The document block carries only the extracted sections, verbatim,
        so the Citations API's `cited_text` still maps to real filing
        prose. What was left out travels alongside it as
        `provenance_note` -- without that, hard rule 2's "say so when the
        context doesn't cover it" makes the model report that the
        *filing* is silent on a topic when only the *excerpt* is.
        """
        if context_refs.filing_ref is None:
            return None

        try:
            result = await self._edgar_service.get_filing_sections(
                context_refs.filing_ref.symbol, context_refs.filing_ref.accession_number
            )
        except ProviderNotFoundError as exc:
            raise InsufficientContextError(
                f"No filing text is available for {context_refs.filing_ref.symbol} "
                f"accession {context_refs.filing_ref.accession_number}."
            ) from exc
        except ProviderUnavailableError as exc:
            raise AdvisorUnavailableError(exc) from exc

        segmented = result.value
        symbol = context_refs.filing_ref.symbol
        accession_number = context_refs.filing_ref.accession_number
        filing_document = build_filing_document(segmented, _MAX_FILING_CHARS)

        excerpt_suffix = " [section excerpt]" if segmented.mode == "sections" else ""
        if filing_document.was_truncated:
            excerpt_suffix = " [truncated excerpt]"

        document: DocumentBlockParam = {
            "type": "document",
            "source": {
                "type": "text",
                "media_type": "text/plain",
                "data": filing_document.text,
            },
            "title": f"{symbol} {segmented.form} filing ({accession_number}){excerpt_suffix}",
            "citations": {"enabled": True},
            # A filing is immutable once published, so this block is
            # byte-identical across every question about the same filing --
            # and it's by far the largest thing in the request. Caching it
            # makes a follow-up question cost a fraction of the first.
            #
            # Placement is already correct by construction: this document
            # is the first content block, ahead of the provenance note,
            # the assembled context, and the question, so the cached
            # prefix is the system prompt plus this document and the
            # volatile text sits after the breakpoint. Default 5-minute
            # TTL, which breaks even at two questions about one filing.
            "cache_control": {"type": "ephemeral"},
        }
        return _FilingAttachment(
            document=document,
            source_label=f"SEC EDGAR filing ({symbol} {segmented.form}){excerpt_suffix}",
            provenance_note=filing_document.provenance_note(),
        )

    async def _build_portfolio_context(
        self, symbols: list[str] | None, readings: list[SourceReading]
    ) -> ContextItem | None:
        """Portfolio totals and holdings, with every figure already computed in `app.domain`.

        Built on `SnapTradeService.get_rollup`, the same rollup the map draws, so
        the advisor can't disagree with it. Shares and totals are always of the
        whole portfolio: `symbols` narrows which holdings are listed, not what
        they're a share of. `flag_concentrated` is called directly here, since
        concentration flagging isn't part of the rollup.
        """
        try:
            result = await self._snaptrade_service.get_rollup()
        except ProviderUnavailableError:
            readings.append(_unavailable(_PORTFOLIO_SOURCE))
            return None

        rollup = result.value
        rows = rollup.positions
        if symbols:
            wanted = {symbol.upper() for symbol in symbols}
            rows = [row for row in rows if row.symbol.upper() in wanted]
        if not rows:
            return None

        allocations = [
            Allocation(symbol=row.symbol, percent=row.share_of_value_pct) for row in rows
        ]
        concentrated_symbols = {
            a.symbol for a in flag_concentrated(allocations, _CONCENTRATION_THRESHOLD_PCT)
        }

        lines = [
            f"Portfolio totals (all positions): market value ${rollup.total_market_value:.2f}, "
            f"cost basis ${rollup.total_cost_basis:.2f}, "
            f"net unrealized gain ${rollup.net_gain_dollars:.2f}.",
            "Current holdings:",
        ]
        for row in rows:
            pnl_pct = f"{row.gain_percent:.1f}%" if row.gain_percent is not None else "n/a"
            cost_share = (
                f", {row.share_of_cost_pct:.1f}% of total cost"
                if row.share_of_cost_pct is not None
                else ""
            )
            gain_share = (
                f", {row.share_of_net_gain_pct:.1f}% of net unrealized gain"
                if row.share_of_net_gain_pct is not None
                else ""
            )
            flag = " [over 20% of portfolio]" if row.symbol in concentrated_symbols else ""
            lines.append(
                f"- {row.symbol}: {row.quantity} shares, market value ${row.market_value:.2f}, "
                f"cost basis ${row.cost_basis:.2f}, "
                f"{row.share_of_value_pct:.1f}% of portfolio{cost_share}, "
                f"unrealized P&L ${row.gain_dollars:.2f} ({pnl_pct}){gain_share}{flag}"
            )

        readings.append(_reading(_PORTFOLIO_SOURCE, result.as_of, result.is_stale))
        return ContextItem(source=_PORTFOLIO_SOURCE, as_of=result.as_of, text="\n".join(lines))

    async def _match_symbols_in_question(self, question: str) -> list[str]:
        """Which held symbols (by ticker or company name) `question` mentions.

        Only called when the caller supplied no explicit symbols and no filing
        reference.
        """
        return match_held_symbols(question, await self._load_held())

    async def _load_held(self) -> list[HeldSymbol]:
        """Every held symbol, largest first, with its company name where known.

        Fails gracefully to nothing held rather than raising, mirroring
        `_build_portfolio_context`'s handling of an unavailable brokerage
        connection -- a general question with nothing to match against should
        still fall back to today's holdings-only behavior, not error out.
        """
        try:
            result = await self._snaptrade_service.get_rollup()
        except ProviderUnavailableError:
            return []

        rows = result.value.positions
        if not rows:
            return []

        try:
            names = await self._edgar_service.resolve_company_names([row.symbol for row in rows])
        except ProviderUnavailableError:
            names = {}
        return [HeldSymbol(symbol=row.symbol, company_name=names.get(row.symbol)) for row in rows]

    async def _build_facts_context(
        self, symbols: list[str], filing_ref: FilingRef | None, readings: list[SourceReading]
    ) -> list[ContextItem]:
        """SEC XBRL facts for every symbol in scope, newest period first.

        Selection is symbol-wide rather than scoped to the referenced
        filing, because a single filing's figures can't answer a question
        about a trend -- but facts the referenced filing reported are
        marked, so the model can still say "this filing reported" instead
        of only "the company reported".

        A filing reference implies its symbol even when the caller didn't
        list it: asking about a 10-K is asking about that company.
        """
        upper_symbols = [symbol.upper() for symbol in symbols]
        if filing_ref is not None:
            upper_symbols.append(filing_ref.symbol.upper())

        items: list[ContextItem] = []
        # dict.fromkeys rather than a set: a caller listing the same symbol
        # twice shouldn't reorder the context non-deterministically.
        for symbol in dict.fromkeys(upper_symbols):
            referenced_accession = (
                filing_ref.accession_number
                if filing_ref is not None and filing_ref.symbol.upper() == symbol
                else None
            )
            source = f"SEC XBRL facts ({symbol})"
            try:
                result = await self._xbrl_service.get_facts(
                    symbol, referenced_accession=referenced_accession
                )
            except ProviderNotFoundError:
                continue
            except ProviderUnavailableError:
                readings.append(_unavailable(source))
                continue

            # An all-absent snapshot would be a block of context saying
            # nothing was found. The model already handles "the context
            # doesn't cover that" correctly; noise here would only crowd
            # out the narrative excerpt.
            if not result.value.facts:
                continue

            readings.append(_reading(source, result.as_of, result.is_stale))
            items.append(
                ContextItem(
                    source=source,
                    as_of=result.as_of,
                    text=_render_xbrl_facts(result.value, result.as_of),
                )
            )
        return items

    async def _build_fundamentals_context(
        self, symbols: list[str], readings: list[SourceReading]
    ) -> list[ContextItem]:
        items: list[ContextItem] = []
        for symbol in symbols:
            try:
                result = await self._fmp_service.get_fundamentals(symbol)
            except ProviderNotFoundError:
                continue
            except ProviderUnavailableError:
                readings.append(_unavailable(f"FMP fundamentals ({symbol})"))
                continue

            fields = result.value.model_dump(exclude={"symbol"}, exclude_none=True)
            if not fields:
                continue
            lines = [f"Fundamentals for {result.value.symbol}:"]
            lines.extend(f"- {name}: {value}" for name, value in fields.items())
            source = f"FMP fundamentals ({result.value.symbol})"
            readings.append(_reading(source, result.as_of, result.is_stale))
            items.append(
                ContextItem(
                    source=source,
                    as_of=result.as_of,
                    text="\n".join(lines),
                )
            )
        return items

    async def _build_news_context(
        self, symbols: list[str], readings: list[SourceReading]
    ) -> ContextItem | None:
        try:
            result = await self._finnhub_service.get_news_for_symbols(symbols)
        except ProviderUnavailableError:
            readings.append(_unavailable(_NEWS_SOURCE))
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

        readings.append(_reading(_NEWS_SOURCE, result.as_of, result.is_stale))
        return ContextItem(source=_NEWS_SOURCE, as_of=result.as_of, text="\n".join(lines))


def _render_xbrl_facts(snapshot: XbrlFacts, as_of: dt.datetime) -> str:
    """Render one symbol's facts as context, grouped by line item.

    Grouped by label rather than emitted as a flat list so a trend reads
    as a trend: every period for one concept sits together, newest first,
    each carrying the accession number of the filing that reported it.
    """
    lines = [
        f"SEC XBRL structured facts for {snapshot.symbol} "
        f"(retrieved {as_of.date().isoformat()}). Each figure below is a value the "
        "company reported in the filing named beside it.",
    ]

    by_label: dict[str, list[XbrlFact]] = {}
    for fact in snapshot.facts:
        by_label.setdefault(fact.label, []).append(fact)

    for label, facts in by_label.items():
        lines.append(f"{label} ({facts[0].unit}):")
        lines.extend(f"- {_render_fact(fact)}" for fact in facts)

    if snapshot.missing_labels:
        lines.append(
            "No values were available in SEC's structured data for these line items: "
            f"{'; '.join(snapshot.missing_labels)}. Treat them as outside this data -- "
            "not as figures the company failed to report. Some are genuinely never "
            "tagged by a given filer, and some measures (a REIT's FFO, for instance) "
            "are non-GAAP and never appear in structured data at all."
        )

    return "\n".join(lines)


def _render_fact(fact: XbrlFact) -> str:
    period = (
        f"{fact.period_start.isoformat()} to {fact.period_end.isoformat()}"
        if fact.period_start is not None
        else f"as of {fact.period_end.isoformat()}"
    )
    marker = " [reported by the filing in question]" if fact.from_referenced_filing else ""
    return (
        f"{period}: {fact.value} "
        f"[{fact.form} accession {fact.accession_number}, filed {fact.filed.isoformat()}]{marker}"
    )


def _build_user_content(
    context_items: list[ContextItem],
    attachment: _FilingAttachment | None,
    question: str,
) -> list[DocumentBlockParam | TextBlockParam]:
    content: list[DocumentBlockParam | TextBlockParam] = []
    blocks = []
    if attachment is not None:
        content.append(attachment.document)
        blocks.append(attachment.provenance_note)

    blocks.extend(item.text for item in context_items)
    context_text = "\n\n".join(blocks)
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

    for block in response.content:
        if getattr(block, "type", None) != "text":
            continue
        answer_parts.append(block.text)
        for raw_citation in getattr(block, "citations", None) or []:
            citation = _to_citation(raw_citation, filing_source_label)
            if citation is not None:
                citations.append(citation)

    return "".join(answer_parts), citations


def _to_citation(
    raw_citation: Any,  # noqa: ANN401 -- the SDK's citation union; every member has `cited_text`
    filing_source_label: str | None,
) -> Citation | None:
    cited_text = getattr(raw_citation, "cited_text", None)
    if not cited_text:
        return None
    return Citation(
        source=filing_source_label or "Claude citation", quote=cited_text, as_of=_utcnow()
    )
