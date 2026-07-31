"""Synthetic SEC XBRL `companyfacts` fixture data.

Fabricated values shaped like a real `companyfacts` response, not real
filing data -- CLAUDE.md forbids committing real financial data even in
fixtures.

The fiscal calendar here ends in late September and runs 363-day years,
because that's the shape that actually stresses the selection rules: a
52/53-week retail-style calendar is why the annual span window is a range
rather than "365 days". Each call returns a fresh dict, so a test can
mutate its copy freely.
"""

from typing import Any

# Fabricated accession numbers, in the real 10-2-6 digit shape so the
# deterministic tiebreak in `_latest_filed` is exercised on realistic
# strings.
ACCN_FY2024_10K = "0000000000-24-000001"
ACCN_FY2025_10K = "0000000000-25-000001"
ACCN_Q1_10Q = "0000000000-26-000001"
ACCN_Q2_10Q = "0000000000-26-000002"

# Fiscal year boundaries used throughout.
FY2023 = ("2022-10-02", "2023-09-30")
FY2024 = ("2023-10-01", "2024-09-28")
FY2025 = ("2024-09-29", "2025-09-27")

# Q1 and Q2 of FY2026, plus the six-month year-to-date span that shares
# Q2's `end` date and must be discarded.
Q1_FY2026 = ("2025-09-28", "2025-12-27")
Q2_FY2026 = ("2025-12-28", "2026-03-28")
H1_FY2026 = ("2025-09-28", "2026-03-28")


def _duration(
    period: tuple[str, str],
    val: float | int,
    *,
    accn: str,
    form: str,
    filed: str,
    fy: int | None = None,
    fp: str | None = None,
) -> dict[str, Any]:
    start, end = period
    entry: dict[str, Any] = {
        "start": start,
        "end": end,
        "val": val,
        "accn": accn,
        "form": form,
        "filed": filed,
    }
    if fy is not None:
        entry["fy"] = fy
    if fp is not None:
        entry["fp"] = fp
    return entry


def _instant(end: str, val: float | int, *, accn: str, form: str, filed: str) -> dict[str, Any]:
    return {"end": end, "val": val, "accn": accn, "form": form, "filed": filed}


def synthetic_company_facts() -> dict[str, Any]:
    """A `companyfacts` payload exercising every selection rule at once.

    Deliberately *not* a well-behaved document. It contains a filer who
    tags revenue with the generic `Revenues` rather than the preferred
    ASC-606 concept, a prior-year figure restated by a later filing, a
    year-to-date duration that shares an `end` with a real quarter, two
    malformed entries, a value under a currency unit nobody asked for, a
    concept whose only entry is unusable, and a `dei` cover-page fact.
    """
    return {
        "cik": 1234567,
        "entityName": "Synthetic Test Co",
        "facts": {
            "us-gaap": {
                # Chain position 3: this filer skips both ASC-606 concepts.
                "Revenues": {
                    "units": {
                        "USD": [
                            # FY2023, as first reported in the FY2024 10-K
                            # as the prior-year comparative.
                            _duration(
                                FY2023,
                                300,
                                accn=ACCN_FY2024_10K,
                                form="10-K",
                                filed="2024-11-01",
                                fy=2024,
                                fp="FY",
                            ),
                            _duration(
                                FY2024,
                                400,
                                accn=ACCN_FY2024_10K,
                                form="10-K",
                                filed="2024-11-01",
                                fy=2024,
                                fp="FY",
                            ),
                            # The FY2025 10-K restates FY2024 upward. Latest
                            # filed must win, and must carry *this*
                            # accession -- the filing that reported 410.
                            _duration(
                                FY2024,
                                410,
                                accn=ACCN_FY2025_10K,
                                form="10-K",
                                filed="2025-10-31",
                                fy=2025,
                                fp="FY",
                            ),
                            _duration(
                                FY2025,
                                500,
                                accn=ACCN_FY2025_10K,
                                form="10-K",
                                filed="2025-10-31",
                                fy=2025,
                                fp="FY",
                            ),
                            _duration(
                                Q1_FY2026,
                                140,
                                accn=ACCN_Q1_10Q,
                                form="10-Q",
                                filed="2026-02-01",
                                fy=2026,
                                fp="Q1",
                            ),
                            _duration(
                                Q2_FY2026,
                                130,
                                accn=ACCN_Q2_10Q,
                                form="10-Q",
                                filed="2026-05-01",
                                fy=2026,
                                fp="Q2",
                            ),
                            # Six-month year-to-date: same `end` as Q2,
                            # different `start`. Must be dropped, or a
                            # 182-day figure sits beside a 91-day one.
                            _duration(
                                H1_FY2026,
                                270,
                                accn=ACCN_Q2_10Q,
                                form="10-Q",
                                filed="2026-05-01",
                                fy=2026,
                                fp="Q2",
                            ),
                        ],
                        # A unit the allowlist never asks for.
                        "CAD": [
                            _duration(
                                FY2025,
                                999_999,
                                accn=ACCN_FY2025_10K,
                                form="10-K",
                                filed="2025-10-31",
                            ),
                        ],
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            _duration(
                                FY2025,
                                90,
                                accn=ACCN_FY2025_10K,
                                form="10-K",
                                filed="2025-10-31",
                                fy=2025,
                                fp="FY",
                            ),
                        ]
                    }
                },
                # Per-share values live under `USD/shares`, not `USD`.
                "EarningsPerShareDiluted": {
                    "units": {
                        "USD/shares": [
                            _duration(
                                FY2025,
                                0.1,
                                accn=ACCN_FY2025_10K,
                                form="10-K",
                                filed="2025-10-31",
                                fy=2025,
                                fp="FY",
                            ),
                        ]
                    }
                },
                "Assets": {
                    "units": {
                        "USD": [
                            _instant(
                                FY2024[1],
                                1_000,
                                accn=ACCN_FY2024_10K,
                                form="10-K",
                                filed="2024-11-01",
                            ),
                            # Same balance-sheet date, restated later.
                            _instant(
                                FY2024[1],
                                1_010,
                                accn=ACCN_FY2025_10K,
                                form="10-K",
                                filed="2025-10-31",
                            ),
                            _instant(
                                FY2025[1],
                                1_100,
                                accn=ACCN_FY2025_10K,
                                form="10-K",
                                filed="2025-10-31",
                            ),
                        ]
                    }
                },
                "Liabilities": {
                    "units": {
                        "USD": [
                            # Unparseable date, and a missing accession:
                            # one bad entry should cost one data point,
                            # not the whole concept.
                            {
                                "end": "not-a-date",
                                "val": 1,
                                "accn": ACCN_FY2025_10K,
                                "form": "10-K",
                                "filed": "2025-10-31",
                            },
                            {
                                "end": FY2023[1],
                                "val": 2,
                                "form": "10-K",
                                "filed": "2024-11-01",
                            },
                            _instant(
                                FY2025[1],
                                600,
                                accn=ACCN_FY2025_10K,
                                form="10-K",
                                filed="2025-10-31",
                            ),
                        ]
                    }
                },
                # Chain position 2 for shareholders' equity: the preferred
                # `StockholdersEquity` is absent.
                "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": {
                    "units": {
                        "USD": [
                            _instant(
                                FY2025[1],
                                500,
                                accn=ACCN_FY2025_10K,
                                form="10-K",
                                filed="2025-10-31",
                            ),
                        ]
                    }
                },
                # Resolves, but its only entry is a six-month span -- so
                # the concept is present and still yields nothing usable.
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {
                        "USD": [
                            _duration(
                                H1_FY2026,
                                75,
                                accn=ACCN_Q2_10Q,
                                form="10-Q",
                                filed="2026-05-01",
                            ),
                        ]
                    }
                },
            },
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            _instant(
                                FY2025[1],
                                15_000_000,
                                accn=ACCN_FY2025_10K,
                                form="10-K",
                                filed="2025-10-31",
                            ),
                        ]
                    }
                }
            },
        },
    }
