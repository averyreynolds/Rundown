"""Tests for `app.domain.symbol_matching`."""

from app.domain.symbol_matching import HeldSymbol, match_held_symbols


def test_matches_a_ticker_mentioned_as_a_standalone_word() -> None:
    held = [HeldSymbol(symbol="AAPL", company_name="Apple Inc.")]

    assert match_held_symbols("What's going on with aapl?", held) == ["AAPL"]


def test_matches_a_company_name_with_no_ticker_mentioned() -> None:
    held = [HeldSymbol(symbol="COMP", company_name="Compass, Inc.")]

    assert match_held_symbols("What's relevant to my Compass position?", held) == ["COMP"]


def test_matches_multiple_held_symbols_in_held_order() -> None:
    held = [
        HeldSymbol(symbol="AAPL", company_name="Apple Inc."),
        HeldSymbol(symbol="COMP", company_name="Compass, Inc."),
    ]

    assert match_held_symbols("Compare Compass and AAPL", held) == ["AAPL", "COMP"]


def test_ticker_as_substring_inside_a_longer_word_is_not_matched() -> None:
    held = [HeldSymbol(symbol="GO", company_name=None)]

    assert match_held_symbols("I'm going to check my portfolio", held) == []


def test_single_word_of_a_multi_word_name_alone_is_not_matched() -> None:
    held = [HeldSymbol(symbol="AWK", company_name="American Water Works Company, Inc.")]

    assert match_held_symbols("I need to top off the water in the tank", held) == []


def test_full_normalized_multi_word_name_matches_as_a_phrase() -> None:
    held = [HeldSymbol(symbol="AWK", company_name="American Water Works Company, Inc.")]

    assert match_held_symbols("How is American Water Works doing lately?", held) == ["AWK"]


def test_single_word_company_name_matches_after_suffix_stripping() -> None:
    """Accepted limitation: a name that normalizes to one common word (e.g.
    "Target Corporation" -> "Target") carries the same false-positive risk
    as a common-word ticker -- documented, not solved here."""
    held = [HeldSymbol(symbol="TGT", company_name="Target Corporation")]

    assert match_held_symbols("How is Target doing lately?", held) == ["TGT"]


def test_symbol_with_no_company_name_still_matches_on_ticker() -> None:
    held = [HeldSymbol(symbol="VOO", company_name=None)]

    assert match_held_symbols("How's my VOO position?", held) == ["VOO"]


def test_ticker_or_name_not_in_held_is_not_matched() -> None:
    held = [HeldSymbol(symbol="AAPL", company_name="Apple Inc.")]

    assert match_held_symbols("What about MSFT or Microsoft?", held) == []


def test_empty_held_returns_empty_list() -> None:
    assert match_held_symbols("What about AAPL?", []) == []


def test_empty_question_returns_empty_list() -> None:
    held = [HeldSymbol(symbol="AAPL", company_name="Apple Inc.")]

    assert match_held_symbols("", held) == []


def test_duplicate_symbol_across_two_accounts_matches_once() -> None:
    """`list_positions` is account-scoped, not merged by symbol -- the same
    stock held at two brokerages produces two `HeldSymbol` entries."""
    held = [
        HeldSymbol(symbol="AAPL", company_name="Apple Inc."),
        HeldSymbol(symbol="AAPL", company_name="Apple Inc."),
    ]

    assert match_held_symbols("What's going on with AAPL?", held) == ["AAPL"]
