"""Suggested next questions, from fixed templates and never written by the model.

Each question stands alone, since the advisor keeps no conversation memory, so
every template names its position in full. Templates ask what the data shows and
never what to do, which `tests/services/test_claude_service.py` checks against the
directive guard.
"""

from collections.abc import Sequence

_MAX_LARGEST_POSITIONS = 2


def suggested_follow_ups(focus: Sequence[str], held_by_value: Sequence[str]) -> list[str]:
    """Return questions to offer after an answer.

    Args:
        focus: The positions the answer ended on, first being the one to ask about.
        held_by_value: Every held symbol, largest first.
    """
    others = [symbol for symbol in held_by_value if symbol not in focus]
    if not focus:
        return [_relevant_to(symbol) for symbol in others[:_MAX_LARGEST_POSITIONS]]

    questions = [
        f"How much of my gain comes from {focus[0]}?",
        f"What's in the news about {focus[0]}?",
    ]
    if others:
        questions.append(_relevant_to(others[0]))
    return questions


def _relevant_to(symbol: str) -> str:
    return f"What's relevant to my {symbol} position?"
