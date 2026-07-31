import { AllocationBar } from "./AllocationBar";
import { PnlValue } from "./PnlValue";
import { StatusChip } from "./StatusChip";
import { formatAsOf, formatCurrency } from "@/lib/format";
import type { AccountSummary, HoldingDetail } from "@/lib/types";

export function PortfolioSummary({
  holdings,
  totals,
  account,
  freshness,
}: {
  holdings: HoldingDetail[];
  totals: { totalValue: number; unrealizedPnlDollars: number; unrealizedPnlPercent: number };
  account: AccountSummary;
  freshness: { asOf: string; source: string; isStale: boolean };
}) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-6 sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-5">
        <div>
          <p className="text-sm text-ink-secondary">Total value</p>
          <p className="mt-1.5 text-[2.25rem] font-semibold leading-none tracking-[-0.02em] tabular-nums text-ink">
            {formatCurrency(totals.totalValue)}
          </p>
          {account.cash !== null && (
            <p className="mt-2 text-sm text-ink-faint">
              Includes {formatCurrency(account.cash)} cash in {account.name}
            </p>
          )}
        </div>

        <div className="text-right">
          <p className="text-sm text-ink-secondary">Unrealized, since cost basis</p>
          <div className="mt-1.5">
            <PnlValue dollars={totals.unrealizedPnlDollars} percent={totals.unrealizedPnlPercent} />
          </div>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-2.5">
        <p className="text-xs text-ink-faint">
          As of {formatAsOf(freshness.asOf)} · {freshness.source}
        </p>
        {freshness.isStale && <StatusChip tone="stale">Data is stale — refresh pending</StatusChip>}
      </div>

      <div className="mt-6">
        <AllocationBar holdings={holdings} />
      </div>
    </section>
  );
}
