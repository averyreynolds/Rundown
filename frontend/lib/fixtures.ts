import type { AccountSummary, HoldingDetail, PositionView } from "./types";

/**
 * Synthetic development fixtures standing in for the live backend
 * (SnapTrade/FMP/EDGAR/Finnhub via FastAPI). No real account, holding,
 * or filing data -- see CLAUDE.md hard rule 5. Tickers are real public
 * companies; every quantity, price, and figure below is invented.
 *
 * `PositionView` has no company-name field, so `name` here is a
 * frontend-only addition -- the real backend contract still needs a
 * name source (fundamentals, or a static reference table) before this
 * can come from a live fetch.
 */

const POSITIONS_AS_OF = "2026-07-30T13:05:00Z";
const STALE_AS_OF = "2026-07-28T09:40:00Z";

/** The page's simulated "current time" -- there is no live clock behind this demo build. */
export const DEMO_NOW = "2026-07-30T13:20:00Z";

function position(p: PositionView): PositionView {
  return p;
}

const RAW_POSITIONS: PositionView[] = [
  position({
    symbol: "AAPL",
    accountId: "demo-001",
    quantity: 42,
    costBasis: 7830.0,
    currentPrice: 227.5,
    marketValue: 9555.0,
    allocationPct: 15.37,
    unrealizedPnlDollars: 1725.0,
    unrealizedPnlPercent: 22.03,
  }),
  position({
    symbol: "MSFT",
    accountId: "demo-001",
    quantity: 18,
    costBasis: 6120.0,
    currentPrice: 468.2,
    marketValue: 8427.6,
    allocationPct: 13.56,
    unrealizedPnlDollars: 2307.6,
    unrealizedPnlPercent: 37.71,
  }),
  position({
    symbol: "NVDA",
    accountId: "demo-001",
    quantity: 55,
    costBasis: 4400.0,
    currentPrice: 148.3,
    marketValue: 8156.5,
    allocationPct: 13.12,
    unrealizedPnlDollars: 3756.5,
    unrealizedPnlPercent: 85.37,
  }),
  position({
    symbol: "AMZN",
    accountId: "demo-001",
    quantity: 30,
    costBasis: 6900.0,
    currentPrice: 231.1,
    marketValue: 6933.0,
    allocationPct: 11.15,
    unrealizedPnlDollars: 33.0,
    unrealizedPnlPercent: 0.48,
  }),
  position({
    symbol: "GOOGL",
    accountId: "demo-001",
    quantity: 25,
    costBasis: 4250.0,
    currentPrice: 196.4,
    marketValue: 4910.0,
    allocationPct: 7.9,
    unrealizedPnlDollars: 660.0,
    unrealizedPnlPercent: 15.53,
  }),
  position({
    symbol: "JPM",
    accountId: "demo-001",
    quantity: 20,
    costBasis: 4820.0,
    currentPrice: 268.9,
    marketValue: 5378.0,
    allocationPct: 8.65,
    unrealizedPnlDollars: 558.0,
    unrealizedPnlPercent: 11.58,
  }),
  position({
    symbol: "BRK.B",
    accountId: "demo-001",
    quantity: 10,
    costBasis: 4550.0,
    currentPrice: 468.75,
    marketValue: 4687.5,
    allocationPct: 7.54,
    unrealizedPnlDollars: 137.5,
    unrealizedPnlPercent: 3.02,
  }),
  position({
    symbol: "XOM",
    accountId: "demo-001",
    quantity: 35,
    costBasis: 4550.0,
    currentPrice: 121.6,
    marketValue: 4256.0,
    allocationPct: 6.85,
    unrealizedPnlDollars: -294.0,
    unrealizedPnlPercent: -6.46,
  }),
  position({
    symbol: "VTI",
    accountId: "demo-001",
    quantity: 12,
    costBasis: 3450.0,
    currentPrice: 312.4,
    marketValue: 3748.8,
    allocationPct: 6.03,
    unrealizedPnlDollars: 298.8,
    unrealizedPnlPercent: 8.66,
  }),
  position({
    symbol: "SCHD",
    accountId: "demo-001",
    quantity: 40,
    costBasis: 3120.0,
    currentPrice: 84.2,
    marketValue: 3368.0,
    allocationPct: 5.42,
    unrealizedPnlDollars: 248.0,
    unrealizedPnlPercent: 7.95,
  }),
  position({
    symbol: "UNH",
    accountId: "demo-001",
    quantity: 8,
    costBasis: 3960.0,
    currentPrice: 342.1,
    marketValue: 2736.8,
    allocationPct: 4.4,
    unrealizedPnlDollars: -1223.2,
    unrealizedPnlPercent: -30.89,
  }),
];

const NAMES: Record<string, string> = {
  AAPL: "Apple Inc.",
  MSFT: "Microsoft Corp.",
  NVDA: "NVIDIA Corp.",
  AMZN: "Amazon.com Inc.",
  GOOGL: "Alphabet Inc. (Class A)",
  JPM: "JPMorgan Chase & Co.",
  "BRK.B": "Berkshire Hathaway (Class B)",
  XOM: "Exxon Mobil Corp.",
  VTI: "Vanguard Total Stock Market ETF",
  SCHD: "Schwab U.S. Dividend Equity ETF",
  UNH: "UnitedHealth Group Inc.",
};

const FLAGS: Record<string, string> = {
  NVDA: "That gain has made it your third-largest position — allocation has drifted well past where it started.",
  XOM: "Filed a 10-Q on Jul 28 that hasn't been reviewed yet.",
  UNH: "Down 31% since cost basis, alongside a guidance-cut headline this week.",
};

function withStaleness(asOf: string, stale: boolean): { asOf: string; isStale: boolean } {
  return stale ? { asOf: STALE_AS_OF, isStale: true } : { asOf, isStale: false };
}

export function getHoldings(): HoldingDetail[] {
  return RAW_POSITIONS.map((pos) => {
    const flagReason = FLAGS[pos.symbol] ?? null;

    const fundamentals =
      pos.symbol === "NVDA"
        ? {
            symbol: "NVDA",
            priceToEarningsRatio: 45.2,
            priceToBookRatio: 38.6,
            debtToEquityRatio: 0.14,
            currentRatio: 3.5,
            netProfitMargin: 0.52,
            returnOnEquityTtm: 0.91,
            revenuePerShareTtm: 4.82,
            netIncomePerShareTtm: 2.51,
          }
        : null;

    const news =
      pos.symbol === "UNH"
        ? {
            symbol: "UNH",
            headline: "UnitedHealth cuts full-year guidance, citing elevated medical costs",
            summary:
              "The insurer lowered its 2026 earnings outlook, pointing to higher-than-expected medical-cost trends in its Medicare Advantage business.",
            url: "https://example.com/news/unh-guidance-cut",
            publisher: "Reuters",
            publishedAt: "2026-07-24T12:31:00Z",
          }
        : null;

    const filing =
      pos.symbol === "XOM"
        ? {
            form: "10-Q",
            filingDate: "2026-07-28",
            accessionNumber: "0000034088-26-000045",
            primaryDocument: "xom-20260630.htm",
          }
        : null;

    return {
      position: pos,
      name: NAMES[pos.symbol] ?? pos.symbol,
      flagged: flagReason !== null,
      flagReason,
      fundamentals: fundamentals
        ? { value: fundamentals, source: "Financial Modeling Prep", asOf: "2026-07-29T06:00:00Z", isStale: false }
        : null,
      news: news ? { value: news, source: "Finnhub", asOf: "2026-07-30T06:00:00Z", isStale: false } : null,
      filing: filing ? { value: filing, source: "SEC EDGAR", asOf: "2026-07-30T06:00:00Z", isStale: false } : null,
    } satisfies HoldingDetail;
  });
}

export function getPositionsFreshness(stale = false): { asOf: string; source: string; isStale: boolean } {
  const { asOf, isStale } = withStaleness(POSITIONS_AS_OF, stale);
  return { asOf, isStale, source: "SnapTrade" };
}

export const ACCOUNT: AccountSummary = {
  accountId: "demo-001",
  name: "Individual Taxable — Demo",
  institutionName: "Charles Schwab",
  cash: 1842.55,
  buyingPower: 1842.55,
  currency: "USD",
};

export function getPortfolioTotals(holdings: HoldingDetail[]) {
  const marketValue = holdings.reduce((sum, h) => sum + h.position.marketValue, 0);
  const costBasis = holdings.reduce((sum, h) => sum + h.position.costBasis, 0);
  const unrealizedPnlDollars = marketValue - costBasis;
  const unrealizedPnlPercent = costBasis === 0 ? 0 : (unrealizedPnlDollars / costBasis) * 100;
  const totalValue = marketValue + (ACCOUNT.cash ?? 0);

  return { marketValue, costBasis, unrealizedPnlDollars, unrealizedPnlPercent, totalValue };
}
