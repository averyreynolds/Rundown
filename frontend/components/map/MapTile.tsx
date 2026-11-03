import { GAIN_LOSS_FILL } from "./GainLossLegend";
import {
  formatPercent,
  formatSignedCurrency,
  formatSignedCurrencyAbbreviated,
  formatSignedPercent,
} from "@/lib/format";
import { gainLossStep } from "@/lib/gain-loss";
import type { TreemapTile } from "@/lib/treemap";
import type { MapSizing, PositionRollup } from "@/lib/types";

/** Below this width a tile's full label doesn't fit, so it shows the short one. */
const FULL_LABEL_MIN_WIDTH = 132;
const READING_STAGGER_MS = 70;
const DETAILS_SIZE = 24;
const DETAILS_INSET = 6;

export type TileEmphasis = "focused" | "dimmed" | "none";

function glyph(value: number): string {
  return value < 0 ? "▼" : "▲";
}

function changeLabel(row: PositionRollup): string | null {
  if (row.gainPercent === null) return null;
  return `${glyph(row.gainPercent)} ${formatSignedPercent(row.gainPercent, 1)}`;
}

function tileLabel(row: PositionRollup, sizing: MapSizing, isNarrow: boolean): string {
  if (sizing === "cost") {
    if (row.shareOfCostPct === null) return "No cost basis";
    const share = formatPercent(row.shareOfCostPct, 1);
    return isNarrow ? share : `${share} of cost`;
  }
  if (sizing === "gain") {
    if (row.gainPercent === null) return "No cost basis";
    const format = isNarrow ? formatSignedCurrencyAbbreviated : formatSignedCurrency;
    return `${glyph(row.gainDollars)} ${format(row.gainDollars)}`;
  }

  const weight = formatPercent(row.shareOfValuePct, 1);
  const change = changeLabel(row);
  if (isNarrow) return change ?? weight;
  return change ? `${weight}  ${change}` : weight;
}

function accessibleName(row: PositionRollup, name: string, action: string): string {
  const change =
    row.gainPercent === null
      ? "no cost basis recorded"
      : `${formatSignedPercent(row.gainPercent, 1)} since cost, ${formatSignedCurrency(row.gainDollars)}`;
  return `${row.symbol}, ${name}. ${formatPercent(row.shareOfValuePct, 1)} of portfolio, ${change}. ${action}`;
}

/** Sets the arrow smaller than the figure, as `PnlValue` does. */
function withSmallGlyph(label: string): React.ReactNode {
  return label.split(/([▲▼])/).map((part, index) =>
    part === "▲" || part === "▼" ? (
      <span key={index} aria-hidden className="text-[0.7em]">
        {part}
      </span>
    ) : (
      part
    ),
  );
}

function tickerSize(shareOfMeasure: number): string {
  if (shareOfMeasure >= 0.1) return "text-[28px]";
  if (shareOfMeasure >= 0.05) return "text-xl";
  return "text-[15px]";
}

export function MapTile({
  row,
  name,
  tile,
  sizing,
  shareOfMeasure,
  emphasis,
  isResizing,
  readingIndex,
  action,
  onSelect,
  onHover,
  onDetails,
}: {
  row: PositionRollup;
  name: string;
  tile: TreemapTile;
  sizing: MapSizing;
  shareOfMeasure: number;
  emphasis: TileEmphasis;
  /** Whether a sizing change is in progress, the one time tiles resize with motion. */
  isResizing: boolean;
  /** This tile's place among those an answer is reading, or `null` if it isn't one. */
  readingIndex: number | null;
  /** What activating the tile does, read out as the end of its accessible name. */
  action: string;
  onSelect?: (symbol: string) => void;
  onHover?: (symbol: string | null) => void;
  /** Offered on a focused tile, as a sibling button since buttons can't nest. */
  onDetails?: (symbol: string) => void;
}) {
  const isNarrow = tile.width < FULL_LABEL_MIN_WIDTH;
  const fill =
    emphasis === "dimmed"
      ? "bg-map-dimmed text-ink-secondary"
      : `${GAIN_LOSS_FILL[gainLossStep(row.gainPercent)]} text-ink`;
  // Identical on a gain or a loss: the outline must never read as an alert.
  const outline = emphasis === "focused" ? "shadow-[inset_0_0_0_3px_var(--color-ink)]" : "";

  const motion = isResizing ? "map-tile-resizing" : "map-tile";

  return (
    <div
      className="contents"
      onMouseEnter={() => onHover?.(row.symbol)}
      onMouseLeave={() => onHover?.(null)}
      onFocus={() => onHover?.(row.symbol)}
      onBlur={(event) => {
        // Tabbing to the details control stays on this tile. Clearing here would
        // remove that control just as it's about to receive focus.
        if (!event.currentTarget.contains(event.relatedTarget)) onHover?.(null);
      }}
    >
      <button
        type="button"
        aria-label={accessibleName(row, name, action)}
        aria-current={emphasis === "focused" ? "true" : undefined}
        onClick={() => onSelect?.(row.symbol)}
        style={{
          left: tile.x,
          top: tile.y,
          width: tile.width,
          height: tile.height,
          animationDelay:
            readingIndex === null ? undefined : `${readingIndex * READING_STAGGER_MS}ms`,
        }}
        className={`absolute flex flex-col justify-between overflow-hidden rounded-md text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
          isNarrow ? "px-1.5 py-1" : "px-2.5 py-2"
        } ${fill} ${outline} ${motion} ${readingIndex === null ? "" : "map-tile-reading"}`}
      >
        <span
          className={`font-bold leading-[1.1] tracking-[-0.02em] ${tickerSize(shareOfMeasure)}`}
        >
          {row.symbol}
        </span>
        <span className="whitespace-pre font-mono text-[11px] leading-[1.3] tabular-nums sm:text-xs">
          {withSmallGlyph(tileLabel(row, sizing, isNarrow))}
        </span>
      </button>
      {emphasis === "focused" && onDetails && (
        <button
          type="button"
          aria-label={`${row.symbol} details`}
          onClick={() => onDetails(row.symbol)}
          style={{
            left: tile.x + tile.width - DETAILS_SIZE - DETAILS_INSET,
            top: tile.y + DETAILS_INSET,
            width: DETAILS_SIZE,
            height: DETAILS_SIZE,
          }}
          className={`absolute flex items-center justify-center rounded-full bg-surface text-xs font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${motion}`}
        >
          <span aria-hidden>i</span>
        </button>
      )}
    </div>
  );
}
