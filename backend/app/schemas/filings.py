"""Response schemas for `GET /filings/{symbol}` and
`GET /filings/{symbol}/{accession_number}`."""

from datetime import date

from pydantic import BaseModel


class FilingMetadata(BaseModel):
    """One filing's metadata, as listed in SEC EDGAR's submissions feed."""

    form: str
    filing_date: date
    accession_number: str
    primary_document: str


class FilingText(BaseModel):
    """Raw text/HTML of one specific filing document.

    Deliberately un-summarized: this unit only fetches, per the plan --
    U8's advisor does the summarizing, grounded in this exact text via
    Anthropic's Citations API.
    """

    accession_number: str
    form: str
    text: str
