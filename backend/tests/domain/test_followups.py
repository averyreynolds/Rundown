"""Tests for `app.domain.followups`."""

from app.domain.followups import suggested_follow_ups

_HELD = ["AAPL", "MSFT", "NVDA", "UNH"]


def test_follow_ups_for_a_focused_position_name_it_and_the_next_largest() -> None:
    assert suggested_follow_ups(("NVDA",), _HELD) == [
        "How much of my gain comes from NVDA?",
        "What's in the news about NVDA?",
        "What's relevant to my AAPL position?",
    ]


def test_the_next_position_is_never_one_already_in_focus() -> None:
    assert suggested_follow_ups(("AAPL", "MSFT"), _HELD)[-1] == (
        "What's relevant to my NVDA position?"
    )


def test_with_no_focus_it_offers_the_largest_positions() -> None:
    assert suggested_follow_ups((), _HELD) == [
        "What's relevant to my AAPL position?",
        "What's relevant to my MSFT position?",
    ]


def test_with_everything_in_focus_it_offers_only_the_focused_questions() -> None:
    assert suggested_follow_ups(("NVDA",), ["NVDA"]) == [
        "How much of my gain comes from NVDA?",
        "What's in the news about NVDA?",
    ]


def test_with_nothing_held_it_offers_nothing() -> None:
    assert suggested_follow_ups((), []) == []


def test_every_follow_up_is_a_complete_question_naming_its_position() -> None:
    """Questions don't carry memory, so a follow-up can't lean on the last answer."""
    for question in [*suggested_follow_ups(("NVDA",), _HELD), *suggested_follow_ups((), _HELD)]:
        assert question.endswith("?")
        assert any(symbol in question for symbol in _HELD)
