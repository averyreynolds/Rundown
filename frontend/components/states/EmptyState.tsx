"use client";

import { useState } from "react";

export function EmptyState() {
  const [status, setStatus] = useState<"idle" | "connecting" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function handleConnect() {
    setStatus("connecting");
    setError(null);
    try {
      const res = await fetch("/api/portfolio/connect", { method: "POST" });
      const body = (await res.json()) as { portalUrl?: string; error?: string };
      if (!res.ok || !body.portalUrl) {
        throw new Error(body.error ?? "Could not start the SnapTrade connection.");
      }
      window.open(body.portalUrl, "_blank", "noopener,noreferrer");
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Could not start the SnapTrade connection.");
    }
  }

  return (
    <section className="rounded-2xl border border-border bg-surface p-8 text-center sm:p-12">
      <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-paper">
        <svg width="18" height="18" viewBox="0 0 16 16" fill="none" aria-hidden>
          <rect x="2" y="4" width="12" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.3" className="text-ink-faint" />
          <path d="M2 6.5h12" stroke="currentColor" strokeWidth="1.3" className="text-ink-faint" />
        </svg>
      </div>
      <h2 className="mt-4 text-base font-medium text-ink">No brokerage connected yet</h2>
      <p className="mx-auto mt-1.5 max-w-sm text-sm text-ink-secondary">
        Connect a brokerage account through SnapTrade to see your positions, fundamentals, and news here.
      </p>
      <button
        onClick={handleConnect}
        disabled={status === "connecting"}
        className="mt-5 rounded-full bg-ink px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-ink/85 disabled:opacity-60"
      >
        {status === "connecting" ? "Opening SnapTrade…" : "Connect your brokerage"}
      </button>
      {error && <p className="mx-auto mt-3 max-w-sm text-xs text-status-error">{error}</p>}
    </section>
  );
}
