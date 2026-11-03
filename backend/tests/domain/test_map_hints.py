"""Tests for `app.domain.map_hints`."""

import pytest

from app.domain.map_hints import MapSizing, derive_map_hint
from app.domain.symbol_matching import HeldSymbol

_HELD = [
    HeldSymbol(symbol="NVDA", company_name="NVIDIA Corp."),
    HeldSymbol(symbol="UNH", company_name="UnitedHealth Group Inc."),
    HeldSymbol(symbol="XOM", company_name=None),
]


def test_named_position_gets_focus_and_gain_sizing() -> None:
    hint = derive_map_hint("NVDA makes up 46% of your gain", _HELD, previous_focus=())

    assert hint.focus == ("NVDA",)
    assert hint.sizing is MapSizing.GAIN


def test_sentence_naming_nothing_keeps_the_prior_focus() -> None:
    hint = derive_map_hint("The position cost $4,400", _HELD, previous_focus=("NVDA",))

    assert hint.focus == ("NVDA",)
    assert hint.sizing is MapSizing.COST


def test_a_company_name_counts_as_naming_a_position() -> None:
    assert derive_map_hint("NVIDIA grew.", _HELD, previous_focus=()).focus == ("NVDA",)


def test_sentence_naming_two_held_symbols_focuses_both() -> None:
    hint = derive_map_hint("UNH and XOM both filed.", _HELD, previous_focus=("NVDA",))

    assert hint.focus == ("UNH", "XOM")


def test_company_not_held_focuses_nothing_new() -> None:
    hint = derive_map_hint("Tesla is unrelated to this.", _HELD, previous_focus=("NVDA",))

    assert hint.focus == ("NVDA",)


def test_nothing_named_and_no_prior_focus_focuses_nothing() -> None:
    assert derive_map_hint("Your portfolio grew.", _HELD, previous_focus=()).focus == ()


@pytest.mark.parametrize(
    "sentence",
    [
        "That is most of your gain.",
        "It makes up 46% of your gains.",
        "The position gained 85%.",
        "The loss came from one holding.",
        "Losses were small.",
        "Its profit is the largest.",
        "Unrealized P&L is $500.",
        "It is down 30.9% from cost.",
        "It is up 85% since cost.",
    ],
)
def test_gain_and_loss_wording_sizes_by_gain(sentence: str) -> None:
    assert derive_map_hint(sentence, _HELD, previous_focus=()).sizing is MapSizing.GAIN


@pytest.mark.parametrize(
    "sentence",
    ["The position cost $4,400.", "That is 8.2% of your total cost basis.", "You paid $4,400."],
)
def test_cost_wording_sizes_by_cost(sentence: str) -> None:
    assert derive_map_hint(sentence, _HELD, previous_focus=()).sizing is MapSizing.COST


@pytest.mark.parametrize(
    "sentence",
    [
        "At today's value it's 13.1% of the portfolio.",
        "It regained ground.",
        "Revenue was costly to report.",
        "Nothing relevant here.",
        "",
    ],
)
def test_no_matching_terms_sizes_by_value(sentence: str) -> None:
    assert derive_map_hint(sentence, _HELD, previous_focus=()).sizing is MapSizing.VALUE


def test_sizing_is_always_one_of_the_closed_set() -> None:
    assert {member.value for member in MapSizing} == {"value", "cost", "gain"}


def test_focus_only_ever_contains_held_symbols() -> None:
    hint = derive_map_hint("AAPL, TSLA, NVDA, and GME moved.", _HELD, previous_focus=())

    assert hint.focus == ("NVDA",)
