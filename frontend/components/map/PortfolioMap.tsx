"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { StatusChip } from "../StatusChip";
import { GainLossLegend } from "./GainLossLegend";
import { MapTile, type TileEmphasis } from "./MapTile";
import { SizingControl, type MapSizing } from "./SizingControl";
import { formatAsOf, formatCurrency, formatSignedCurrency } from "@/lib/format";
import { computeColumns, layoutTreemap, type TreemapBounds } from "@/lib/treemap";
import type { PortfolioRollup, PositionRollup, SourcedValue } from "@/lib/types";

type MapView = "map" | "table";

const TILE_GAP = 4;
// What the first render lays out against, before the area can be measured.
const INITIAL_BOUNDS: TreemapBounds = { width: 860, height: 720, gap: TILE_GAP };

/** Tile area for a sizing mode. A position with no cost basis has no known gain to size by. */
function measureOf(row: PositionRollup, sizing: MapSizing): number {
  if (sizing === "cost") return row.costBasis;
  if (sizing === "gain") return row.gainPercent === null ? 0 : Math.abs(row.gainDollars);
  return row.marketValue;
}

/**
 * The map and table are two views of the same positions. Below 901px there is
 * no treemap, only `tableView`: see "Layout" in DESIGN.md.
 */
export function PortfolioMap({
  rollup,
  names,
  tableView,
  focusedSymbols = [],
  tileAction,
  onTileSelect,
}: {
  rollup: SourcedValue<PortfolioRollup>;
  names: Readonly<Record<string, string>>;
  tableView: React.ReactNode;
  focusedSymbols?: readonly string[];
  tileAction: string;
  onTileSelect?: (symbol: string) => void;
}) {
  const [view, setView] = useState<MapView>("map");
  const [sizing, setSizing] = useState<MapSizing>("value");
  const [bounds, setBounds] = useState(INITIAL_BOUNDS);
  const [isResizing, setIsResizing] = useState(false);
  const areaRef = useRef<HTMLDivElement>(null);

  const { positions, totalMarketValue, netGainDollars } = rollup.value;

  useEffect(() => {
    const area = areaRef.current;
    if (!area || typeof ResizeObserver === "undefined") return;

    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      // A hidden area measures zero: keep the last real size for when it returns.
      if (width === 0 || height === 0) return;
      setIsResizing(false);
      setBounds({ width, height, gap: TILE_GAP });
    });
    observer.observe(area);
    return () => observer.disconnect();
  }, [positions.length]);

  const columns = useMemo(
    () =>
      computeColumns(
        positions.map((row) => ({ symbol: row.symbol, value: row.marketValue })),
        bounds,
      ),
    [positions, bounds],
  );
  const measures = useMemo(
    () => Object.fromEntries(positions.map((row) => [row.symbol, measureOf(row, sizing)])),
    [positions, sizing],
  );
  const layout = useMemo(() => layoutTreemap(columns, measures, bounds), [columns, measures, bounds]);

  if (positions.length === 0) return <>{tableView}</>;

  const rowsBySymbol = new Map(positions.map((row) => [row.symbol, row]));
  const totalMeasure = Object.values(measures).reduce((sum, measure) => sum + measure, 0);
  const hasFocus = focusedSymbols.length > 0;

  function changeSizing(next: MapSizing) {
    setIsResizing(true);
    setSizing(next);
  }

  function emphasisOf(symbol: string): TileEmphasis {
    if (!hasFocus) return "none";
    return focusedSymbols.includes(symbol) ? "focused" : "dimmed";
  }

  return (
    <section aria-label="Portfolio map" className="flex flex-col gap-2.5 min-[901px]:h-full">
      <div className="hidden flex-wrap items-center justify-between gap-x-5 gap-y-2 min-[901px]:flex">
        <div className="flex flex-wrap items-center gap-2.5">
          <div role="group" aria-label="View as" className="flex gap-0.5 rounded-full bg-paper p-0.5">
            {(["map", "table"] as const).map((option) => (
              <button
                key={option}
                type="button"
                aria-pressed={view === option}
                onClick={() => setView(option)}
                className={`min-h-9 rounded-full px-3 text-xs font-medium capitalize transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
                  view === option ? "bg-ink text-white" : "text-ink-secondary hover:text-ink"
                }`}
              >
                {option}
              </button>
            ))}
          </div>
          {view === "map" && <SizingControl sizing={sizing} onChange={changeSizing} />}
        </div>
        {view === "map" && <GainLossLegend />}
      </div>

      {view === "map" && layout.hasMinimumSizeTiles && (
        <p className="hidden text-xs text-ink-secondary min-[901px]:block">
          Small positions are shown at a minimum size.
        </p>
      )}

      <div
        ref={areaRef}
        data-testid="map-area"
        className={
          view === "map"
            ? "hidden min-h-0 flex-1 overflow-y-auto min-[901px]:block"
            : "hidden"
        }
      >
        <div className="relative w-full" style={{ height: layout.contentHeight }}>
          {layout.tiles.map((tile) => {
            const row = rowsBySymbol.get(tile.symbol);
            if (!row) return null;
            return (
              <MapTile
                key={tile.symbol}
                row={row}
                name={names[tile.symbol] ?? tile.symbol}
                tile={tile}
                sizing={sizing}
                shareOfMeasure={totalMeasure > 0 ? (measures[tile.symbol] ?? 0) / totalMeasure : 0}
                emphasis={emphasisOf(tile.symbol)}
                isResizing={isResizing}
                action={tileAction}
                onSelect={onTileSelect}
              />
            );
          })}
        </div>
      </div>

      <div
        data-testid="table-area"
        className={
          view === "table"
            ? "min-[901px]:min-h-0 min-[901px]:flex-1 min-[901px]:overflow-y-auto"
            : "min-[901px]:hidden"
        }
      >
        {tableView}
      </div>

      <p className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-xs text-ink-faint tabular-nums">
        <span>
          {formatCurrency(totalMarketValue)} in positions,{" "}
          <span aria-hidden className="text-[0.7em]">
            {netGainDollars < 0 ? "▼" : "▲"}
          </span>{" "}
          {formatSignedCurrency(netGainDollars)} since cost
        </span>
        <span className="inline-flex items-center gap-2">
          {rollup.isStale && <StatusChip tone="stale">Data is stale</StatusChip>}
          {rollup.source} · as of {formatAsOf(rollup.asOf)}
        </span>
      </p>
    </section>
  );
}
