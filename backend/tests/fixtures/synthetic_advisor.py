"""A fake Anthropic client matching only the surface `ClaudeService` calls.

Shaped to match `anthropic.AsyncAnthropic.messages.create()`'s return
value (a `Message` with a `.content` list of text blocks, each optionally
carrying `.citations`) closely enough for `ClaudeService` to use
unmodified -- no live API key is used or required.
"""

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock


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


class FakeAnswerStream:
    """Shaped like `AsyncMessageStreamManager` and the stream it opens.

    Yields the SDK's `text`, `citation`, and (ignored) `thinking` events, then
    answers `get_final_message()`. `closed` records whether the service released
    the stream, which is how a client disconnect cancels the Claude request.
    """

    def __init__(
        self,
        events: list[SimpleNamespace],
        *,
        stop_reason: str,
        open_error: Exception | None,
        mid_error: Exception | None,
    ) -> None:
        self._events = events
        self._stop_reason = stop_reason
        self._open_error = open_error
        self._mid_error = mid_error
        self.opened = False
        self.closed = False

    async def __aenter__(self) -> "FakeAnswerStream":
        if self._open_error is not None:
            raise self._open_error
        self.opened = True
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        self.closed = True

    async def __aiter__(self) -> AsyncIterator[SimpleNamespace]:
        for event in self._events:
            yield event
        if self._mid_error is not None:
            raise self._mid_error

    async def get_final_message(self) -> SimpleNamespace:
        return SimpleNamespace(stop_reason=self._stop_reason)


def text_event(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def citation_event(cited_text: str) -> SimpleNamespace:
    return SimpleNamespace(type="citation", citation=SimpleNamespace(cited_text=cited_text))


def fake_streaming_anthropic_client(
    *chunks: str | SimpleNamespace,
    stop_reason: str = "end_turn",
    open_error: Exception | None = None,
    mid_error: Exception | None = None,
) -> SimpleNamespace:
    """A fake client whose `messages.stream()` yields `chunks`, plain strings being text deltas.

    `client.answer_stream` is the one stream it hands out, for checking `closed`.
    """
    events = [text_event(chunk) if isinstance(chunk, str) else chunk for chunk in chunks]
    answer_stream = FakeAnswerStream(
        events, stop_reason=stop_reason, open_error=open_error, mid_error=mid_error
    )
    return SimpleNamespace(
        messages=SimpleNamespace(stream=MagicMock(return_value=answer_stream)),
        answer_stream=answer_stream,
    )
