"""Tests for `app.domain.sentence_stream`."""

import pytest

from app.domain.sentence_stream import SentenceSegmenter


def _segment(*deltas: str) -> list[str]:
    segmenter = SentenceSegmenter()
    sentences: list[str] = []
    for delta in deltas:
        sentences.extend(segmenter.feed(delta))
    sentences.extend(segmenter.flush())
    return sentences


def test_splits_on_sentence_endings() -> None:
    assert _segment("NVDA is up. It cost less. Why? Costs fell!") == [
        "NVDA is up.",
        "It cost less.",
        "Why?",
        "Costs fell!",
    ]


def test_keeps_figures_and_decimals_in_one_sentence() -> None:
    assert _segment("That's $3,756.50 of your $8,207.20 total. It grew 85.4%.") == [
        "That's $3,756.50 of your $8,207.20 total.",
        "It grew 85.4%.",
    ]


@pytest.mark.parametrize(
    "token",
    ["U.S.", "Inc.", "Corp.", "Co.", "Ltd.", "vs.", "e.g.", "i.e.", "10-Q.", "10-K.", "8-K."],
)
def test_abbreviations_and_form_names_do_not_end_a_sentence(token: str) -> None:
    assert _segment(f"Compare {token} Others here. Next one.") == [
        f"Compare {token} Others here.",
        "Next one.",
    ]


def test_numbered_heading_does_not_end_a_sentence() -> None:
    assert _segment("See Item 1. Business for more. Next.") == [
        "See Item 1. Business for more.",
        "Next.",
    ]


def test_does_not_split_before_a_lowercase_word() -> None:
    assert _segment("See the note. for details.") == ["See the note. for details."]


@pytest.mark.parametrize(
    "deltas",
    [
        ("That's $3,", "756.50 total. Next", " one."),
        ("That's $3,756", ".", "50 total", ".", " ", "Next one."),
        tuple("That's $3,756.50 total. Next one."),
    ],
)
def test_boundaries_split_across_deltas_give_the_same_sentences(deltas: tuple[str, ...]) -> None:
    assert _segment(*deltas) == ["That's $3,756.50 total.", "Next one."]


def test_a_sentence_is_only_released_once_the_next_one_has_started() -> None:
    segmenter = SentenceSegmenter()

    assert segmenter.feed("First sentence.") == []
    assert segmenter.feed(" ") == []
    assert segmenter.feed("Second") == ["First sentence."]
    assert segmenter.flush() == ["Second"]


def test_keeps_a_bold_span_with_its_closing_markers() -> None:
    assert _segment("**Margins fell.** Revenue rose.") == ["**Margins fell.**", "Revenue rose."]


def test_does_not_split_inside_a_bold_span() -> None:
    assert _segment("**Margins fell. Revenue rose.** Next.") == [
        "**Margins fell. Revenue rose.**",
        "Next.",
    ]


def test_closing_markers_split_across_deltas() -> None:
    assert _segment("**Margins fell.*", "* Revenue rose.") == [
        "**Margins fell.**",
        "Revenue rose.",
    ]


def test_each_list_item_is_one_unit_with_its_marker() -> None:
    text = "What stands out.\n- UNH fell. It filed.\n* XOM filed.\n1. First. Second.\n"

    assert _segment(text) == [
        "What stands out.",
        "- UNH fell. It filed.",
        "* XOM filed.",
        "1. First. Second.",
    ]


def test_a_list_marker_split_across_deltas_stays_a_list_item() -> None:
    assert _segment("-", " UNH fell. It filed.", "\n", "Next.") == [
        "- UNH fell. It filed.",
        "Next.",
    ]


def test_a_bold_line_is_not_mistaken_for_a_list_item() -> None:
    assert _segment("*", "*Margins fell.** Revenue rose.") == [
        "**Margins fell.**",
        "Revenue rose.",
    ]


def test_a_line_break_ends_a_fragment_and_blank_lines_are_ignored() -> None:
    assert _segment("A heading\n\n  Second para.  \n") == ["A heading", "Second para."]


def test_flush_releases_an_unterminated_final_fragment() -> None:
    assert _segment("One sentence. And a fragment") == ["One sentence.", "And a fragment"]


def test_flush_releases_an_unterminated_list_item() -> None:
    assert _segment("- A list item with no newline") == ["- A list item with no newline"]


def test_flush_leaves_nothing_behind() -> None:
    segmenter = SentenceSegmenter()
    segmenter.feed("A fragment")

    assert segmenter.flush() == ["A fragment"]
    assert segmenter.flush() == []


@pytest.mark.parametrize("text", ["", "   ", "\n\n", " \n "])
def test_empty_text_yields_nothing(text: str) -> None:
    assert _segment(text) == []
