/**
 * Server-only assembly of the dashboard's real data from the backend.
 * Fundamentals/news/filing enrichment is best-effort per holding: a
 * failure on any one of those (e.g. a placeholder FMP/Finnhub/EDGAR key
 * in dev) degrades that holding's card to "not available" rather than
 * failing the whole page -- only the core positions/accounts fetch is
 * load-bearing for the dashboard actually rendering.
 */

import {
  RundownApiError,
  getAccounts,
  getCompanyNames,
  getFundamentals,
  getLatestFiling,
  getNewsForSymbols,
  getPositions,
} from "./rundown-api";
import type { AccountSummary, HoldingDetail, PositionView } from "./types";

export interface DashboardTotals {
  totalValue: number;
  marketValue: number;
  costBasis: number;
  unrealizedPnlDollars: number;
  unrealizedPnlPercent: number;
}

export interface DashboardFreshness {
  asOf: string;
  source: string;
  isStale: boolean;
}

export type DashboardResult =
  | { kind: "ready"; account: AccountSummary; holdings: HoldingDetail[]; totals: DashboardTotals; freshness: DashboardFreshness }
  | { kind: "empty" }
  | { kind: "error"; message: string };

export async function loadDashboard(): Promise<DashboardResult> {
  let positionsResult;
  let accountsResult;
  try {
    [positionsResult, accountsResult] = await Promise.all([getPositions(), getAccounts()]);
  } catch (err) {
    if (err instanceof RundownApiError && err.status === 409) return { kind: "empty" };
    return { kind: "error", message: err instanceof Error ? err.message : "Unknown error" };
  }

  const account = accountsResult.value[0];
  if (!account) return { kind: "empty" };

  const positions = positionsResult.value;
  const symbols = positions.map((p) => p.symbol);

  const [newsResult, companyNames, enriched] = await Promise.all([
    symbols.length > 0 ? getNewsForSymbols(symbols).catch(() => null) : Promise.resolve(null),
    symbols.length > 0
      ? getCompanyNames(symbols).catch((): Record<string, string> => ({}))
      : Promise.resolve<Record<string, string>>({}),
    Promise.all(positions.map(enrichHolding)),
  ]);

  const newsBySymbol = new Map(newsResult?.value.map((item) => [item.symbol, item]) ?? []);

  const holdings: HoldingDetail[] = enriched.map((partial) => {
    const item = newsBySymbol.get(partial.position.symbol);
    return {
      ...partial,
      name: companyNames[partial.position.symbol] ?? partial.name,
      news: item && newsResult ? { value: item, source: newsResult.source, asOf: newsResult.asOf, isStale: newsResult.isStale } : null,
    };
  });

  const marketValue = positions.reduce((sum, p) => sum + p.marketValue, 0);
  const costBasis = positions.reduce((sum, p) => sum + p.costBasis, 0);
  const unrealizedPnlDollars = marketValue - costBasis;
  const unrealizedPnlPercent = costBasis === 0 ? 0 : (unrealizedPnlDollars / costBasis) * 100;
  const totalValue = marketValue + (account.cash ?? 0);

  return {
    kind: "ready",
    account,
    holdings,
    totals: { totalValue, marketValue, costBasis, unrealizedPnlDollars, unrealizedPnlPercent },
    freshness: { asOf: positionsResult.asOf, source: positionsResult.source, isStale: positionsResult.isStale },
  };
}

type HoldingWithoutNews = Omit<HoldingDetail, "news">;

async function enrichHolding(position: PositionView): Promise<HoldingWithoutNews> {
  const [fundamentals, filing] = await Promise.all([
    getFundamentals(position.symbol).catch(() => null),
    getLatestFiling(position.symbol).catch(() => null),
  ]);

  return {
    position,
    // Overwritten below with the real company name where `/portfolio/company-names`
    // has one; a symbol it can't resolve (an ETF, a non-US listing) keeps this fallback.
    name: position.symbol,
    // No backend "worth a look" signal exists yet either -- see README.
    flagged: false,
    flagReason: null,
    fundamentals,
    filing,
  };
}
