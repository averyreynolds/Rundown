"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useAdvisor } from "./AdvisorProvider";
import { getHoldings, getPositionsFreshness } from "@/lib/fixtures";
import { formatAsOf, formatSignedPercent } from "@/lib/format";
import type { ChatMessage, Citation } from "@/lib/types";

const SUGGESTED_PROMPT = "Should I sell NVDA?";

function buildScopedExchange(symbol: string): ChatMessage[] {
  const holding = getHoldings().find((h) => h.position.symbol === symbol);
  if (!holding) return [];

  const { position, fundamentals, flagReason } = holding;
  const freshness = getPositionsFreshness();
  const direction = position.unrealizedPnlDollars >= 0 ? "up" : "down";

  const lines = [
    `I can't tell you whether to buy or sell — that's not something I do. Here's what's relevant to your ${symbol} position instead:`,
    `${symbol} is ${direction} ${formatSignedPercent(Math.abs(position.unrealizedPnlPercent ?? 0))} since cost basis and makes up ${position.allocationPct.toFixed(1)}% of your portfolio.`,
  ];
  if (fundamentals) {
    lines.push(
      `Its P/E is ${fundamentals.value.priceToEarningsRatio?.toFixed(1)} and trailing ROE is ${((fundamentals.value.returnOnEquityTtm ?? 0) * 100).toFixed(0)}%, per its latest fundamentals.`
    );
  }
  if (flagReason) lines.push(flagReason);

  const citations: Citation[] = [
    { source: "SnapTrade — /portfolio/positions", quote: `${symbol}: allocation_pct=${position.allocationPct}, unrealized_pnl_percent=${position.unrealizedPnlPercent}`, asOf: freshness.asOf },
  ];
  if (fundamentals) {
    citations.push({
      source: "Financial Modeling Prep — /fundamentals/" + symbol,
      quote: `priceToEarningsRatio: ${fundamentals.value.priceToEarningsRatio}, returnOnEquityTTM: ${fundamentals.value.returnOnEquityTtm}`,
      asOf: fundamentals.asOf,
    });
  }

  return [
    { role: "user", text: `Should I sell ${symbol}?` },
    { role: "advisor", text: lines.join(" "), citations },
  ];
}

export function AdvisorPanel() {
  const { isOpen, scopeSymbol, close, open } = useAdvisor();
  const [draft, setDraft] = useState("");
  const [transientNotice, setTransientNotice] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    if (isOpen) document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isOpen, close]);

  const messages = useMemo(() => (scopeSymbol ? buildScopedExchange(scopeSymbol) : []), [scopeSymbol]);

  if (!isOpen) return null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim()) return;
    setTransientNotice(
      "This build runs on synthetic fixture data — live chat connects once /advisor/chat is wired to the backend."
    );
    setDraft("");
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        aria-label="Close advisor panel"
        onClick={close}
        className="absolute inset-0 bg-ink/20 backdrop-blur-[1px]"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Portfolio advisor"
        className="relative flex h-full w-full max-w-md flex-col border-l border-border bg-surface shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <p className="text-sm font-medium text-ink">
              {scopeSymbol ? `About ${scopeSymbol}` : "Ask about your portfolio"}
            </p>
            <p className="text-xs text-ink-faint">Explains what&apos;s relevant — never tells you what to do</p>
          </div>
          <button
            onClick={close}
            aria-label="Close"
            className="rounded-full p-1.5 text-ink-secondary hover:bg-paper hover:text-ink"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
              <path d="M3 3L13 13M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-start justify-between">
              <div className="space-y-3 text-sm text-ink-secondary">
                <p>Ask about a position, a filing, or a recent headline. Answers cite the exact data behind them.</p>
                <button
                  type="button"
                  onClick={() => open("NVDA")}
                  className="rounded-lg border border-border bg-paper px-3 py-2 text-left text-sm text-ink transition-colors hover:border-border-strong"
                >
                  {SUGGESTED_PROMPT}
                </button>
              </div>
            </div>
          ) : (
            <ol className="space-y-4">
              {messages.map((m, i) => (
                <li key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
                  <div
                    className={
                      m.role === "user"
                        ? "max-w-[85%] rounded-2xl rounded-br-sm bg-accent px-3.5 py-2.5 text-sm text-white"
                        : "max-w-[92%] rounded-2xl rounded-bl-sm border border-border bg-paper px-3.5 py-2.5 text-sm text-ink"
                    }
                  >
                    <p className="leading-relaxed">{m.text}</p>
                    {m.citations && m.citations.length > 0 && (
                      <ul className="mt-3 space-y-2 border-t border-border/70 pt-2.5">
                        {m.citations.map((c, ci) => (
                          <li key={ci} className="text-xs text-ink-faint">
                            <span className="font-mono">{c.source}</span>
                            <span className="mx-1">·</span>
                            <span className="italic">&ldquo;{c.quote}&rdquo;</span>
                            <span className="mx-1">·</span>
                            as of {formatAsOf(c.asOf)}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>

        {transientNotice && (
          <p className="border-t border-border bg-paper px-5 py-2.5 text-xs text-ink-faint">{transientNotice}</p>
        )}

        <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-border p-3.5">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Ask a question about your holdings"
            className="flex-1 rounded-full border border-border bg-paper px-4 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
          />
          <button
            type="submit"
            className="rounded-full bg-accent px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-ink"
          >
            Ask
          </button>
        </form>
      </div>
    </div>
  );
}
