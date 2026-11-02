"use client";

import { useEffect } from "react";
import { PnlValue } from "../PnlValue";
import { StatusChip } from "../StatusChip";
import { useAdvisor } from "../advisor/AdvisorProvider";
import { CostBasisBar } from "./CostBasisBar";
import { PositionChart } from "./PositionChart";
import { useHoldingSelection } from "./HoldingSelectionProvider";
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
  const { open } = useAdvisor();
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
        onClick={() =>
          open(position.symbol, filing ? { symbol: position.symbol, accessionNumber: filing.value.accessionNumber } : undefined)
        }
        className="text-sm font-medium text-accent-ink hover:underline"
      >
        Ask about this position →
      </button>
    </div>
  );
}

function EmptyPanelState() {
  return (
    <div className="flex h-full min-h-[220px] flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-paper">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
          <path
            d="M2 8a6 6 0 1 1 12 0A6 6 0 0 1 2 8Zm6-3v3l2 1.5"
            stroke="currentColor"
            strokeWidth="1.3"
            strokeLinecap="round"
            className="text-ink-faint"
          />
        </svg>
      </div>
      <p className="text-sm text-ink-secondary">Select a holding to see its fundamentals, filing, and news.</p>
    </div>
  );
}

export function HoldingDetailPanel({ holdings }: { holdings: HoldingDetail[] }) {
  const { selectedSymbol, clear } = useHoldingSelection();
  const holding = holdings.find((h) => h.position.symbol === selectedSymbol) ?? null;

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") clear();
    }
    if (holding) document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [holding, clear]);

  return (
    <>
      {holding && (
        <div className="fixed inset-0 z-50 flex justify-end lg:hidden">
          <button aria-label="Close details" onClick={clear} className="absolute inset-0 bg-ink/20 backdrop-blur-[1px]" />
          <div
            role="dialog"
            aria-modal="true"
            aria-label={`${holding.position.symbol} details`}
            className="relative flex h-full w-full max-w-md flex-col border-l border-border bg-surface shadow-xl"
          >
            <PanelHeader holding={holding} onClose={clear} />
            <div className="flex-1 overflow-y-auto px-5 py-5">
              <HoldingDetailContent holding={holding} />
            </div>
          </div>
        </div>
      )}

      <div className="hidden lg:sticky lg:top-10 lg:block lg:max-h-[calc(100vh-5rem)] lg:overflow-y-auto lg:rounded-2xl lg:border lg:border-border lg:bg-surface">
        {holding ? (
          <>
            <PanelHeader holding={holding} onClose={clear} />
            <div className="px-5 py-5">
              <HoldingDetailContent holding={holding} />
            </div>
          </>
        ) : (
          <EmptyPanelState />
        )}
      </div>
    </>
  );
}
