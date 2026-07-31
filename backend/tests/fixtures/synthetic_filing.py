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


def synthetic_10k_html(*, risk_body: str = "", mdna_body: str = "") -> str:
    """A 10-K shaped like a real inline-XBRL filing, with all the usual hazards.

    Deliberately includes every pattern the extractor has to survive:
    a table of contents that repeats every Item heading, an `<ix:header>`
    hidden-fact block, a `display:none` span, `<font>`-wrapped headings
    with em-dash separators, a financial table, inline `<ix:nonFraction>`
    tags splitting a number out of the middle of a sentence, and a
    trailing cross-reference that mentions an Item number in prose.

    Fabricated content, not real filing data (CLAUDE.md hard rule 5).
    """
    risk_body = risk_body or (
        "Our synthetic operations depend on a single fabricated supplier. "
        "A disruption there would reduce revenue materially."
    )
    mdna_body = mdna_body or (
        "Revenue increased to $1,234 million in fiscal 2024 from $1,100 million "
        "in fiscal 2023, driven entirely by imaginary demand."
    )
    return f"""<html>
<head><style>.hidden {{ display:none; }}</style>
<script>trackPageView();</script></head>
<body>
<ix:header><ix:hidden><ix:nonFraction contextRef="c-1" unitRef="usd">99999
</ix:nonFraction></ix:hidden></ix:header>
<span style="display:none">XBRL-ONLY-FACT-DO-NOT-SURFACE</span>

<div><b>TABLE OF CONTENTS</b></div>
<table>
<tr><td>Item 1.</td><td>Business</td><td>3</td></tr>
<tr><td>Item 1A.</td><td>Risk Factors</td><td>9</td></tr>
<tr><td>Item 3.</td><td>Legal Proceedings</td><td>21</td></tr>
<tr><td>Item 5.</td><td>Market for Registrant's Common Equity</td><td>24</td></tr>
<tr><td>Item 7.</td><td>Management's Discussion and Analysis</td><td>28</td></tr>
<tr><td>Item 7A.</td><td>Quantitative and Qualitative Disclosures</td>
<td>44</td></tr>
<tr><td>Item 8.</td><td>Financial Statements and Supplementary Data</td><td>47</td></tr>
</table>

<p><font size="3"><b>PART I</b></font></p>
<p><font size="3"><b>Item 1&#160;&#8212;&#160;Business</b></font></p>
<p>Synthetic Test Co fabricates test data. This section is long and static and
the extractor is expected to leave it out of the advisor's excerpt.</p>

<p><font size="3"><b>Item 1A. Risk Factors</b></font></p>
<p>{risk_body}</p>

<p><font size="3"><b>Item 3. Legal Proceedings</b></font></p>
<p>We are party to one fabricated proceeding arising in the ordinary course.</p>

<p><b>PART II</b></p>
<p><font size="3"><b>Item 5: Market for Registrant's Common Equity</b></font></p>
<p>We repurchased 1,000 synthetic shares and declared a $0.25 quarterly dividend.</p>

<p><font size="3"><b>ITEM 7 - MANAGEMENT'S DISCUSSION AND ANALYSIS</b></font></p>
<p>{mdna_body}</p>
<table>
<tr><th>Metric</th><th>2024</th><th>2023</th></tr>
<tr><td>Revenue</td><td>$1,234</td><td>$1,100</td></tr>
</table>
<p>Segment margin was <ix:nonFraction contextRef="c-2">42</ix:nonFraction>% for the year.</p>

<p><font size="3"><b>Item 7A. Quantitative and Qualitative Disclosures About
Market Risk</b></font></p>
<p>A hypothetical 100 basis point move would change fabricated interest expense
by $4 million.</p>

<p><font size="3"><b>Item 8. Financial Statements and Supplementary Data</b></font></p>
<p>Item 8 of this Annual Report contains the audited synthetic financial
statements, which the extractor is expected to leave out of the excerpt.</p>
</body></html>"""


def synthetic_10q_html() -> str:
    """A 10-Q, where Item numbers repeat across Part I and Part II.

    "Item 1" is Financial Statements in Part I and Legal Proceedings in
    Part II -- the case that makes Part anchoring mandatory rather than
    a nicety.
    """
    return """<html><body>
<div>PART I &#8212; FINANCIAL INFORMATION</div>
<div>Item 1. Financial Statements</div>
<div>Condensed consolidated synthetic balance sheets follow. Excluded by policy.</div>
<div>Item 2. Management's Discussion and Analysis of Financial Condition</div>
<div>Quarterly synthetic revenue rose to $312 million on fabricated volume growth.</div>
<div>Item 3. Quantitative and Qualitative Disclosures About Market Risk</div>
<div>There have been no material changes to our fabricated market risk exposures.</div>
<div>Item 4. Controls and Procedures</div>
<div>Disclosure controls were effective. Excluded by policy.</div>
<div>PART II &#8212; OTHER INFORMATION</div>
<div>Item 1. Legal Proceedings</div>
<div>No new fabricated proceedings arose during the quarter just ended.</div>
<div>Item 1A. Risk Factors</div>
<div>There have been no material changes from the risk factors previously
disclosed in our synthetic Annual Report on Form 10-K.</div>
<div>Item 6. Exhibits</div>
<div>Exhibit index. Excluded by policy.</div>
</body></html>"""


SYNTHETIC_8K_HTML = """<html><body>
<div>Item 2.02 Results of Operations and Financial Condition.</div>
<div>On November 1, 2024, Synthetic Test Co issued a press release announcing
fabricated results for the quarter ended September 30, 2024.</div>
</body></html>"""

# Pre-2001 EDGAR filings are plain ASCII with no markup at all.
SYNTHETIC_PLAIN_TEXT_10K = """\
ITEM 1A. RISK FACTORS

Our fabricated business is subject to synthetic risks that could reduce revenue.

ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION

Fabricated revenue for the year was $500 million, up from $450 million.
"""
