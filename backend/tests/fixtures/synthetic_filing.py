"""Synthetic SEC EDGAR fixture data.

Fabricated content shaped like a real SEC response, not real filing
data -- CLAUDE.md forbids committing real financial data even in test
fixtures.
"""

from typing import Any

SYNTHETIC_TICKER_MAP: dict[str, dict[str, Any]] = {
    "0": {"cik_str": 320193, "ticker": "SYNT", "title": "Synthetic Test Co"},
    "1": {"cik_str": 789019, "ticker": "OTHR", "title": "Other Synthetic Co"},
}


def synthetic_submissions(cik: int = 320193) -> dict[str, Any]:
    """A submissions-feed response with one filing of each tracked form."""
    return {
        "cik": str(cik),
        "name": "Synthetic Test Co",
        "filings": {
            "recent": {
                "accessionNumber": [
                    "0000320193-24-000123",
                    "0000320193-24-000099",
                    "0000320193-23-000050",
                    "0000320193-23-000010",
                ],
                "filingDate": ["2024-11-01", "2024-08-01", "2023-11-01", "2023-02-01"],
                "form": ["10-K", "10-Q", "8-K", "S-8"],
                "primaryDocument": [
                    "synthetic-10k.htm",
                    "synthetic-10q.htm",
                    "synthetic-8k.htm",
                    "synthetic-s8.htm",
                ],
            },
            "files": [],
        },
    }


SYNTHETIC_FILING_TEXT = "<html><body>Synthetic filing text for testing only.</body></html>"
