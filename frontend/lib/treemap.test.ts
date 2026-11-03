import { describe, expect, it } from "vitest";

import { MIN_TILE_HEIGHT, MIN_TILE_WIDTH, computeColumns, layoutTreemap } from "./treemap";
import type { TreemapBounds, TreemapTile } from "./treemap";

const BOUNDS: TreemapBounds = { width: 860, height: 720, gap: 4 };

// Synthetic, gently concentrated portfolio: no real holdings.
function portfolio(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    symbol: `S${index + 1}`,
    value: 100_000 / Math.pow(index + 1, 0.9),
  }));
}

function measuresFrom(items: { symbol: string; value: number }[], scale = (value: number) => value) {
  return Object.fromEntries(items.map((item) => [item.symbol, scale(item.value)]));
}

function bySymbol(tiles: TreemapTile[], symbol: string): TreemapTile {
  const tile = tiles.find((candidate) => candidate.symbol === symbol);
  if (!tile) throw new Error(`no tile for ${symbol}`);
  return tile;
}

describe("computeColumns", () => {
  it("places every symbol in exactly one column", () => {
    const items = portfolio(30);
    const symbols = computeColumns(items, BOUNDS).flat();

    expect(symbols.toSorted()).toEqual(items.map((item) => item.symbol).toSorted());
  });

  it("is deterministic for the same input", () => {
    const items = portfolio(11);

    expect(computeColumns(items, BOUNDS)).toEqual(computeColumns(items, BOUNDS));
  });

  it("orders by value regardless of input order", () => {
    const items = portfolio(11);

    expect(computeColumns(items.toReversed(), BOUNDS)).toEqual(computeColumns(items, BOUNDS));
  });

  it("never makes more columns than the width can hold at minimum size", () => {
    const narrow = { width: 300, height: 720, gap: 4 };
    const maxColumns = Math.floor((narrow.width + narrow.gap) / (MIN_TILE_WIDTH + narrow.gap));

    expect(computeColumns(portfolio(30), narrow).length).toBeLessThanOrEqual(maxColumns);
  });

  it("doesn't strand a small position in a final column narrower than the minimum", () => {
    const items = [
      ...portfolio(10),
      { symbol: "TINY", value: 500 },
    ];
    const bounds = { width: 720, height: 560, gap: 4 };
    const { tiles } = layoutTreemap(computeColumns(items, bounds), measuresFrom(items), bounds);

    const column = bySymbol(tiles, "TINY").column;
    expect(tiles.filter((tile) => tile.column === column).length).toBeGreaterThan(1);
    expect(bySymbol(tiles, "TINY").width).toBeGreaterThan(MIN_TILE_WIDTH);
  });

  it("returns no columns for no positions", () => {
    expect(computeColumns([], BOUNDS)).toEqual([]);
  });
});

describe("layoutTreemap", () => {
  it("sizes tiles in proportion to the measure within a column", () => {
    const items = [
      { symbol: "A", value: 300 },
      { symbol: "B", value: 100 },
    ];
    const { tiles } = layoutTreemap([["A", "B"]], measuresFrom(items), BOUNDS);
    const a = bySymbol(tiles, "A");
    const b = bySymbol(tiles, "B");

    expect(a.width).toBeCloseTo(BOUNDS.width);
    expect(a.height / b.height).toBeCloseTo(3);
  });

  it("fills the full area when no tile is at the minimum", () => {
    const items = [
      { symbol: "A", value: 400 },
      { symbol: "B", value: 300 },
      { symbol: "C", value: 200 },
      { symbol: "D", value: 100 },
    ];
    const columns = computeColumns(items, BOUNDS);
    const { tiles, contentHeight, hasMinimumSizeTiles } = layoutTreemap(
      columns,
      measuresFrom(items),
      BOUNDS,
    );

    const tileArea = tiles.reduce((sum, tile) => sum + tile.width * tile.height, 0);
    const gapArea =
      (columns.length - 1) * BOUNDS.gap * BOUNDS.height +
      columns.reduce((sum, column) => {
        const columnWidth = bySymbol(tiles, column[0]).width;
        return sum + (column.length - 1) * BOUNDS.gap * columnWidth;
      }, 0);

    expect(hasMinimumSizeTiles).toBe(false);
    expect(contentHeight).toBe(BOUNDS.height);
    expect(tileArea + gapArea).toBeCloseTo(BOUNDS.width * BOUNDS.height, 3);
  });

  it("keeps tiles inside the area without overlapping", () => {
    const items = portfolio(30);
    const { tiles, contentHeight } = layoutTreemap(
      computeColumns(items, BOUNDS),
      measuresFrom(items),
      BOUNDS,
    );

    for (const tile of tiles) {
      expect(tile.x).toBeGreaterThanOrEqual(0);
      expect(tile.x + tile.width).toBeLessThanOrEqual(BOUNDS.width + 0.001);
      expect(tile.y + tile.height).toBeLessThanOrEqual(contentHeight + 0.001);
    }
    for (const a of tiles) {
      for (const b of tiles) {
        if (a === b) continue;
        const overlapsX = a.x < b.x + b.width - 0.001 && b.x < a.x + a.width - 0.001;
        const overlapsY = a.y < b.y + b.height - 0.001 && b.y < a.y + a.height - 0.001;
        expect(overlapsX && overlapsY).toBe(false);
      }
    }
  });

  it("keeps every symbol in the same column when the sizing mode changes", () => {
    const items = portfolio(11);
    const columns = computeColumns(items, BOUNDS);
    const columnOf = (tiles: TreemapTile[], symbol: string) => bySymbol(tiles, symbol).column;

    const byValue = layoutTreemap(columns, measuresFrom(items), BOUNDS).tiles;
    const byGain = layoutTreemap(
      columns,
      measuresFrom(items, (value) => Math.abs(Math.sin(value)) * 1000),
      BOUNDS,
    ).tiles;

    for (const item of items) {
      expect(columnOf(byGain, item.symbol)).toBe(columnOf(byValue, item.symbol));
    }
    expect(bySymbol(byGain, "S1").height).not.toBeCloseTo(bySymbol(byValue, "S1").height);
  });

  it("lets a single position fill the map", () => {
    const items = [{ symbol: "ONLY", value: 500 }];
    const { tiles } = layoutTreemap(computeColumns(items, BOUNDS), measuresFrom(items), BOUNDS);

    expect(tiles).toEqual([
      expect.objectContaining({ x: 0, y: 0, width: BOUNDS.width, height: BOUNDS.height }),
    ]);
  });

  it("gives a zero-measure position the minimum size without dividing by zero", () => {
    const { tiles, hasMinimumSizeTiles } = layoutTreemap(
      [["A", "B"]],
      { A: 500, B: 0 },
      BOUNDS,
    );
    const b = bySymbol(tiles, "B");

    expect(b.height).toBe(MIN_TILE_HEIGHT);
    expect(b.atMinimum).toBe(true);
    expect(hasMinimumSizeTiles).toBe(true);
    expect(Number.isFinite(bySymbol(tiles, "A").height)).toBe(true);
  });

  it("shares the area evenly when every measure is zero", () => {
    const { tiles } = layoutTreemap([["A", "B"]], { A: 0, B: 0 }, BOUNDS);

    expect(bySymbol(tiles, "A").height).toBeCloseTo(bySymbol(tiles, "B").height);
    expect(bySymbol(tiles, "A").height).toBeGreaterThan(MIN_TILE_HEIGHT);
  });

  it("treats a symbol with no measure as zero", () => {
    const { tiles } = layoutTreemap([["A", "B"]], { A: 500 }, BOUNDS);

    expect(bySymbol(tiles, "B").height).toBe(MIN_TILE_HEIGHT);
  });

  it.each(["value", "gain"] as const)(
    "keeps 30 positions at or above the minimum size when sized by %s",
    (mode) => {
      const items = portfolio(30);
      const scale =
        mode === "gain" ? (value: number) => Math.abs(Math.sin(value)) * value : undefined;
      const { tiles } = layoutTreemap(
        computeColumns(items, BOUNDS),
        measuresFrom(items, scale),
        BOUNDS,
      );

      expect(tiles).toHaveLength(30);
      for (const tile of tiles) {
        expect(tile.width).toBeGreaterThanOrEqual(MIN_TILE_WIDTH - 0.001);
        expect(tile.height).toBeGreaterThanOrEqual(MIN_TILE_HEIGHT - 0.001);
      }
    },
  );

  it("fits 30 synthetic positions on one desktop screen", () => {
    const items = portfolio(30);
    const { contentHeight } = layoutTreemap(
      computeColumns(items, BOUNDS),
      measuresFrom(items),
      BOUNDS,
    );

    expect(contentHeight).toBe(BOUNDS.height);
  });

  it("grows past the area instead of shrinking tiles when they can't all fit", () => {
    const short = { width: 300, height: 200, gap: 4 };
    const items = portfolio(30);
    const { tiles, contentHeight } = layoutTreemap(
      computeColumns(items, short),
      measuresFrom(items),
      short,
    );

    expect(contentHeight).toBeGreaterThan(short.height);
    for (const tile of tiles) {
      expect(tile.height).toBeGreaterThanOrEqual(MIN_TILE_HEIGHT - 0.001);
      expect(tile.x + tile.width).toBeLessThanOrEqual(short.width + 0.001);
    }
  });

  it("returns an empty layout for no columns", () => {
    expect(layoutTreemap([], {}, BOUNDS)).toEqual({
      tiles: [],
      contentHeight: BOUNDS.height,
      hasMinimumSizeTiles: false,
    });
  });
});
