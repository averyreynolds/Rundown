import { formatSignedCurrency, formatSignedPercent } from "@/lib/format";

/**
 * P&L figures stay in ink with a sign and a directional glyph, so color is
 * never the only signal. Any gain/loss color sits behind a figure as a fill,
 * as on the portfolio map. See "The Gain/Loss Color Rule" in DESIGN.md.
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
