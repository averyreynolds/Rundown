"use client";

import { useEffect, useState } from "react";
import { PnlValue } from "../PnlValue";
import { StatusChip } from "../StatusChip";
import { IndexedCompareChart } from "./IndexedCompareChart";
import { PriceChart } from "./PriceChart";
import { WindowSelector } from "./WindowSelector";
import { formatAsOf } from "@/lib/format";
import type { PriceHistoryWindow, PriceWindow, SourcedValue } from "@/lib/types";

const DEFAULT_WINDOW: PriceWindow = "1M";
const BENCHMARK_SYMBOL = "SPY";
const BENCHMARK_LABEL = "S&P 500 (SPY)";

const WINDOW_LABEL: Record<PriceWindow, string> = {
  "1D": "today",
  "1W": "this week",
  "1M": "this month",
  "3M": "these 3 months",
  YTD: "year to date",
  "1Y": "this year",
  ALL: "over the cached history",
};

type FetchState = SourcedValue<PriceHistoryWindow> | "loading" | "error";

async function fetchWindow(symbol: string, window: PriceWindow): Promise<SourcedValue<PriceHistoryWindow> | "error"> {
  try {
    const res = await fetch(`/api/fundamentals/${encodeURIComponent(symbol)}/price-history?window=${window}`);
    if (!res.ok) return "error";
    return (await res.json()) as SourcedValue<PriceHistoryWindow>;
  } catch {
    return "error";
  }
}

/** Selectable-window price chart + today's move, for one held symbol. */
export function PositionChart({
  symbol,
  quantity,
  costBasisPerShare,
}: {
  symbol: string;
  quantity: number;
  costBasisPerShare: number;
}) {
  const [window, setWindow] = useState<PriceWindow>(DEFAULT_WINDOW);
  const [chart, setChart] = useState<FetchState>("loading");
  const [today, setToday] = useState<FetchState>("loading");
  const [compareToBenchmark, setCompareToBenchmark] = useState(false);
  const [benchmark, setBenchmark] = useState<FetchState>("loading");

  useEffect(() => {
    let cancelled = false;
    fetchWindow(symbol, window).then((result) => {
      if (!cancelled) setChart(result);
    });
    return () => {
      cancelled = true;
    };
  }, [symbol, window]);

  useEffect(() => {
    let cancelled = false;
    fetchWindow(symbol, "1D").then((result) => {
      if (!cancelled) setToday(result);
    });
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  useEffect(() => {
    if (!compareToBenchmark) return;
    let cancelled = false;
    fetchWindow(BENCHMARK_SYMBOL, window).then((result) => {
      if (!cancelled) setBenchmark(result);
    });
    return () => {
      cancelled = true;
    };
  }, [compareToBenchmark, window]);

  function handleWindowChange(next: PriceWindow) {
    setChart("loading");
    if (compareToBenchmark) setBenchmark("loading");
    setWindow(next);
  }

  function handleToggleBenchmark() {
    setBenchmark("loading");
    setCompareToBenchmark((current) => !current);
  }

  const todayChange = today !== "loading" && today !== "error" ? today.value.priceChangeDollars : null;
  const todayPercent = today !== "loading" && today !== "error" ? today.value.priceChangePercent : null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-ink-faint">Today</p>
          {today === "loading" ? (
            <p className="text-sm text-ink-faint">—</p>
          ) : today === "error" || todayChange === null ? (
            <p className="text-sm text-ink-faint">Not available</p>
          ) : (
            <PnlValue dollars={todayChange * quantity} percent={todayPercent} />
          )}
        </div>
        <WindowSelector value={window} onChange={handleWindowChange} />
      </div>

      {chart === "loading" && <div className="flex h-[140px] items-center justify-center text-xs text-ink-faint">Loading chart…</div>}

      {chart === "error" && (
        <div className="flex h-[140px] items-center justify-center text-xs text-ink-faint">Price history not available.</div>
      )}

      {chart !== "loading" && chart !== "error" && (
        <>
          {compareToBenchmark ? (
            benchmark === "loading" ? (
              <div className="flex h-[140px] items-center justify-center text-xs text-ink-faint">Loading {BENCHMARK_LABEL}…</div>
            ) : benchmark === "error" ? (
              <div className="flex h-[140px] items-center justify-center text-xs text-ink-faint">{BENCHMARK_LABEL} not available.</div>
            ) : (
              <IndexedCompareChart
                positionLabel={symbol}
                positionPoints={chart.value.points}
                benchmarkLabel={BENCHMARK_LABEL}
                benchmarkPoints={benchmark.value.points}
              />
            )
          ) : (
            <PriceChart points={chart.value.points} costBasisPerShare={costBasisPerShare} />
          )}

          <button
            type="button"
            onClick={handleToggleBenchmark}
            aria-pressed={compareToBenchmark}
            className={`text-xs font-medium ${compareToBenchmark ? "text-accent-ink" : "text-ink-faint hover:text-ink-secondary"}`}
          >
            {compareToBenchmark ? "✓ Comparing to S&P 500" : "Compare to S&P 500"}
          </button>

          <div className="flex items-center justify-between">
            <p className="text-xs text-ink-secondary">
              Change {WINDOW_LABEL[window]}:{" "}
              {chart.value.priceChangeDollars === null ? (
                <span className="text-ink-faint">not enough history</span>
              ) : (
                <PnlValue dollars={chart.value.priceChangeDollars * quantity} percent={chart.value.priceChangePercent} />
              )}
            </p>
            <div className="flex items-center gap-1.5 text-xs text-ink-faint">
              {chart.isStale && <StatusChip tone="stale">Stale</StatusChip>}
              <span>
                {chart.source} · as of {formatAsOf(chart.asOf)}
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
