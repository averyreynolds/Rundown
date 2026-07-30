"""`POST /advisor/chat` -- the grounded, cited, never-directive AI advisor.

See `app/services/claude_service.py`'s module docstring for how the
no-directive-advice and context-grounding rules (CLAUDE.md hard rules 1
and 2) are enforced.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_claude_service
from app.schemas.advisor import ChatRequest, ChatResponse
from app.services.claude_service import ClaudeService

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.post("/chat", summary="Ask the advisor a question grounded in your own data")
async def chat(
    request: ChatRequest,
    claude_service: Annotated[ClaudeService, Depends(get_claude_service)],
) -> ChatResponse:
    """422s if no context is available at all; 502s if Claude itself is unavailable."""
    return await claude_service.chat(request.question, request.context_refs)
