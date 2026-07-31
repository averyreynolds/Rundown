import { HoldingRow } from "./HoldingRow";
import type { HoldingDetail } from "@/lib/types";

export function HoldingsList({ holdings }: { holdings: HoldingDetail[] }) {
  const sorted = [...holdings].sort((a, b) => b.position.allocationPct - a.position.allocationPct);

  return (
    <section className="mt-8">
      <div className="mb-2 flex items-baseline justify-between px-1">
        <h2 className="text-sm font-medium text-ink-secondary">Holdings</h2>
        <p className="text-xs text-ink-faint">{sorted.length} positions</p>
      </div>
      <ul className="rounded-2xl border border-border bg-surface px-5 sm:px-6">
        {sorted.map((h) => (
          <HoldingRow key={h.position.symbol} holding={h} />
        ))}
      </ul>
    </section>
  );
}
