import { formatSignedCurrency, formatSignedPercent } from "@/lib/format";

/**
 * P&L is rendered in neutral ink with a directional glyph, never a
 * red/green wash: CLAUDE.md hard rule 1 forbids the advisor (and, by
 * extension, this UI) from reading as a buy/sell signal, and a
 * stoplight-colored gain/loss figure is exactly that kind of implicit
 * directive. See the surface brief's "Selected direction" note.
 */
export function PnlValue({
  dollars,
  percent,
}: {
  dollars: number;
  percent: number | null;
}) {
  const isNegative = dollars < 0;
  const glyph = isNegative ? "▼" : "▲";

  return (
    <span className="inline-flex flex-nowrap items-baseline gap-1 whitespace-nowrap text-sm tabular-nums">
      <span aria-hidden className="text-[0.65em] text-ink-faint">
        {glyph}
      </span>
      <span className="font-medium text-ink">{formatSignedCurrency(dollars)}</span>
      {percent !== null && (
        <span className="text-ink-secondary">({formatSignedPercent(percent)})</span>
      )}
    </span>
  );
}
