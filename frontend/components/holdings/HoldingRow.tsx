"use client";

import { PnlValue } from "../PnlValue";
import { StatusChip } from "../StatusChip";
import { useHoldingSelection } from "./HoldingSelectionProvider";
import { formatCurrency, formatPercent } from "@/lib/format";
import type { HoldingDetail } from "@/lib/types";

export function HoldingRow({ holding }: { holding: HoldingDetail }) {
  const { selectedSymbol, select } = useHoldingSelection();
  const { position, name, flagged } = holding;
  const isSelected = selectedSymbol === position.symbol;

  return (
    <li className="border-b border-border last:border-b-0">
      <button
        onClick={() => select(position.symbol)}
        aria-current={isSelected ? "true" : undefined}
        aria-label={`${position.symbol} — ${name}, view details`}
        className={`grid w-full grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 px-1 py-4 text-left transition-colors sm:grid-cols-[minmax(0,2fr)_minmax(88px,1fr)_minmax(150px,1fr)] sm:gap-x-6 ${
          isSelected ? "bg-paper" : "hover:bg-paper/60"
        }`}
      >
        <div className="flex min-w-0 items-center gap-3.5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-paper text-sm font-semibold text-ink-secondary">
            {position.symbol.slice(0, 2)}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="truncate text-base font-semibold text-ink">{position.symbol}</p>
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
    </li>
  );
}
