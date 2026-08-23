import { HoldingRow } from "./HoldingRow";
import type { HoldingDetail } from "@/lib/types";

export function HoldingsList({ holdings }: { holdings: HoldingDetail[] }) {
  const sorted = [...holdings].sort((a, b) => {
    if (a.flagged !== b.flagged) return a.flagged ? -1 : 1;
    return b.position.allocationPct - a.position.allocationPct;
  });
  const flaggedCount = sorted.filter((h) => h.flagged).length;

  return (
    <section className="mt-10">
      <div className="mb-3 flex items-baseline justify-between px-1">
        <h2 className="text-base font-semibold text-ink">Holdings</h2>
        <p className="text-xs text-ink-faint">
          {sorted.length} position{sorted.length === 1 ? "" : "s"}
          {flaggedCount > 0 && (
            <>
              {" "}
              · <span className="text-accent-ink">{flaggedCount} worth a look</span>
            </>
          )}
        </p>
      </div>
      <ul className="rounded-2xl border border-border bg-surface px-5 sm:px-6">
        {sorted.map((h) => (
          <HoldingRow key={h.position.symbol} holding={h} />
        ))}
      </ul>
    </section>
  );
}
