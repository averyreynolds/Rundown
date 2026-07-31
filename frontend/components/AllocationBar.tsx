import type { HoldingDetail } from "@/lib/types";

const RAMP_OPACITY = [1, 0.82, 0.66, 0.52, 0.4, 0.3];
const MAX_SEGMENTS = RAMP_OPACITY.length;

export function AllocationBar({ holdings }: { holdings: HoldingDetail[] }) {
  const sorted = [...holdings].sort((a, b) => b.position.allocationPct - a.position.allocationPct);
  const shown = sorted.slice(0, MAX_SEGMENTS);
  const rest = sorted.slice(MAX_SEGMENTS);
  const restPct = rest.reduce((sum, h) => sum + h.position.allocationPct, 0);

  return (
    <div>
      <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-border">
        {shown.map((h, i) => (
          <div
            key={h.position.symbol}
            style={{ width: `${h.position.allocationPct}%`, backgroundColor: `rgba(54, 84, 214, ${RAMP_OPACITY[i]})` }}
            title={`${h.position.symbol} — ${h.position.allocationPct.toFixed(1)}%`}
          />
        ))}
        {restPct > 0 && (
          <div
            style={{ width: `${restPct}%` }}
            className="bg-border-strong"
            title={`Other — ${restPct.toFixed(1)}%`}
          />
        )}
      </div>
      <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-ink-secondary">
        {shown.map((h, i) => (
          <span key={h.position.symbol} className="inline-flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: `rgba(54, 84, 214, ${RAMP_OPACITY[i]})` }}
            />
            {h.position.symbol}
            <span className="tabular-nums text-ink-faint">{h.position.allocationPct.toFixed(1)}%</span>
          </span>
        ))}
        {restPct > 0 && (
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="inline-block h-2 w-2 rounded-full bg-border-strong" />
            Other
            <span className="tabular-nums text-ink-faint">{restPct.toFixed(1)}%</span>
          </span>
        )}
      </div>
    </div>
  );
}
