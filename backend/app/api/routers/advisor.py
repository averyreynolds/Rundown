"""`POST /advisor/chat` and `POST /advisor/chat/stream` -- the grounded, cited,
never-directive AI advisor.

See `app/services/claude_service.py`'s module docstring for how the
no-directive-advice and context-grounding rules (CLAUDE.md hard rules 1
and 2) are enforced.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_claude_service
from app.schemas.advisor import AdvisorStreamEvent, ChatRequest, ChatResponse
from app.services.claude_service import ClaudeService

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.post("/chat", summary="Ask the advisor a question grounded in your own data")
async def chat(
    request: ChatRequest,
    claude_service: Annotated[ClaudeService, Depends(get_claude_service)],
) -> ChatResponse:
    """422s if no context is available at all; 502s if Claude itself is unavailable."""
    return await claude_service.chat(request.question, request.context_refs)


async def _server_sent_events(events: AsyncIterator[AdvisorStreamEvent]) -> AsyncIterator[str]:
    async for event in events:
        yield f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"


@router.post(
    "/chat/stream",
    summary="Ask the advisor, receiving checked sentences as server-sent events",
    response_class=StreamingResponse,
)
async def chat_stream(
    request: ChatRequest,
    claude_service: Annotated[ClaudeService, Depends(get_claude_service)],
) -> StreamingResponse:
    """422s if no context is available at all; 502s if Claude can't be reached.

    Both are decided before the response starts, so they're ordinary statuses.
    Anything that fails later arrives as an event, because the headers have gone.
    A client disconnect cancels the generator, which ends the Claude request.
    """
    answer = await claude_service.open_answer_stream(request.question, request.context_refs)
    return StreamingResponse(
        _server_sent_events(answer.events()),
        media_type="text/event-stream",
        # Sentences must reach the browser as they're released, not when a proxy flushes.
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
