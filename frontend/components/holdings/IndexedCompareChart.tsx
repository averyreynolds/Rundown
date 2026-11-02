"use client";

import { useMemo, useState } from "react";
import type { PriceChartPoint } from "./PriceChart";
import { formatDate, formatSignedPercent } from "@/lib/format";

const VIEW_WIDTH = 600;
const VIEW_HEIGHT = 200;
const PADDING = { top: 22, right: 10, bottom: 22, left: 10 };

const POSITION_COLOR = "var(--color-accent)";
const BENCHMARK_COLOR = "var(--color-ink-faint)"; // de-emphasis hue: a comparison line, not a second identity.

interface IndexedPoint {
  date: string;
  percent: number; // % change from the first point in the (shared) window
}

function toIndexed(points: PriceChartPoint[]): IndexedPoint[] {
  if (points.length === 0) return [];
  const base = points[0].close;
  return points.map((p) => ({ date: p.date, percent: base === 0 ? 0 : ((p.close - base) / base) * 100 }));
}

/**
 * Two series -- the held position and a benchmark -- indexed to % change
 * from the window's first shared point, on one shared axis. Two
 * differently-scaled prices (e.g. a $148 stock vs. a $550 index) never
 * share a dual y-axis (dataviz's #1 anti-pattern); indexing to a common
 * base is the correct fix, not a second axis.
 */
export function IndexedCompareChart({
  positionLabel,
  positionPoints,
  benchmarkLabel,
  benchmarkPoints,
}: {
  positionLabel: string;
  positionPoints: PriceChartPoint[];
  benchmarkLabel: string;
  benchmarkPoints: PriceChartPoint[];
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  const layout = useMemo(() => {
    const n = Math.min(positionPoints.length, benchmarkPoints.length);
    if (n < 2) return null;
    const position = toIndexed(positionPoints.slice(-n));
    const benchmark = toIndexed(benchmarkPoints.slice(-n));

    const values = [...position, ...benchmark].map((p) => p.percent);
    const min = Math.min(...values, 0);
    const max = Math.max(...values, 0);
    const range = max - min || 1;
    const padded = { min: min - range * 0.1, max: max + range * 0.1 };
    const paddedRange = padded.max - padded.min || 1;

    const innerWidth = VIEW_WIDTH - PADDING.left - PADDING.right;
    const innerHeight = VIEW_HEIGHT - PADDING.top - PADDING.bottom;
    const yFor = (pct: number) => PADDING.top + innerHeight - ((pct - padded.min) / paddedRange) * innerHeight;
    const xFor = (index: number) => PADDING.left + (n === 1 ? 0 : (index / (n - 1)) * innerWidth);

    const positionCoords = position.map((p, i) => ({ x: xFor(i), y: yFor(p.percent) }));
    const benchmarkCoords = benchmark.map((p, i) => ({ x: xFor(i), y: yFor(p.percent) }));
    const zeroY = yFor(0);

    const pathFor = (coords: { x: number; y: number }[]) =>
      coords.map((c, i) => `${i === 0 ? "M" : "L"}${c.x.toFixed(2)},${c.y.toFixed(2)}`).join(" ");

    return { n, position, benchmark, positionCoords, benchmarkCoords, zeroY, pathFor };
  }, [positionPoints, benchmarkPoints]);

  if (!layout) {
    return (
      <div className="flex h-[140px] items-center justify-center text-xs text-ink-faint">
        Not enough overlapping history to compare yet.
      </div>
    );
  }

  const { n, position, benchmark, positionCoords, benchmarkCoords, zeroY, pathFor } = layout;
  const last = n - 1;
  const active = activeIndex ?? last;

  function nearestIndexForClientX(container: SVGSVGElement, clientX: number): number {
    const rect = container.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const viewX = PADDING.left + ratio * (VIEW_WIDTH - PADDING.left - PADDING.right);
    let closest = 0;
    let closestDistance = Infinity;
    positionCoords.forEach(({ x }, index) => {
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
      <div className="mb-1.5 flex items-center gap-3 text-xs">
        <span className="inline-flex items-center gap-1.5 text-ink-secondary">
          <span aria-hidden className="inline-block h-0.5 w-3 rounded-full" style={{ backgroundColor: POSITION_COLOR }} />
          {positionLabel}
        </span>
        <span className="inline-flex items-center gap-1.5 text-ink-secondary">
          <span aria-hidden className="inline-block h-0.5 w-3 rounded-full" style={{ backgroundColor: BENCHMARK_COLOR }} />
          {benchmarkLabel}
        </span>
      </div>

      <svg
        viewBox={`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`}
        className="block w-full touch-none"
        role="img"
        aria-label={`${positionLabel} vs ${benchmarkLabel}, indexed to percent change from ${formatDate(position[0].date)}`}
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
        {/* Zero line: the shared starting point both series are indexed against. */}
        <line
          x1={PADDING.left}
          x2={VIEW_WIDTH - PADDING.right}
          y1={zeroY}
          y2={zeroY}
          stroke="var(--color-border)"
          strokeWidth={1}
        />

        <path d={pathFor(benchmarkCoords)} fill="none" stroke={BENCHMARK_COLOR} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        <path d={pathFor(positionCoords)} fill="none" stroke={POSITION_COLOR} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

        <circle cx={positionCoords[last].x} cy={positionCoords[last].y} r={4} fill={POSITION_COLOR} stroke="var(--color-surface)" strokeWidth={2} />
        <circle cx={benchmarkCoords[last].x} cy={benchmarkCoords[last].y} r={4} fill={BENCHMARK_COLOR} stroke="var(--color-surface)" strokeWidth={2} />

        <text x={positionCoords[last].x} y={PADDING.top - 8} textAnchor="end" className="fill-ink text-[10px] font-medium">
          {formatSignedPercent(position[last].percent, 1)}
        </text>

        <line
          x1={positionCoords[active].x}
          x2={positionCoords[active].x}
          y1={PADDING.top}
          y2={VIEW_HEIGHT - PADDING.bottom}
          stroke="var(--color-border-strong)"
          strokeWidth={1}
          opacity={activeIndex === null ? 0 : 1}
        />
        <circle cx={positionCoords[active].x} cy={positionCoords[active].y} r={4} fill={POSITION_COLOR} stroke="var(--color-surface)" strokeWidth={2} opacity={activeIndex === null ? 0 : 1} />
        <circle cx={benchmarkCoords[active].x} cy={benchmarkCoords[active].y} r={4} fill={BENCHMARK_COLOR} stroke="var(--color-surface)" strokeWidth={2} opacity={activeIndex === null ? 0 : 1} />

        <text x={PADDING.left} y={VIEW_HEIGHT - 6} className="fill-ink-faint text-[9px]">
          {formatDate(position[0].date)}
        </text>
        <text x={VIEW_WIDTH - PADDING.right} y={VIEW_HEIGHT - 6} textAnchor="end" className="fill-ink-faint text-[9px]">
          {formatDate(position[last].date)}
        </text>

        <rect x={PADDING.left} y={0} width={VIEW_WIDTH - PADDING.left - PADDING.right} height={VIEW_HEIGHT} fill="transparent" />
      </svg>

      {activeIndex !== null && (
        <div
          role="status"
          className="pointer-events-none absolute top-0 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-surface px-2 py-1.5 text-xs shadow-sm"
          style={{ left: `${(positionCoords[active].x / VIEW_WIDTH) * 100}%` }}
        >
          <p className="text-ink-faint">{formatDate(position[active].date)}</p>
          <p>
            <span aria-hidden className="mr-1 inline-block h-0.5 w-2.5 align-middle rounded-full" style={{ backgroundColor: POSITION_COLOR }} />
            <span className="font-semibold tabular-nums text-ink">{formatSignedPercent(position[active].percent, 1)}</span>{" "}
            <span className="text-ink-faint">{positionLabel}</span>
          </p>
          <p>
            <span aria-hidden className="mr-1 inline-block h-0.5 w-2.5 align-middle rounded-full" style={{ backgroundColor: BENCHMARK_COLOR }} />
            <span className="font-semibold tabular-nums text-ink">{formatSignedPercent(benchmark[active].percent, 1)}</span>{" "}
            <span className="text-ink-faint">{benchmarkLabel}</span>
          </p>
        </div>
      )}
    </div>
  );
}
