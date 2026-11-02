/**
 * Server-only typed client for the Rundown FastAPI backend. Only import
 * this from Server Components or Route Handlers -- it attaches the shared
 * bearer token from `lib/env.ts`, which must never reach the browser.
 *
 * Backend Pydantic schemas are snake_case with no camelCase alias (except
 * `fundamentals.py`); the `map*` functions below are the one place that
 * snake_case -> camelCase translation happens, matching the contract
 * documented in `lib/types.ts`.
 */

import { getRundownApiBaseUrl, getRundownApiBearerToken } from "./env";
import type {
  AccountSummary,
  Citation,
  FilingMetadata,
  FundamentalsSnapshot,
  NewsItem,
  PositionView,
  PriceHistoryWindow,
  PriceWindow,
  SourcedValue,
} from "./types";

export class RundownApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message);
    this.name = "RundownApiError";
  }
}

async function rundownFetch(path: string, init?: RequestInit): Promise<unknown> {
  let res: Response;
  try {
    res = await fetch(`${getRundownApiBaseUrl()}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${getRundownApiBearerToken()}`,
        "Content-Type": "application/json",
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch (cause) {
    throw new RundownApiError(0, `Could not reach the Rundown backend at ${getRundownApiBaseUrl()}: ${cause}`);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body && typeof body === "object" && "detail" in body ? String(body.detail) : res.statusText;
    throw new RundownApiError(res.status, detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

interface RawSourced<T> {
  value: T;
  source: string;
  as_of: string;
  is_stale: boolean;
}

function mapSourcedValue<T, R>(raw: RawSourced<T>, mapValue: (v: T) => R): SourcedValue<R> {
  return { value: mapValue(raw.value), source: raw.source, asOf: raw.as_of, isStale: raw.is_stale };
}

function mapSourcedList<T, R>(raw: RawSourced<T[]>, mapValue: (v: T) => R): SourcedValue<R[]> {
  return { value: raw.value.map(mapValue), source: raw.source, asOf: raw.as_of, isStale: raw.is_stale };
}

interface RawPositionView {
  symbol: string;
  account_id: string;
  quantity: number | string;
  cost_basis: number | string;
  current_price: number | string;
  market_value: number | string;
  allocation_pct: number | string;
  unrealized_pnl_dollars: number | string;
  unrealized_pnl_percent: number | string | null;
}

function mapPosition(raw: RawPositionView): PositionView {
  return {
    symbol: raw.symbol,
    accountId: raw.account_id,
    quantity: Number(raw.quantity),
    costBasis: Number(raw.cost_basis),
    currentPrice: Number(raw.current_price),
    marketValue: Number(raw.market_value),
    allocationPct: Number(raw.allocation_pct),
    unrealizedPnlDollars: Number(raw.unrealized_pnl_dollars),
    unrealizedPnlPercent: raw.unrealized_pnl_percent === null ? null : Number(raw.unrealized_pnl_percent),
  };
}

interface RawAccountSummary {
  account_id: string;
  name: string;
  institution_name: string;
  cash: number | string | null;
  buying_power: number | string | null;
  currency: string | null;
}

function mapAccount(raw: RawAccountSummary): AccountSummary {
  return {
    accountId: raw.account_id,
    name: raw.name,
    institutionName: raw.institution_name,
    cash: raw.cash === null ? null : Number(raw.cash),
    buyingPower: raw.buying_power === null ? null : Number(raw.buying_power),
    currency: raw.currency,
  };
}

// `FundamentalsSnapshot` is the one backend schema with `alias_generator =
// to_camel` (see backend/app/schemas/fundamentals.py), so -- unlike every
// other schema here -- it serializes camelCase over the wire already.
// `*Ttm` fields use FMP's real casing (`...TTM`) via an explicit alias.
interface RawFundamentalsSnapshot {
  symbol: string;
  priceToEarningsRatio: number | string | null;
  priceToBookRatio: number | string | null;
  debtToEquityRatio: number | string | null;
  currentRatio: number | string | null;
  netProfitMargin: number | string | null;
  returnOnEquityTTM: number | string | null;
  revenuePerShareTTM: number | string | null;
  netIncomePerShareTTM: number | string | null;
}

function toNumOrNull(v: number | string | null): number | null {
  return v === null ? null : Number(v);
}

function mapFundamentals(raw: RawFundamentalsSnapshot): FundamentalsSnapshot {
  return {
    symbol: raw.symbol,
    priceToEarningsRatio: toNumOrNull(raw.priceToEarningsRatio),
    priceToBookRatio: toNumOrNull(raw.priceToBookRatio),
    debtToEquityRatio: toNumOrNull(raw.debtToEquityRatio),
    currentRatio: toNumOrNull(raw.currentRatio),
    netProfitMargin: toNumOrNull(raw.netProfitMargin),
    returnOnEquityTtm: toNumOrNull(raw.returnOnEquityTTM),
    revenuePerShareTtm: toNumOrNull(raw.revenuePerShareTTM),
    netIncomePerShareTtm: toNumOrNull(raw.netIncomePerShareTTM),
  };
}

// `NewsItem.publisher`/`published_at` are declared with
// `Field(alias="source"/"datetime")` (backend/app/schemas/news.py) and
// FastAPI serializes by alias, so the wire keys are "source"/"datetime",
// not the Python field names.
interface RawNewsItem {
  symbol: string;
  headline: string;
  summary: string;
  url: string;
  source: string;
  datetime: string;
}

function mapNews(raw: RawNewsItem): NewsItem {
  return {
    symbol: raw.symbol,
    headline: raw.headline,
    summary: raw.summary,
    url: raw.url,
    publisher: raw.source,
    publishedAt: raw.datetime,
  };
}

interface RawFilingMetadata {
  form: string;
  filing_date: string;
  accession_number: string;
  primary_document: string;
}

function mapFiling(raw: RawFilingMetadata): FilingMetadata {
  return {
    form: raw.form,
    filingDate: raw.filing_date,
    accessionNumber: raw.accession_number,
    primaryDocument: raw.primary_document,
  };
}

export async function connectPortfolio(): Promise<{ portalUrl: string }> {
  const raw = (await rundownFetch("/portfolio/connect", { method: "POST" })) as { portal_url: string };
  return { portalUrl: raw.portal_url };
}

export async function getAccounts(): Promise<SourcedValue<AccountSummary[]>> {
  const raw = (await rundownFetch("/portfolio/accounts")) as RawSourced<RawAccountSummary[]>;
  return mapSourcedList(raw, mapAccount);
}

export async function getPositions(): Promise<SourcedValue<PositionView[]>> {
  const raw = (await rundownFetch("/portfolio/positions")) as RawSourced<RawPositionView[]>;
  return mapSourcedList(raw, mapPosition);
}

export async function getFundamentals(symbol: string): Promise<SourcedValue<FundamentalsSnapshot>> {
  const raw = (await rundownFetch(`/fundamentals/${encodeURIComponent(symbol)}`)) as RawSourced<RawFundamentalsSnapshot>;
  return mapSourcedValue(raw, mapFundamentals);
}

interface RawPriceHistoryWindow {
  points: { date: string; close: number | string }[];
  price_change_dollars: number | string | null;
  price_change_percent: number | string | null;
}

function mapPriceHistoryWindow(raw: RawPriceHistoryWindow): PriceHistoryWindow {
  return {
    points: raw.points.map((p) => ({ date: p.date, close: Number(p.close) })),
    priceChangeDollars: raw.price_change_dollars === null ? null : Number(raw.price_change_dollars),
    priceChangePercent: raw.price_change_percent === null ? null : Number(raw.price_change_percent),
  };
}

export async function getPriceHistory(
  symbol: string,
  window: PriceWindow = "ALL"
): Promise<SourcedValue<PriceHistoryWindow>> {
  const raw = (await rundownFetch(
    `/fundamentals/${encodeURIComponent(symbol)}/price-history?window=${window}`
  )) as RawSourced<RawPriceHistoryWindow>;
  return mapSourcedValue(raw, mapPriceHistoryWindow);
}

export async function getNewsForSymbols(symbols: string[]): Promise<SourcedValue<NewsItem[]>> {
  const params = new URLSearchParams();
  for (const symbol of symbols) params.append("symbols", symbol);
  const raw = (await rundownFetch(`/news?${params.toString()}`)) as RawSourced<RawNewsItem[]>;
  return mapSourcedList(raw, mapNews);
}

/**
 * Best-effort `{symbol: companyName}` from SEC's ticker map. Not wrapped in
 * `SourcedValue` -- the backend deliberately doesn't track staleness for
 * this lookup (a registered company name effectively never changes) --
 * and a symbol absent from SEC's mapping (an ETF, a non-US listing) is
 * simply missing from the returned map, not an error.
 */
export async function getCompanyNames(symbols: string[]): Promise<Record<string, string>> {
  const params = new URLSearchParams();
  for (const symbol of symbols) params.append("symbols", symbol);
  return (await rundownFetch(`/portfolio/company-names?${params.toString()}`)) as Record<string, string>;
}

export async function getLatestFiling(symbol: string): Promise<SourcedValue<FilingMetadata> | null> {
  const raw = (await rundownFetch(`/filings/${encodeURIComponent(symbol)}`)) as RawSourced<RawFilingMetadata[]>;
  const latest = raw.value[0];
  if (latest === undefined) return null;
  return mapSourcedValue({ ...raw, value: latest }, mapFiling);
}

export interface AdvisorFilingRef {
  symbol: string;
  accessionNumber: string;
}

export interface AdvisorChatInput {
  question: string;
  symbols?: string[];
  filingRef?: AdvisorFilingRef;
}

export interface AdvisorChatResult {
  answer: string;
  citations: Citation[];
}

interface RawCitation {
  source: string;
  quote: string;
  as_of: string;
}

export async function postAdvisorChat(input: AdvisorChatInput): Promise<AdvisorChatResult> {
  const raw = (await rundownFetch("/advisor/chat", {
    method: "POST",
    body: JSON.stringify({
      question: input.question,
      context_refs: {
        symbols: input.symbols ?? [],
        filing_ref: input.filingRef
          ? { symbol: input.filingRef.symbol, accession_number: input.filingRef.accessionNumber }
          : null,
      },
    }),
  })) as { answer: string; citations: RawCitation[] };

  return {
    answer: raw.answer,
    citations: raw.citations.map((c) => ({ source: c.source, quote: c.quote, asOf: c.as_of })),
  };
}
