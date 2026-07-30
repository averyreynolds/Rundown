"""One module per third-party integration (SnapTrade, FMP, EDGAR, Finnhub,
Anthropic), plus the shared exception types and cache-through helper every
provider service builds on.

Route handlers stay thin; orchestration and provider-specific logic live
here, never in `api/routers/`.
"""
