import { formatCurrency } from "@/lib/format";

/**
 * Where the current price sits relative to average cost, as a track+fill
 * bar rather than two bare numbers. One neutral hue regardless of
 * direction -- see PriceChart.tsx's note on why this app never
 * red/green-codes a price move.
 */
export function CostBasisBar({ costBasisPerShare, currentPrice }: { costBasisPerShare: number; currentPrice: number }) {
  const low = Math.min(costBasisPerShare, currentPrice);
  const high = Math.max(costBasisPerShare, currentPrice);
  const domainPadding = (high - low || high * 0.05 || 1) * 0.4;
  const domainMin = Math.max(0, low - domainPadding);
  const domainMax = high + domainPadding;
  const domainSpan = domainMax - domainMin || 1;

  const costPct = ((costBasisPerShare - domainMin) / domainSpan) * 100;
  const currentPct = ((currentPrice - domainMin) / domainSpan) * 100;
  const fillLeft = Math.min(costPct, currentPct);
  const fillWidth = Math.abs(currentPct - costPct);

  return (
    <div>
      <div className="relative h-1.5 rounded-full bg-accent-soft">
        <div
          className="absolute inset-y-0 rounded-full bg-accent"
          style={{ left: `${fillLeft}%`, width: `${fillWidth}%` }}
        />
        <div
          className="absolute top-1/2 h-2.5 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-ink-faint"
          style={{ left: `${costPct}%` }}
          aria-hidden
        />
      </div>
      <div className="mt-1.5 flex justify-between text-xs text-ink-faint">
        <span>Avg cost {formatCurrency(costBasisPerShare)}</span>
        <span>Current {formatCurrency(currentPrice)}</span>
      </div>
    </div>
  );
}
