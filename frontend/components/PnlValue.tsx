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
  size = "sm",
}: {
  dollars: number;
  percent: number | null;
  size?: "sm" | "md";
}) {
  const isNegative = dollars < 0;
  const glyph = isNegative ? "▼" : "▲";
  const textSize = size === "md" ? "text-base" : "text-sm";
  const dollarsWeight = size === "md" ? "font-semibold" : "font-medium";

  return (
    <span className={`inline-flex flex-nowrap items-baseline gap-1 whitespace-nowrap tabular-nums ${textSize}`}>
      <span aria-hidden className="text-[0.65em] text-ink-faint">
        {glyph}
      </span>
      <span className={`${dollarsWeight} text-ink`}>{formatSignedCurrency(dollars)}</span>
      {percent !== null && (
        <span className="text-ink-secondary">({formatSignedPercent(percent)})</span>
      )}
    </span>
  );
}
