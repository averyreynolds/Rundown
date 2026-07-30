"""Request/response schemas for `POST /advisor/chat`."""

from datetime import datetime

from pydantic import BaseModel, Field


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
