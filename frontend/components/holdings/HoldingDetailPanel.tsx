"use client";

import { useEffect } from "react";
import { PnlValue } from "../PnlValue";
import { StatusChip } from "../StatusChip";
import { useWorkspace } from "../workspace/WorkspaceProvider";
import { CostBasisBar } from "./CostBasisBar";
import { PositionChart } from "./PositionChart";
import { formatAsOf, formatCurrency, formatDate, formatPercent } from "@/lib/format";
import type { HoldingDetail } from "@/lib/types";

function PanelHeader({ holding, onClose }: { holding: HoldingDetail; onClose: () => void }) {
  return (
    <div className="flex items-center justify-between border-b border-border px-5 py-4">
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-ink">{holding.position.symbol}</p>
        <p className="truncate text-xs text-ink-faint">{holding.name}</p>
      </div>
      <button onClick={onClose} aria-label="Close" className="rounded-full p-1.5 text-ink-secondary hover:bg-paper hover:text-ink">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
          <path d="M3 3L13 13M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
    </div>
  );
}

function HoldingDetailContent({ holding }: { holding: HoldingDetail }) {
  const { ask, clearSelection } = useWorkspace();
  const { position, flagged, flagReason, fundamentals, news, filing } = holding;

  const costBasisPerShare = position.quantity !== 0 ? position.costBasis / position.quantity : position.currentPrice;

  return (
    <div className="space-y-5">
      <div>
        <p className="text-xs text-ink-faint">Market value</p>
        <div className="mt-0.5 flex items-baseline gap-2.5">
          <p className="text-2xl font-semibold tabular-nums text-ink">{formatCurrency(position.marketValue)}</p>
          <PnlValue dollars={position.unrealizedPnlDollars} percent={position.unrealizedPnlPercent} size="md" />
        </div>
        <p className="mt-0.5 text-xs text-ink-faint">since purchase</p>
      </div>

      <CostBasisBar costBasisPerShare={costBasisPerShare} currentPrice={position.currentPrice} />

      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <div>
          <dt className="text-xs text-ink-faint">Quantity</dt>
          <dd className="tabular-nums text-ink">{position.quantity}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-faint">Allocation</dt>
          <dd className="tabular-nums text-ink">{formatPercent(position.allocationPct, 1)}</dd>
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

      <div className="rounded-lg border border-border bg-paper px-3.5 py-3">
        <PositionChart key={position.symbol} symbol={position.symbol} quantity={position.quantity} costBasisPerShare={costBasisPerShare} />
      </div>

      {flagged && flagReason && (
        <div className="rounded-lg border border-accent-soft bg-accent-soft/60 px-3.5 py-3">
          <p className="text-xs font-medium text-accent-ink">Why it&apos;s worth a look</p>
          <p className="mt-1 text-sm leading-relaxed text-ink">{flagReason}</p>
        </div>
      )}

      {(fundamentals || news || filing) && (
        <div className="space-y-2.5">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-faint">Supporting data</p>

          {fundamentals && (
            <div className="rounded-lg border border-border bg-paper px-3.5 py-3">
              <div className="flex items-center gap-2">
                <p className="text-xs font-medium text-ink-secondary">Fundamentals</p>
                {fundamentals.isStale && <StatusChip tone="stale">Stale</StatusChip>}
              </div>
              <p className="mt-1 text-sm text-ink">
                <abbr title="Price-to-earnings ratio" className="cursor-help underline decoration-dotted decoration-ink-faint/50 underline-offset-2">
                  P/E
                </abbr>{" "}
                {fundamentals.value.priceToEarningsRatio?.toFixed(1)} ·{" "}
                <abbr
                  title="Return on equity, trailing twelve months"
                  className="cursor-help underline decoration-dotted decoration-ink-faint/50 underline-offset-2"
                >
                  ROE (TTM)
                </abbr>{" "}
                {((fundamentals.value.returnOnEquityTtm ?? 0) * 100).toFixed(0)}% ·{" "}
                <abbr title="Net profit margin" className="cursor-help underline decoration-dotted decoration-ink-faint/50 underline-offset-2">
                  Net margin
                </abbr>{" "}
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
              <div className="flex items-center gap-2">
                <p className="text-xs font-medium text-ink-secondary">Recent news</p>
                {news.isStale && <StatusChip tone="stale">Stale</StatusChip>}
              </div>
              <p className="mt-1 text-sm text-ink">{news.value.headline}</p>
              <p className="mt-1.5 text-xs text-ink-faint">
                {news.value.publisher} · {formatAsOf(news.value.publishedAt)} · via {news.source}
              </p>
            </a>
          )}

          {filing && (
            <div className="rounded-lg border border-border bg-paper px-3.5 py-3">
              <div className="flex items-center gap-2">
                <p className="text-xs font-medium text-ink-secondary">Filing</p>
                {filing.isStale && <StatusChip tone="stale">Stale</StatusChip>}
              </div>
              <p className="mt-1 text-sm text-ink">
                {filing.value.form} filed {formatDate(filing.value.filingDate)}
              </p>
              <p className="mt-1.5 font-mono text-xs text-ink-faint">{filing.value.accessionNumber}</p>
              <p className="mt-1 text-xs text-ink-faint">
                {filing.source} · as of {formatAsOf(filing.asOf)}
              </p>
            </div>
          )}
        </div>
      )}

      <button
        onClick={() => {
          ask(
            `What's relevant to my ${position.symbol} position right now?`,
            filing ? { symbol: position.symbol, accessionNumber: filing.value.accessionNumber } : undefined,
          );
          clearSelection();
        }}
        className="text-sm font-medium text-accent-ink hover:underline"
      >
        Ask about this position →
      </button>
    </div>
  );
}

/**
 * Overlays the map pane above 900px, leaving the conversation usable, and the
 * whole screen below it. See "Holdings list and detail" in DESIGN.md.
 */
export function HoldingDetailPanel({ holdings }: { holdings: HoldingDetail[] }) {
  const { selectedSymbol, clearSelection } = useWorkspace();
  const holding = holdings.find((h) => h.position.symbol === selectedSymbol) ?? null;

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") clearSelection();
    }
    if (holding) document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [holding, clearSelection]);

  if (!holding) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end min-[901px]:left-[520px]">
      <button aria-label="Close details" onClick={clearSelection} className="absolute inset-0 bg-ink/20 backdrop-blur-[1px]" />
      <div
        role="dialog"
        aria-label={`${holding.position.symbol} details`}
        className="relative flex h-full w-full max-w-md flex-col border-l border-border bg-surface shadow-xl"
      >
        <PanelHeader holding={holding} onClose={clearSelection} />
        <div className="flex-1 overflow-y-auto px-5 py-5">
          <HoldingDetailContent holding={holding} />
        </div>
      </div>
    </div>
  );
}
