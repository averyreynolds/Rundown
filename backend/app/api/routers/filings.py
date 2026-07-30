"""`GET /filings/{symbol}` and `GET /filings/{symbol}/{accession_number}` --
SEC EDGAR filing metadata and full text.

Only fetches and lists; summarization is U8's job, grounded in the exact
text this router returns via Anthropic's Citations API.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_edgar_service
from app.schemas.common import SourcedValue
from app.schemas.filings import FilingMetadata, FilingText
from app.services.edgar_service import EdgarService

router = APIRouter(prefix="/filings", tags=["filings"])


@router.get("/{symbol}", summary="Recent 10-K/10-Q/8-K filings for a symbol")
async def list_filings(
    symbol: str,
    edgar_service: Annotated[EdgarService, Depends(get_edgar_service)],
) -> SourcedValue[list[FilingMetadata]]:
    """404s if `symbol` isn't in SEC's ticker->CIK mapping."""
    return await edgar_service.list_filings(symbol)


@router.get("/{symbol}/{accession_number}", summary="Raw text of one specific filing")
async def get_filing_text(
    symbol: str,
    accession_number: str,
    edgar_service: Annotated[EdgarService, Depends(get_edgar_service)],
) -> SourcedValue[FilingText]:
    """404s if `symbol` is unknown or has no filing matching `accession_number`."""
    return await edgar_service.get_filing_text(symbol, accession_number)
