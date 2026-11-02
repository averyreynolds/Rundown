/**
 * Mirrors backend/app/schemas/*.py. Field names are camelCased from the
 * Python snake_case; keep both sides in sync when the backend contract
 * changes (see CLAUDE.md: "update both sides in the same change").
 */

export interface SourcedValue<T> {
  value: T;
  source: string;
  asOf: string; // ISO 8601
  isStale: boolean;
}

// schemas/portfolio.py
export interface PositionView {
  symbol: string;
  accountId: string;
  quantity: number;
  costBasis: number;
  currentPrice: number;
  marketValue: number;
  allocationPct: number; // 0-100
  unrealizedPnlDollars: number;
  unrealizedPnlPercent: number | null;
}

export interface AccountSummary {
  accountId: string;
  name: string;
  institutionName: string;
  cash: number | null;
  buyingPower: number | null;
  currency: string | null;
}

// schemas/fundamentals.py
export interface FundamentalsSnapshot {
  symbol: string;
  priceToEarningsRatio: number | null;
  priceToBookRatio: number | null;
  debtToEquityRatio: number | null;
  currentRatio: number | null;
  netProfitMargin: number | null;
  returnOnEquityTtm: number | null;
  revenuePerShareTtm: number | null;
  netIncomePerShareTtm: number | null;
}

// schemas/prices.py
export type PriceWindow = "1D" | "1W" | "1M" | "3M" | "YTD" | "1Y" | "ALL";

export interface PricePoint {
  date: string; // date-only, e.g. "2024-06-14"
  close: number;
}

export interface PriceHistoryWindow {
  points: PricePoint[];
  priceChangeDollars: number | null;
  priceChangePercent: number | null;
}

// schemas/filings.py
export interface FilingMetadata {
  form: string;
  filingDate: string; // date
  accessionNumber: string;
  primaryDocument: string;
}

// schemas/news.py
export interface NewsItem {
  symbol: string;
  headline: string;
  summary: string;
  url: string;
  publisher: string;
  publishedAt: string; // ISO 8601
}

// schemas/advisor.py
export interface Citation {
  source: string;
  quote: string;
  asOf: string;
}

export interface ChatMessage {
  role: "user" | "advisor";
  text: string;
  citations?: Citation[];
}

/**
 * Frontend-only display model: PositionView plus fields no single backend
 * schema carries directly -- `name` is filled in from
 * `/portfolio/company-names` (falling back to the ticker for symbols SEC
 * doesn't recognize), `flagged`/`flagReason` are a synthesized "worth a
 * look" signal -- and the related fundamentals/news/filing this dashboard
 * cites alongside each row.
 */
export interface HoldingDetail {
  position: PositionView;
  name: string;
  flagged: boolean;
  flagReason: string | null;
  fundamentals: SourcedValue<FundamentalsSnapshot> | null;
  news: SourcedValue<NewsItem> | null;
  filing: SourcedValue<FilingMetadata> | null;
}

export type DashboardState = "ready" | "loading" | "empty" | "error" | "stale";
