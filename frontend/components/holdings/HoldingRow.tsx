"use client";

import { useId, useState } from "react";
import { PnlValue } from "../PnlValue";
import { StatusChip } from "../StatusChip";
import { useAdvisor } from "../advisor/AdvisorProvider";
import { formatAsOf, formatCurrency, formatDate, formatPercent } from "@/lib/format";
import type { HoldingDetail } from "@/lib/types";

export function HoldingRow({ holding }: { holding: HoldingDetail }) {
  const [expanded, setExpanded] = useState(false);
  const { open } = useAdvisor();
  const panelId = useId();
  const { position, name, flagged, flagReason, fundamentals, news, filing } = holding;

  return (
    <li className="border-b border-border last:border-b-0">
      <button
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-controls={panelId}
        className="grid w-full grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 px-1 py-4 text-left transition-colors hover:bg-paper/60 sm:grid-cols-[minmax(0,2fr)_minmax(88px,1fr)_minmax(150px,1fr)] sm:gap-x-6"
      >
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-paper text-xs font-semibold text-ink-secondary">
            {position.symbol.slice(0, 2)}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="truncate text-sm font-medium text-ink">{position.symbol}</p>
              {flagged && <StatusChip tone="flag">Worth a look</StatusChip>}
            </div>
            <p className="truncate text-xs text-ink-faint">{name}</p>
          </div>
        </div>

        <div className="col-start-2 row-start-1 text-right sm:col-start-2 sm:text-right">
          <p className="tabular-nums text-sm font-medium text-ink">{formatCurrency(position.marketValue)}</p>
          <p className="tabular-nums text-xs text-ink-faint">{formatPercent(position.allocationPct, 1)}</p>
        </div>

        <div className="col-span-2 row-start-2 sm:col-span-1 sm:col-start-3 sm:row-start-1 sm:text-right">
          <PnlValue dollars={position.unrealizedPnlDollars} percent={position.unrealizedPnlPercent} />
        </div>
      </button>

      {expanded && (
        <div id={panelId} className="grid gap-4 px-1 pb-5 pt-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] sm:gap-6">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <div>
              <dt className="text-xs text-ink-faint">Quantity</dt>
              <dd className="tabular-nums text-ink">{position.quantity}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-faint">Current price</dt>
              <dd className="tabular-nums text-ink">{formatCurrency(position.currentPrice)}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-faint">Cost basis</dt>
              <dd className="tabular-nums text-ink">{formatCurrency(position.costBasis)}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-faint">Account</dt>
              <dd className="text-ink">{position.accountId}</dd>
            </div>
          </dl>

          <div className="space-y-3">
            {flagReason && <p className="text-sm leading-relaxed text-ink-secondary">{flagReason}</p>}

            {fundamentals && (
              <div className="rounded-lg border border-border bg-paper px-3.5 py-3">
                <p className="text-xs font-medium text-ink-secondary">Fundamentals</p>
                <p className="mt-1 text-sm text-ink">
                  P/E {fundamentals.value.priceToEarningsRatio?.toFixed(1)} · ROE (TTM){" "}
                  {((fundamentals.value.returnOnEquityTtm ?? 0) * 100).toFixed(0)}% · Net margin{" "}
                  {((fundamentals.value.netProfitMargin ?? 0) * 100).toFixed(0)}%
                </p>
                <p className="mt-1.5 text-xs text-ink-faint">
                  {fundamentals.source} · as of {formatAsOf(fundamentals.asOf)}
                </p>
              </div>
            )}

            {news && (
              <a
                href={news.value.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded-lg border border-border bg-paper px-3.5 py-3 transition-colors hover:border-border-strong"
              >
                <p className="text-xs font-medium text-ink-secondary">Recent news</p>
                <p className="mt-1 text-sm text-ink">{news.value.headline}</p>
                <p className="mt-1.5 text-xs text-ink-faint">
                  {news.value.publisher} · {formatAsOf(news.value.publishedAt)} · via {news.source}
                </p>
              </a>
            )}

            {filing && (
              <div className="rounded-lg border border-border bg-paper px-3.5 py-3">
                <p className="text-xs font-medium text-ink-secondary">Filing</p>
                <p className="mt-1 text-sm text-ink">
                  {filing.value.form} filed {formatDate(filing.value.filingDate)}
                </p>
                <p className="mt-1.5 font-mono text-xs text-ink-faint">{filing.value.accessionNumber}</p>
                <p className="mt-1 text-xs text-ink-faint">
                  {filing.source} · as of {formatAsOf(filing.asOf)}
                </p>
              </div>
            )}

            <button
              onClick={() => open(position.symbol)}
              className="text-sm font-medium text-accent-ink hover:underline"
            >
              Ask about this position →
            </button>
          </div>
        </div>
      )}
    </li>
  );
}
