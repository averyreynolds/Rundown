"""A fake Anthropic client matching only the surface `ClaudeService` calls.

Shaped to match `anthropic.AsyncAnthropic.messages.create()`'s return
value (a `Message` with a `.content` list of text blocks, each optionally
carrying `.citations`) closely enough for `ClaudeService` to use
unmodified -- no live API key is used or required.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock


def fake_anthropic_client(
    text: str = "This is a neutral, grounded answer.",
    *,
    citations: list[Any] | None = None,
    error: Exception | None = None,
) -> SimpleNamespace:
    message = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text, citations=citations)]
    )
    create_mock = AsyncMock(side_effect=error, return_value=None if error else message)
    return SimpleNamespace(messages=SimpleNamespace(create=create_mock))
