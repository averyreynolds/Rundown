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
 * Frontend-only display model: PositionView plus the fields no backend
 * schema currently carries (company name, a synthesized "worth a look"
 * flag) and the related fundamentals/news/filing this dashboard cites
 * alongside each row. Real integration still needs a company-name
 * source -- see the summary note in the surface brief.
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
