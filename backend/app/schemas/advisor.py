"""Request/response schemas for `POST /advisor/chat` and `POST /advisor/chat/stream`."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.map_hints import MapSizing


class FilingRef(BaseModel):
    """A specific filing to ground a summarization request in."""

    symbol: str
    accession_number: str


class ContextRefs(BaseModel):
    """Which specific data the advisor should ground its answer in.

    The advisor never free-associates over "the user's portfolio" in the
    abstract (CLAUDE.md hard rule 2) -- the caller names exactly which
    symbols/filing to consider, and the service assembles only that data
    into context. Both fields are optional and independent: a question
    can reference symbols, a filing, both, or (if a SnapTrade connection
    exists) neither and still get whole-portfolio context.
    """

    symbols: list[str] = Field(default_factory=list)
    filing_ref: FilingRef | None = None


class ChatRequest(BaseModel):
    question: str
    context_refs: ContextRefs = Field(default_factory=ContextRefs)


class Citation(BaseModel):
    """One source citation backing a specific claim in the advisor's answer."""

    source: str
    quote: str
    as_of: datetime


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)


class SourceReading(BaseModel):
    """One source the backend read for an answer, or tried to.

    `as_of` is `None` only when `status` is `unavailable`: nothing was read, so
    there's no data to date. Reporting those is what stops an answer looking
    grounded in a source that couldn't be reached.
    """

    source: str
    as_of: datetime | None
    status: Literal["used", "stale", "unavailable"]


class ScopeEvent(BaseModel):
    """Which held symbols this answer is about, for the map to mark as being read."""

    type: Literal["scope"] = "scope"
    symbols: list[str]


class ReadingEvent(SourceReading):
    type: Literal["reading"] = "reading"


class SentenceEvent(BaseModel):
    """One sentence that has passed the directive guard, with what the map should show."""

    type: Literal["sentence"] = "sentence"
    text: str
    focus: list[str]
    sizing: MapSizing
    citations: list[Citation] = Field(default_factory=list)


class RetractEvent(BaseModel):
    """A later check failed: `message` replaces every sentence already sent."""

    type: Literal["retract"] = "retract"
    message: str


class DoneEvent(BaseModel):
    """The answer finished. `citations` are any not attached to a sentence."""

    type: Literal["done"] = "done"
    sources: list[SourceReading]
    citations: list[Citation] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)


class InterruptedEvent(BaseModel):
    """The answer stopped early: Claude failed (`unavailable`) or declined (`declined`)."""

    type: Literal["interrupted"] = "interrupted"
    reason: Literal["unavailable", "declined"]
    citations: list[Citation] = Field(default_factory=list)


class IncompleteEvent(BaseModel):
    """The answer hit the token limit, so what was sent is checked but cut short."""

    type: Literal["incomplete"] = "incomplete"
    sources: list[SourceReading]
    citations: list[Citation] = Field(default_factory=list)


AdvisorStreamEvent = (
    ScopeEvent
    | ReadingEvent
    | SentenceEvent
    | RetractEvent
    | DoneEvent
    | InterruptedEvent
    | IncompleteEvent
)
