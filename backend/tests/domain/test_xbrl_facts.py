"""Tests for `app.domain.xbrl_facts`.

Organized around the ways SEC's `companyfacts` data is awkward -- filers
disagreeing on tag names, the same period reported (and restated) by
several filings, year-to-date spans colliding with real quarters -- rather
than around lines of code. A bug here shows a user a wrong number, which
is the failure mode CLAUDE.md's near-full-coverage rule for `app/domain/`
exists to prevent. Every fixture is fabricated (hard rule 5).
"""

import datetime as dt
from decimal import Decimal

import pytest

from app.domain.xbrl_facts import (
    ALLOWLIST_LABELS,
    SelectedFact,
    SelectedFacts,
    select_facts,
)
from tests.fixtures.synthetic_xbrl import (
    ACCN_FY2024_10K,
    ACCN_FY2025_10K,
    ACCN_Q2_10Q,
    FY2024,
    FY2025,
    synthetic_company_facts,
)


def _labelled(result: SelectedFacts, label: str) -> list[SelectedFact]:
    return [fact for fact in result.facts if fact.label == label]


def _annual(facts: list[SelectedFact]) -> list[SelectedFact]:
    return [fact for fact in facts if fact.period_start is not None and _span(fact) > 300]


def _span(fact: SelectedFact) -> int:
    assert fact.period_start is not None
    return (fact.period_end - fact.period_start).days


# --- Tag resolution ---------------------------------------------------------


def test_falls_back_through_the_tag_chain() -> None:
    """This filer tags revenue as `Revenues`, skipping both ASC-606 concepts."""
    revenue = _labelled(select_facts(synthetic_company_facts()), "Revenue")
    assert revenue
    assert {fact.concept for fact in revenue} == {"Revenues"}


def test_prefers_the_earliest_tag_in_the_chain_when_several_are_present() -> None:
    payload = synthetic_company_facts()
    payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"] = {
        "units": {
            "USD": [
                {
                    "start": FY2025[0],
                    "end": FY2025[1],
                    "val": 777,
                    "accn": ACCN_FY2025_10K,
                    "form": "10-K",
                    "filed": "2025-10-31",
                }
            ]
        }
    }

    revenue = _labelled(select_facts(payload), "Revenue")
    assert {fact.concept for fact in revenue} == {
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    }
    assert [fact.value for fact in revenue] == [Decimal("777")]


def test_reads_the_dei_taxonomy_not_only_us_gaap() -> None:
    shares = _labelled(select_facts(synthetic_company_facts()), "Shares outstanding (cover page)")
    assert [fact.taxonomy for fact in shares] == ["dei"]
    assert [fact.value for fact in shares] == [Decimal("15000000")]


def test_ignores_units_the_allowlist_did_not_ask_for() -> None:
    """The fixture reports a CAD revenue figure; only the USD series is wanted."""
    result = select_facts(synthetic_company_facts())
    assert all(fact.unit != "CAD" for fact in result.facts)
    assert all(fact.value != Decimal("999999") for fact in result.facts)


# --- Restatement / latest-filed --------------------------------------------


def test_restated_period_keeps_the_later_value_and_its_own_accession() -> None:
    """FY2024 revenue was 400 in the FY2024 10-K and 410 in the FY2025 10-K.

    The later filing wins, and the surviving fact must cite the filing
    that actually reported 410 -- citing the FY2024 accession for a
    number it never contained is the silently-wrong provenance CLAUDE.md
    hard rule 6 exists to prevent.
    """
    revenue = _labelled(select_facts(synthetic_company_facts()), "Revenue")
    fy2024 = next(fact for fact in revenue if fact.period_end == dt.date.fromisoformat(FY2024[1]))

    assert fy2024.value == Decimal("410")
    assert fy2024.accession_number == ACCN_FY2025_10K
    assert fy2024.filed == dt.date(2025, 10, 31)


def test_unrestated_period_keeps_its_original_filing() -> None:
    revenue = _labelled(select_facts(synthetic_company_facts()), "Revenue")
    fy2023 = min(_annual(revenue), key=lambda fact: fact.period_end)
    assert fy2023.value == Decimal("300")
    assert fy2023.accession_number == ACCN_FY2024_10K


def test_instant_facts_dedupe_on_the_balance_sheet_date() -> None:
    assets = _labelled(select_facts(synthetic_company_facts()), "Total assets")

    assert [fact.period_end for fact in assets] == [
        dt.date.fromisoformat(FY2025[1]),
        dt.date.fromisoformat(FY2024[1]),
    ]
    # The FY2024 balance was restated from 1,000 to 1,010.
    assert [fact.value for fact in assets] == [Decimal("1100"), Decimal("1010")]


# --- Period shape ----------------------------------------------------------


def test_year_to_date_spans_are_dropped() -> None:
    """A 10-Q reports both a three-month and a six-month figure ending the
    same day. Keeping both would sit a 181-day number beside a 90-day one
    with nothing but the start date to distinguish them."""
    revenue = _labelled(select_facts(synthetic_company_facts()), "Revenue")

    assert all(_span(fact) < 121 or _span(fact) > 300 for fact in revenue)
    assert Decimal("270") not in [fact.value for fact in revenue]


def test_instant_facts_carry_no_period_start() -> None:
    for label in ("Total assets", "Total liabilities", "Shares outstanding (cover page)"):
        facts = _labelled(select_facts(synthetic_company_facts()), label)
        assert facts
        assert all(fact.period_start is None for fact in facts)


def test_duration_facts_always_carry_both_period_bounds() -> None:
    for label in ("Revenue", "Net income", "EPS (diluted)"):
        facts = _labelled(select_facts(synthetic_company_facts()), label)
        assert facts
        assert all(fact.period_start is not None for fact in facts)


# --- Window fitting --------------------------------------------------------


def test_window_limits_annual_and_quarterly_series_independently() -> None:
    revenue = _labelled(
        select_facts(synthetic_company_facts(), annual_periods=1, quarterly_periods=1),
        "Revenue",
    )

    assert len(revenue) == 2
    assert [fact.period_end for fact in revenue] == [
        dt.date(2026, 3, 28),  # newest quarter
        dt.date.fromisoformat(FY2025[1]),  # newest fiscal year
    ]


def test_instant_history_reaches_as_far_back_as_duration_history() -> None:
    """Balance-sheet dates have no span, so an earlier version of this
    kept the 9 most recent -- which for a filer reporting quarterly is
    barely two years, while revenue got five. The annual series has to be
    identified by the form that reported it."""
    payload = {
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            # Five fiscal year-ends, oldest first.
                            *(
                                {
                                    "end": f"20{year}-09-30",
                                    "val": year,
                                    "accn": f"0000000000-{year}-000001",
                                    "form": "10-K",
                                    "filed": f"20{year}-11-01",
                                }
                                for year in (21, 22, 23, 24, 25)
                            ),
                            # Six quarter-ends, all more recent than the
                            # older year-ends.
                            *(
                                {
                                    "end": f"2026-{month:02d}-27",
                                    "val": 900 + month,
                                    "accn": f"0000000000-26-00000{month}",
                                    "form": "10-Q",
                                    "filed": f"2026-{month:02d}-28",
                                }
                                for month in (1, 2, 3, 4, 5, 6)
                            ),
                        ]
                    }
                }
            }
        }
    }

    assets = _labelled(select_facts(payload), "Total assets")
    year_ends = {fact.period_end for fact in assets if fact.form.startswith("10-K")}

    assert year_ends == {dt.date(2000 + year, 9, 30) for year in (21, 22, 23, 24, 25)}
    # ...and the four most recent quarters are still there alongside them.
    assert len([fact for fact in assets if fact.form == "10-Q"]) == 4


def test_year_end_restated_by_a_later_10q_still_counts_as_annual() -> None:
    """A 10-Q's balance sheet carries the prior fiscal year-end as its
    comparative column. Filed later, that copy wins the restatement rule
    -- so the surviving fact says `10-Q` and the date would look
    quarterly if the annual series were read off the winner's form."""
    payload = {
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            {
                                "end": "2025-09-27",
                                "val": 100,
                                "accn": ACCN_FY2025_10K,
                                "form": "10-K",
                                "filed": "2025-10-31",
                            },
                            {
                                "end": "2025-09-27",
                                "val": 105,
                                "accn": ACCN_Q2_10Q,
                                "form": "10-Q",
                                "filed": "2026-05-01",
                            },
                        ]
                    }
                }
            }
        }
    }

    assets = _labelled(select_facts(payload, quarterly_periods=0), "Total assets")

    # quarterly_periods=0 means only the annual series can supply a fact.
    assert [fact.value for fact in assets] == [Decimal("105")]
    assert assets[0].form == "10-Q"


def test_zero_periods_yields_no_facts_but_is_not_an_error() -> None:
    result = select_facts(synthetic_company_facts(), annual_periods=0, quarterly_periods=0)
    assert result.facts == ()
    assert "Revenue" in result.missing_labels


def test_facts_are_ordered_newest_first_within_a_concept() -> None:
    revenue = _labelled(select_facts(synthetic_company_facts()), "Revenue")
    assert [fact.period_end for fact in revenue] == sorted(
        (fact.period_end for fact in revenue), reverse=True
    )


def test_concepts_are_emitted_in_allowlist_order_not_alphabetically() -> None:
    """Revenue leads, so the advisor's context reads top-line first."""
    labels = [fact.label for fact in select_facts(synthetic_company_facts()).facts]
    assert labels[0] == "Revenue"
    assert labels.index("Net income") < labels.index("Total assets")


@pytest.mark.parametrize(("annual", "quarterly"), [(-1, 4), (5, -1)])
def test_negative_period_counts_are_rejected(annual: int, quarterly: int) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        select_facts(synthetic_company_facts(), annual_periods=annual, quarterly_periods=quarterly)


# --- Absences --------------------------------------------------------------


def test_untagged_concepts_are_reported_as_missing() -> None:
    """A filer reporting no R&D is ordinary, not an error -- but the
    advisor must be told, or hard rule 2 makes it claim the *company*
    never disclosed the figure."""
    result = select_facts(synthetic_company_facts())

    assert "R&D expense" in result.missing_labels
    assert "Gross profit" in result.missing_labels
    assert all(fact.label not in result.missing_labels for fact in result.facts)


def test_concept_that_resolves_but_yields_nothing_usable_is_missing() -> None:
    """Operating cash flow is tagged, but its only entry is a six-month
    span -- so the concept exists and still contributes no fact."""
    result = select_facts(synthetic_company_facts())
    assert "Operating cash flow" in result.missing_labels
    assert _labelled(result, "Operating cash flow") == []


def test_every_allowlisted_concept_is_either_present_or_reported_missing() -> None:
    """The invariant that keeps the advisor honest: no concept may be
    silently absent from both the facts and the missing list."""
    result = select_facts(synthetic_company_facts())
    found = {fact.label for fact in result.facts}

    assert found | set(result.missing_labels) == set(ALLOWLIST_LABELS)
    assert not found & set(result.missing_labels)


def test_empty_payload_reports_everything_missing_without_raising() -> None:
    result = select_facts({})
    assert result.facts == ()
    assert result.missing_labels == ALLOWLIST_LABELS


# --- Malformed input -------------------------------------------------------


def test_malformed_entries_are_skipped_without_losing_the_concept() -> None:
    """`Liabilities` carries an unparseable date and an entry with no
    accession, alongside one good value."""
    liabilities = _labelled(select_facts(synthetic_company_facts()), "Total liabilities")

    assert [fact.value for fact in liabilities] == [Decimal("600")]
    assert all(fact.accession_number for fact in liabilities)


def test_values_are_parsed_via_string_so_float_error_never_enters_a_decimal() -> None:
    """`Decimal(0.1)` is 0.1000000000000000055...; `Decimal("0.1")` is not."""
    eps = _labelled(select_facts(synthetic_company_facts()), "EPS (diluted)")
    assert [str(fact.value) for fact in eps] == ["0.1"]
