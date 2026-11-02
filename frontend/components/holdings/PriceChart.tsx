"use client";

import { useId, useMemo, useState } from "react";
import { formatCurrency, formatDate } from "@/lib/format";

export interface PriceChartPoint {
  date: string; // ISO date, e.g. "2024-06-14"
  close: number;
}

const VIEW_WIDTH = 600;
const VIEW_HEIGHT = 200;
const PADDING = { top: 22, right: 10, bottom: 22, left: 10 };

/**
 * A single price line for one position over the selected window, with an
 * optional dashed cost-basis reference line. Deliberately one neutral
 * accent-colored line regardless of whether the window's move is a gain or
 * a loss -- see PnlValue.tsx: a stoplight-colored chart would read as the
 * same kind of implicit buy/sell signal CLAUDE.md's advisor rule forbids,
 * just drawn instead of spoken.
 *
 * No charting library: the frontend has none installed, and a two-line
 * series plus one reference line doesn't need one.
 */
export function PriceChart({
  points,
  costBasisPerShare,
}: {
  points: PriceChartPoint[];
  costBasisPerShare?: number | null;
}) {
  const gradientId = useId();
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  const layout = useMemo(() => buildLayout(points, costBasisPerShare ?? null), [points, costBasisPerShare]);

  if (points.length < 2 || !layout) {
    return (
      <div className="flex h-[140px] items-center justify-center text-xs text-ink-faint">
        Not enough price history to chart yet.
      </div>
    );
  }

  const { linePath, areaPath, coords, costBasisY } = layout;
  const last = points.length - 1;
  const active = activeIndex ?? last;
  const activePoint = points[active];
  const activeCoord = coords[active];

  function nearestIndexForClientX(container: SVGSVGElement, clientX: number): number {
    const rect = container.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const viewX = PADDING.left + ratio * (VIEW_WIDTH - PADDING.left - PADDING.right);
    let closest = 0;
    let closestDistance = Infinity;
    coords.forEach(({ x }, index) => {
      const distance = Math.abs(x - viewX);
      if (distance < closestDistance) {
        closestDistance = distance;
        closest = index;
      }
    });
    return closest;
  }

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
        className="block w-full touch-none"
        role="img"
        aria-label={`Price from ${formatDate(points[0].date)} to ${formatDate(points[last].date)}, ${formatCurrency(points[0].close)} to ${formatCurrency(points[last].close)}`}
        tabIndex={0}
        onFocus={() => setActiveIndex(last)}
        onBlur={() => setActiveIndex(null)}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") {
            e.preventDefault();
            setActiveIndex((current) => Math.max(0, (current ?? last) - 1));
          } else if (e.key === "ArrowRight") {
            e.preventDefault();
            setActiveIndex((current) => Math.min(last, (current ?? last) + 1));
          } else if (e.key === "Escape") {
            setActiveIndex(null);
          }
        }}
        onPointerMove={(e) => setActiveIndex(nearestIndexForClientX(e.currentTarget, e.clientX))}
        onPointerLeave={() => setActiveIndex(null)}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.14" />
            <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {costBasisY !== null && (
          <>
            <line
              x1={PADDING.left}
              x2={VIEW_WIDTH - PADDING.right}
              y1={costBasisY}
              y2={costBasisY}
              stroke="var(--color-ink-faint)"
              strokeWidth={1}
              strokeDasharray="4 4"
            />
            <text x={PADDING.left} y={costBasisY - 5} className="fill-ink-faint text-[9px]">
              Avg cost {formatCurrency(costBasisPerShare ?? 0)}
            </text>
          </>
        )}

        <path d={areaPath} fill={`url(#${gradientId})`} stroke="none" />
        <path d={linePath} fill="none" stroke="var(--color-accent)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

        {/* End-of-line marker + direct value label -- text carries a text token, never the line color. */}
        <circle cx={coords[last].x} cy={coords[last].y} r={4} fill="var(--color-accent)" stroke="var(--color-surface)" strokeWidth={2} />
        <text x={coords[last].x} y={PADDING.top - 8} textAnchor="end" className="fill-ink text-[10px] font-medium">
          {formatCurrency(points[last].close)}
        </text>

        {/* Crosshair + hover/focus marker. */}
        <line
          x1={activeCoord.x}
          x2={activeCoord.x}
          y1={PADDING.top}
          y2={VIEW_HEIGHT - PADDING.bottom}
          stroke="var(--color-border-strong)"
          strokeWidth={1}
          opacity={activeIndex === null ? 0 : 1}
        />
        <circle
          cx={activeCoord.x}
          cy={activeCoord.y}
          r={4}
          fill="var(--color-accent)"
          stroke="var(--color-surface)"
          strokeWidth={2}
          opacity={activeIndex === null ? 0 : 1}
        />

        <text x={PADDING.left} y={VIEW_HEIGHT - 6} className="fill-ink-faint text-[9px]">
          {formatDate(points[0].date)}
        </text>
        <text x={VIEW_WIDTH - PADDING.right} y={VIEW_HEIGHT - 6} textAnchor="end" className="fill-ink-faint text-[9px]">
          {formatDate(points[last].date)}
        </text>

        {/* Full-area hit target for pointer tracking -- larger than the painted line. */}
        <rect
          x={PADDING.left}
          y={0}
          width={VIEW_WIDTH - PADDING.left - PADDING.right}
          height={VIEW_HEIGHT}
          fill="transparent"
        />
      </svg>

      {activeIndex !== null && (
        <div
          role="status"
          className="pointer-events-none absolute top-0 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-surface px-2 py-1 text-xs shadow-sm"
          style={{
            left: `${(activeCoord.x / VIEW_WIDTH) * 100}%`,
          }}
        >
          <span className="font-semibold tabular-nums text-ink">{formatCurrency(activePoint.close)}</span>{" "}
          <span className="text-ink-faint">{formatDate(activePoint.date)}</span>
        </div>
      )}
    </div>
  );
}

function buildLayout(points: PriceChartPoint[], costBasisPerShare: number | null) {
  if (points.length < 2) return null;

  const closes = points.map((p) => p.close);
  const values = costBasisPerShare !== null ? [...closes, costBasisPerShare] : closes;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const padded = { min: min - range * 0.08, max: max + range * 0.08 };
  const paddedRange = padded.max - padded.min || 1;

  const innerWidth = VIEW_WIDTH - PADDING.left - PADDING.right;
  const innerHeight = VIEW_HEIGHT - PADDING.top - PADDING.bottom;

  const yFor = (close: number) => PADDING.top + innerHeight - ((close - padded.min) / paddedRange) * innerHeight;
  const xFor = (index: number) => PADDING.left + (points.length === 1 ? 0 : (index / (points.length - 1)) * innerWidth);

  const coords = points.map((p, i) => ({ x: xFor(i), y: yFor(p.close) }));

  const linePath = coords.map((c, i) => `${i === 0 ? "M" : "L"}${c.x.toFixed(2)},${c.y.toFixed(2)}`).join(" ");
  const baseline = PADDING.top + innerHeight;
  const areaPath = `${linePath} L${coords[coords.length - 1].x.toFixed(2)},${baseline} L${coords[0].x.toFixed(2)},${baseline} Z`;

  return {
    linePath,
    areaPath,
    coords,
    costBasisY: costBasisPerShare !== null ? yFor(costBasisPerShare) : null,
    yFor,
  };
}
