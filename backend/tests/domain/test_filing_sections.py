"""Tests for `app.domain.filing_sections`.

The point of this module is surviving *filer format variation*, so these
tests are organized around the specific ways EDGAR documents differ from
each other -- inline XBRL, table-of-contents duplication, Part-scoped
Item numbering, plain-text legacy filings -- rather than around lines of
code. Every fixture is fabricated (CLAUDE.md hard rule 5).
"""

import pytest

from app.domain.filing_sections import (
    build_filing_document,
    filing_html_to_text,
    looks_like_html,
    normalize_form,
    segment_filing,
)
from tests.fixtures.synthetic_filing import (
    SYNTHETIC_8K_HTML,
    SYNTHETIC_PLAIN_TEXT_10K,
    synthetic_10k_html,
    synthetic_10q_html,
)

_BUDGET = 300_000


def _labels(raw: str, form: str) -> list[str]:
    return [section.label for section in segment_filing(raw, form).sections]


def _text_for(raw: str, form: str, key: str) -> str:
    sections = {s.key: s.text for s in segment_filing(raw, form).sections}
    return sections[key]


# --- Stage 1: markup normalization -----------------------------------------


def test_hidden_inline_xbrl_facts_are_dropped() -> None:
    text = filing_html_to_text(synthetic_10k_html())
    assert "XBRL-ONLY-FACT-DO-NOT-SURFACE" not in text
    assert "contextRef" not in text
    assert "99999" not in text


def test_script_and_style_bodies_are_dropped() -> None:
    text = filing_html_to_text(synthetic_10k_html())
    assert "trackPageView" not in text
    assert "display:none" not in text


def test_adjacent_table_cells_do_not_concatenate() -> None:
    """The bug the old stdlib extractor had: `<td>Revenue</td><td>$1,234</td>`
    came out as `Revenue$1,234`, making every financial table unreadable."""
    text = filing_html_to_text("<table><tr><td>Revenue</td><td>$1,234</td></tr></table>")
    assert "Revenue$1,234" not in text
    assert "Revenue" in text
    assert "$1,234" in text


def test_inline_tags_do_not_split_sentences() -> None:
    """iXBRL wraps individual numbers mid-sentence. Separating inline
    elements would shred every sentence in the filing, which would in turn
    make Citations API `cited_text` unreadable."""
    text = filing_html_to_text(
        "<p>Segment margin was <ix:nonFraction contextRef='c-2'>42</ix:nonFraction>% "
        "for the year.</p>"
    )
    assert "Segment margin was 42% for the year." in text


def test_html_entities_are_decoded() -> None:
    assert "Item 1 — Business" in filing_html_to_text("<p>Item 1 &#8212; Business</p>")


def test_non_breaking_spaces_become_plain_spaces() -> None:
    assert filing_html_to_text("<p>Item&#160;1A. Risk Factors</p>") == "Item 1A. Risk Factors"


def test_plain_text_filings_skip_the_html_parser() -> None:
    assert looks_like_html(SYNTHETIC_PLAIN_TEXT_10K) is False
    assert "ITEM 1A. RISK FACTORS" in filing_html_to_text(SYNTHETIC_PLAIN_TEXT_10K)


# --- Stage 2: Item segmentation --------------------------------------------


def test_10k_extracts_exactly_the_portfolio_relevant_items() -> None:
    labels = _labels(synthetic_10k_html(), "10-K")
    assert labels == [
        "Item 1A. Risk Factors",
        "Item 3. Legal Proceedings",
        (
            "Item 5. Market for Registrant's Common Equity, Related Stockholder "
            "Matters and Issuer Purchases of Equity Securities"
        ),
        (
            "Item 7. Management's Discussion and Analysis of Financial Condition "
            "and Results of Operations"
        ),
        "Item 7A. Quantitative and Qualitative Disclosures About Market Risk",
    ]


def test_10k_excludes_business_and_financial_statements() -> None:
    """Item 1 is long and static; Item 8 is enormous and FMP already
    supplies the ratios it backs."""
    segmented = segment_filing(synthetic_10k_html(), "10-K")
    body = "\n".join(section.text for section in segmented.sections)
    assert "long and static" not in body
    assert "audited synthetic financial" not in body


@pytest.mark.parametrize(
    ("heading_variant", "expected_key"),
    [
        ("<p><b>Item 1A. Risk Factors</b></p>", "1A"),
        ("<p><b>ITEM 1A - RISK FACTORS</b></p>", "1A"),
        ("<p><b>Item 1A&#8212;Risk Factors</b></p>", "1A"),
        ("<p><b>Item&#160;1A: Risk Factors</b></p>", "1A"),
        ("<p><b>item 1a.</b></p>", "1A"),
        ("<p><b>Item 7A</b></p>", "7A"),
    ],
)
def test_heading_punctuation_variants_all_parse(heading_variant: str, expected_key: str) -> None:
    html = (
        f"<html><body>{heading_variant}"
        "<p>Body text long enough to clear the minimum-section-body threshold "
        "that rejects table-of-contents entries.</p></body></html>"
    )
    assert [s.key for s in segment_filing(html, "10-K").sections] == [expected_key]


def test_table_of_contents_entries_lose_to_the_real_section() -> None:
    """Every Item heading appears at least twice in a real filing. The TOC
    copy has a page number as its 'body' and must not win."""
    mdna = _text_for(synthetic_10k_html(), "10-K", "7")
    assert "Revenue increased to $1,234 million" in mdna
    assert mdna.strip() != "28"


def test_item_number_boundaries_are_exact() -> None:
    """`Item 1A` must not register as `Item 1`, nor `Item 7A` as `Item 7` --
    a greedy or unanchored match would silently mislabel Risk Factors as
    Business and hand the advisor the wrong section under the right name."""
    body = "<p>Body text long enough to clear the minimum-section-body threshold.</p>"
    html = (
        f"<html><body><p>Item 1A. Risk Factors</p>{body}"
        f"<p>Item 7A. Market Risk</p>{body}"
        f"<p>Item 10. Directors and Executive Officers</p>{body}</body></html>"
    )
    assert {s.key for s in segment_filing(html, "10-K").sections} == {"1A", "7A"}


def test_prose_cross_reference_does_not_split_a_section() -> None:
    """`Item 8 of this Annual Report contains ...` starts a line inside the
    real Item 8 body; it must not be mistaken for a heading elsewhere."""
    segmented = segment_filing(synthetic_10k_html(), "10-K")
    assert "8" not in {section.key for section in segmented.sections}


def test_section_text_is_verbatim() -> None:
    """CLAUDE.md hard rule 2: filing-derived claims must be traceable to
    source passages, which fails the moment extraction rewrites anything."""
    sentence = "A hypothetical 100 basis point move would change fabricated interest expense"
    assert sentence in _text_for(synthetic_10k_html(), "10-K", "7A")


def test_10q_item_1_resolves_by_part_not_by_number() -> None:
    """Part I Item 1 is Financial Statements (excluded); Part II Item 1 is
    Legal Proceedings (included). Number alone is ambiguous."""
    segmented = segment_filing(synthetic_10q_html(), "10-Q")
    assert [s.key for s in segmented.sections] == ["I:2", "I:3", "II:1", "II:1A"]

    legal = next(s for s in segmented.sections if s.key == "II:1")
    assert "No new fabricated proceedings" in legal.text
    assert "balance sheets" not in legal.text


def test_10q_excludes_financial_statements_and_exhibits() -> None:
    body = "\n".join(s.text for s in segment_filing(synthetic_10q_html(), "10-Q").sections)
    assert "Excluded by policy" not in body


def test_8k_passes_through_whole() -> None:
    """8-Ks use a different numbering scheme entirely (2.02, 5.02, 8.01)
    and are short enough that segmenting them costs more than it saves."""
    segmented = segment_filing(SYNTHETIC_8K_HTML, "8-K")
    assert segmented.mode == "whole_document"
    assert "Item 2.02 Results of Operations" in segmented.sections[0].text


def test_plain_text_filing_still_segments() -> None:
    segmented = segment_filing(SYNTHETIC_PLAIN_TEXT_10K, "10-K")
    assert [s.key for s in segmented.sections] == ["1A", "7"]


def test_unrecognizable_filing_falls_back_to_whole_document() -> None:
    """Better a labeled whole-document excerpt than silently no context."""
    segmented = segment_filing("<html><body><p>No item headings here.</p></body></html>", "10-K")
    assert segmented.mode == "unsegmented"
    assert "No item headings here." in segmented.sections[0].text


def test_missing_sections_are_reported_not_silently_dropped() -> None:
    html = (
        "<html><body><p>Item 7. MD&amp;A</p>"
        "<p>Only MD&amp;A is present in this filing, long enough to clear the "
        "minimum body threshold for a real section.</p></body></html>"
    )
    segmented = segment_filing(html, "10-K")
    assert [s.key for s in segmented.sections] == ["7"]
    assert "Item 1A. Risk Factors" in segmented.missing_labels


@pytest.mark.parametrize(
    ("form", "expected"),
    [("10-K", "10-K"), ("10-K/A", "10-K"), ("10-K405", "10-K"), ("10-Q/A", "10-Q"), ("S-8", "S-8")],
)
def test_form_suffixes_are_normalized(form: str, expected: str) -> None:
    assert normalize_form(form) == expected


def test_amended_filings_use_the_base_form_policy() -> None:
    assert [s.key for s in segment_filing(synthetic_10k_html(), "10-K/A").sections] == [
        "1A",
        "3",
        "5",
        "7",
        "7A",
    ]


# --- Budget fitting ---------------------------------------------------------


def test_document_includes_every_section_when_it_fits() -> None:
    document = build_filing_document(segment_filing(synthetic_10k_html(), "10-K"), _BUDGET)
    assert document.was_truncated is False
    assert len(document.included_labels) == 5
    assert "Revenue increased to $1,234 million" in document.text


def test_sections_are_emitted_in_document_order() -> None:
    document = build_filing_document(segment_filing(synthetic_10k_html(), "10-K"), _BUDGET)
    positions = [document.text.index(label) for label in document.included_labels]
    assert positions == sorted(positions)


def test_tight_budget_keeps_mdna_and_drops_legal_proceedings() -> None:
    """The regression this whole change exists for: a head-truncating
    `text[:max_chars]` on a large 10-K kept the cover page and table of
    contents and cut off before MD&A. Priority fill inverts that."""
    document = build_filing_document(segment_filing(synthetic_10k_html(), "10-K"), 400)
    assert any("Management's Discussion" in label for label in document.included_labels)
    assert any("Legal Proceedings" in label for label in document.omitted_labels)


def test_omitted_labels_cover_dropped_missing_and_policy_excluded() -> None:
    document = build_filing_document(segment_filing(synthetic_10k_html(), "10-K"), _BUDGET)
    assert "Item 1. Business" in document.omitted_labels
    assert "Item 8. Financial Statements and Supplementary Data" in document.omitted_labels


def test_provenance_note_names_included_and_omitted_sections() -> None:
    """Without this the model reports that the *filing* is silent on a
    topic when in fact only the *excerpt* is -- a trust-breaking answer
    that reads as authoritative."""
    note = build_filing_document(
        segment_filing(synthetic_10k_html(), "10-K"), _BUDGET
    ).provenance_note()
    assert "Item 7." in note
    assert "Item 1. Business" in note
    assert "outside this excerpt" in note


def test_provenance_note_flags_truncation() -> None:
    note = build_filing_document(
        segment_filing(synthetic_10k_html(), "10-K"), 400
    ).provenance_note()
    assert "cut off" in note


def test_document_respects_the_budget() -> None:
    document = build_filing_document(segment_filing(synthetic_10k_html(), "10-K"), 400)
    assert len(document.text) <= 400


def test_non_positive_budget_is_rejected() -> None:
    segmented = segment_filing(synthetic_10k_html(), "10-K")
    with pytest.raises(ValueError, match="max_chars must be positive"):
        build_filing_document(segmented, 0)


# --- Pointer sections (incorporation by reference) --------------------------
# SEC rules let a filer satisfy an Item by pointing elsewhere instead of
# restating the content, and large filers lean on it hard. Segmentation
# is *correct* in those cases -- the section really does say only that --
# but handing the advisor a page number labeled "MD&A" is exactly the
# silently-wrong grounding hard rule 6 exists to prevent.
#
# The wording below is taken from real filings (JPMorgan, Tesla, P&G,
# UnitedHealth, Coca-Cola), which is the point: the phrasing varies
# wildly while the length does not.

_POINTER_10K = """<html><body>
<p>Item 3. Legal Proceedings</p>
<p>Refer to Note 30 for a description of the Firm's material legal proceedings.</p>
<p>Item 7. Management's Discussion and Analysis</p>
<p>Management's discussion and analysis of financial condition and results of
operations, entitled "Management's discussion and analysis," appears on pages
46-160. Such information should be read in conjunction with the Consolidated
Financial Statements and Notes thereto, which appear on pages 165-314.</p>
<p>Item 7A. Market Risk</p>
<p>The information required by this item is incorporated by reference to the
section entitled Other Information in the MD&amp;A and Note 9.</p>
</body></html>"""


def test_pointer_sections_are_flagged_regardless_of_phrasing() -> None:
    """Three different real-world deferral wordings -- "Refer to Note 30",
    "appears on pages 46-160", and "incorporated by reference" -- none of
    which a single phrase pattern would catch together."""
    sections = {s.key: s for s in segment_filing(_POINTER_10K, "10-K").sections}
    assert sections["3"].is_pointer is True
    assert sections["7"].is_pointer is True
    assert sections["7A"].is_pointer is True


def test_substantive_sections_are_not_flagged_as_pointers() -> None:
    long_body = "We face substantive fabricated risks in our operations. " * 40
    html = f"<html><body><p>Item 1A. Risk Factors</p><p>{long_body}</p></body></html>"
    sections = segment_filing(html, "10-K").sections
    assert len(sections) == 1
    assert sections[0].is_pointer is False


def test_provenance_note_warns_that_pointer_sections_lack_substance() -> None:
    note = build_filing_document(segment_filing(_POINTER_10K, "10-K"), _BUDGET).provenance_note()
    assert "too short to contain the substance" in note
    assert "Item 7." in note
    assert "do not treat them as the section's full content" in note


def test_pointer_flag_survives_the_cache_round_trip() -> None:
    original = segment_filing(_POINTER_10K, "10-K")
    restored = type(original).from_cacheable(original.to_cacheable())
    assert restored == original
    assert all(section.is_pointer for section in restored.sections)


# --- Cache round-trip -------------------------------------------------------


def test_segmented_filing_survives_a_cache_round_trip() -> None:
    """`CacheRepository` stores JSON, so the parse result has to serialize
    losslessly or the cached path would silently differ from the live one."""
    original = segment_filing(synthetic_10k_html(), "10-K")
    restored = type(original).from_cacheable(original.to_cacheable())
    assert restored == original
