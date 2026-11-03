/**
 * Treemap geometry for the portfolio map. Presentation only: every figure on a
 * tile comes from the backend, and this decides only where tiles go.
 *
 * Columns are computed once from value and held across sizing modes, so tiles
 * resize instead of jumping. Every tile keeps a minimum size, which means
 * minimum-size tiles aren't proportional and the content can grow taller than
 * its area. See "Map density" in DESIGN.md.
 */

export const MIN_TILE_WIDTH = 76;
export const MIN_TILE_HEIGHT = 44;

export interface TreemapBounds {
  width: number;
  height: number;
  gap: number;
}

export interface TreemapTile {
  symbol: string;
  column: number;
  x: number;
  y: number;
  width: number;
  height: number;
  atMinimum: boolean;
}

export interface TreemapLayout {
  tiles: TreemapTile[];
  /** At least `bounds.height`; taller means the tile area has to scroll. */
  contentHeight: number;
  /** Whether any tile is drawn larger than its share, which the map must say. */
  hasMinimumSizeTiles: boolean;
}

/** Groups symbols into columns by value, keeping tiles as close to square as it can. */
export function computeColumns(
  items: readonly { symbol: string; value: number }[],
  bounds: TreemapBounds,
): string[][] {
  const sorted = items
    .map((item) => ({ symbol: item.symbol, value: Math.max(item.value, 0) }))
    .toSorted((a, b) => b.value - a.value || a.symbol.localeCompare(b.symbol));
  const maxColumns = Math.max(
    1,
    Math.floor((bounds.width + bounds.gap) / (MIN_TILE_WIDTH + bounds.gap)),
  );

  const columns: string[][] = [];
  let rest = sorted;
  let remainingWidth = bounds.width;

  while (rest.length > 0) {
    const restTotal = sum(rest.map((item) => item.value));
    const count =
      columns.length === maxColumns - 1
        ? rest.length
        : bestColumnSize(rest, restTotal, remainingWidth, bounds.height);
    const column = rest.slice(0, count);

    columns.push(column.map((item) => item.symbol));
    remainingWidth -= columnWidth(column, rest.length, restTotal, remainingWidth);
    rest = rest.slice(count);
  }
  return columns;
}

/** Sizes tiles to `measures`, for the columns from `computeColumns`. A missing measure is zero. */
export function layoutTreemap(
  columns: readonly (readonly string[])[],
  measures: Readonly<Record<string, number>>,
  bounds: TreemapBounds,
): TreemapLayout {
  const measureOf = (symbol: string) => Math.max(measures[symbol] ?? 0, 0);

  const tallestColumn = Math.max(0, ...columns.map((column) => column.length));
  const contentHeight = Math.max(
    bounds.height,
    stackedLength(tallestColumn, MIN_TILE_HEIGHT, bounds.gap),
  );

  const widths = allocate(
    columns.map((column) => sum(column.map(measureOf))),
    bounds.width - bounds.gap * (columns.length - 1),
    MIN_TILE_WIDTH,
  );

  const tiles: TreemapTile[] = [];
  let x = 0;
  columns.forEach((column, columnIndex) => {
    const heights = allocate(
      column.map(measureOf),
      contentHeight - bounds.gap * (column.length - 1),
      MIN_TILE_HEIGHT,
    );

    let y = 0;
    column.forEach((symbol, tileIndex) => {
      const height = heights[tileIndex];
      tiles.push({
        symbol,
        column: columnIndex,
        x,
        y,
        width: widths[columnIndex].size,
        height: height.size,
        atMinimum: widths[columnIndex].atMinimum || height.atMinimum,
      });
      y += height.size + bounds.gap;
    });
    x += widths[columnIndex].size + bounds.gap;
  });

  return {
    tiles,
    contentHeight,
    hasMinimumSizeTiles: tiles.some((tile) => tile.atMinimum),
  };
}

function bestColumnSize(
  rest: readonly { value: number }[],
  restTotal: number,
  remainingWidth: number,
  height: number,
): number {
  let best = rest.length;
  let bestAspect = Infinity;

  for (let count = 1; count < rest.length; count++) {
    const column = rest.slice(0, count);
    const width = columnWidth(column, rest.length, restTotal, remainingWidth);
    if (width < MIN_TILE_WIDTH) continue;

    const columnTotal = sum(column.map((item) => item.value));
    const worstAspect = Math.max(
      ...column.map((item) => {
        const share = columnTotal > 0 ? item.value / columnTotal : 1 / column.length;
        const tileHeight = share * height;
        return tileHeight > 0 ? Math.max(width / tileHeight, tileHeight / width) : Infinity;
      }),
    );
    if (worstAspect < bestAspect) {
      bestAspect = worstAspect;
      best = count;
    }
  }
  return best;
}

function columnWidth(
  column: readonly { value: number }[],
  restCount: number,
  restTotal: number,
  remainingWidth: number,
): number {
  const share =
    restTotal > 0 ? sum(column.map((item) => item.value)) / restTotal : column.length / restCount;
  return share * remainingWidth;
}

/**
 * Splits `available` in proportion to `weights`, with no size below `minimum`.
 * Anything below it is fixed at the minimum and the rest share what's left,
 * repeating because fixing one can push another below it. All-zero weights
 * share evenly. If the minimums alone don't fit, the sizes overflow `available`.
 */
function allocate(
  weights: readonly number[],
  available: number,
  minimum: number,
): { size: number; atMinimum: boolean }[] {
  const allZero = weights.every((weight) => weight === 0);
  const effective = allZero ? weights.map(() => 1) : weights;
  const fixed = new Set<number>();

  while (true) {
    const flexible = effective.flatMap((weight, index) =>
      fixed.has(index) ? [] : [{ weight, index }],
    );
    const flexibleTotal = sum(flexible.map((item) => item.weight));
    const flexibleSpace = available - fixed.size * minimum;
    const tooSmall = flexible.filter(
      (item) => flexibleTotal === 0 || (item.weight / flexibleTotal) * flexibleSpace < minimum,
    );

    if (tooSmall.length === 0) {
      return effective.map((weight, index) =>
        fixed.has(index)
          ? { size: minimum, atMinimum: true }
          : { size: (weight / flexibleTotal) * flexibleSpace, atMinimum: false },
      );
    }
    tooSmall.forEach((item) => fixed.add(item.index));
  }
}

function stackedLength(count: number, size: number, gap: number): number {
  return count * size + Math.max(count - 1, 0) * gap;
}

function sum(values: readonly number[]): number {
  return values.reduce((total, value) => total + value, 0);
}
