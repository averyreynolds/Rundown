"""Turns a stream of text deltas into complete sentences, ready to be checked.

Nothing reaches the user until it has passed the directive guard, and the guard
needs whole sentences. A sentence is only released once what follows it proves it
ended, so "$3." never goes out ahead of "50". List items stay one unit with their
marker, and bold spans are never split, so each unit is still valid markdown.

Splitting a little too rarely is the safe direction here: two sentences released
together are checked together. That's why form names like "10-Q." don't end a
sentence even when one really does end there.
"""

import re

_ABBREVIATIONS = frozenset(
    {"u.s.", "inc.", "corp.", "co.", "ltd.", "vs.", "e.g.", "i.e.", "10-q.", "10-k.", "8-k."}
)
_LIST_ITEM = re.compile(r"(?:[-*+]|\d+\.)\s")
# Could still become a list marker once more text arrives: "-", "12", or "12.".
_POSSIBLE_LIST_MARKER = re.compile(r"(?:[-*+]|\d+\.?)")
_CLOSING_MARKERS = "*_\"')]"
_NEXT_SENTENCE_START = re.compile(r"[A-Z0-9$\"'(*_\[]")
_OPENING_MARKERS = "*_\"'("


class SentenceSegmenter:
    """Accumulates deltas with `feed`, releasing sentences as they complete."""

    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, delta: str) -> list[str]:
        """Add `delta` and return any sentences it completed, possibly none."""
        self._buffer += delta
        return self._release()

    def flush(self) -> list[str]:
        """Return whatever remains, for when the stream has ended."""
        remainder = self._buffer
        self._buffer = ""
        return (
            _split_line(remainder.strip()) if not _is_list_item(remainder) else [remainder.strip()]
        )

    def _release(self) -> list[str]:
        sentences: list[str] = []

        # Every line before a newline is complete, whatever it holds.
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            stripped = line.strip()
            if stripped:
                sentences.extend([stripped] if _is_list_item(stripped) else _split_line(stripped))

        # The current line may still be growing: only release what's provably done.
        current = self._buffer.lstrip()
        if not current or _is_list_item(current) or _POSSIBLE_LIST_MARKER.fullmatch(current):
            return sentences
        complete, remainder = _split_complete(current)
        self._buffer = remainder
        sentences.extend(complete)
        return sentences


def _is_list_item(text: str) -> bool:
    return _LIST_ITEM.match(text.lstrip()) is not None


def _split_line(line: str) -> list[str]:
    if not line:
        return []
    complete, remainder = _split_complete(line)
    remainder = remainder.strip()
    return [*complete, remainder] if remainder else complete


def _split_complete(text: str) -> tuple[list[str], str]:
    """Split `text` into sentences proven complete, and the remainder."""
    sentences: list[str] = []
    start = 0
    index = 0

    while index < len(text):
        if text[index] not in ".!?":
            index += 1
            continue

        end = index + 1
        while end < len(text) and text[end] in _CLOSING_MARKERS:
            end += 1
        next_start = end
        while next_start < len(text) and text[next_start].isspace():
            next_start += 1

        ends_here = (
            next_start > end
            and next_start < len(text)
            and _NEXT_SENTENCE_START.match(text[next_start]) is not None
            and not _ends_with_non_terminal(text[start : index + 1])
            and text[start:end].count("**") % 2 == 0
        )
        if ends_here:
            sentences.append(text[start:end])
            start = next_start
            index = next_start
        else:
            index += 1

    return sentences, text[start:]


def _ends_with_non_terminal(text: str) -> bool:
    last_word = text.split()[-1].lower().lstrip(_OPENING_MARKERS)
    return last_word in _ABBREVIATIONS or last_word[:-1].isdigit()
