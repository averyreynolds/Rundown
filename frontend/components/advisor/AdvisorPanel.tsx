"use client";

import { useEffect, useRef, useState } from "react";
import { useAdvisor } from "./AdvisorProvider";
import { formatAsOf } from "@/lib/format";
import type { AdvisorFilingRef } from "@/lib/rundown-api";
import type { ChatMessage } from "@/lib/types";

const GENERAL_SUGGESTED_PROMPT = "What's changed in my portfolio recently?";

/** Calls the same-origin proxy (`app/api/advisor/chat/route.ts`), never the backend directly. */
async function askAdvisor(question: string, symbols: string[], filingRef: AdvisorFilingRef | null): Promise<ChatMessage> {
  try {
    const res = await fetch("/api/advisor/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, symbols, filingRef: filingRef ?? undefined }),
    });
    const body = (await res.json()) as { answer?: string; citations?: ChatMessage["citations"]; error?: string };
    if (!res.ok || typeof body.answer !== "string") {
      return { role: "advisor", text: body.error ?? "The advisor is temporarily unavailable." };
    }
    return { role: "advisor", text: body.answer, citations: body.citations };
  } catch {
    return { role: "advisor", text: "Couldn't reach the advisor — check that the backend is running." };
  }
}

export function AdvisorPanel() {
  const { isOpen, scopeSymbol, scopeFilingRef, close } = useAdvisor();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const lastAutoAskedScope = useRef<string | null>(null);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    if (isOpen) document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isOpen, close]);

  // Opening the panel scoped to a new symbol (e.g. "Ask about this
  // position") starts a fresh, grounded exchange about just that holding.
  useEffect(() => {
    if (!isOpen || !scopeSymbol || lastAutoAskedScope.current === scopeSymbol) return;
    lastAutoAskedScope.current = scopeSymbol;

    const question = `What's relevant to my ${scopeSymbol} position right now?`;
    setMessages([{ role: "user", text: question }]);
    setIsSending(true);
    askAdvisor(question, [scopeSymbol], scopeFilingRef).then((reply) => {
      setMessages((prev) => [...prev, reply]);
      setIsSending(false);
    });
  }, [isOpen, scopeSymbol, scopeFilingRef]);

  if (!isOpen) return null;

  async function submitQuestion(question: string) {
    if (!question || isSending) return;
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setIsSending(true);
    const reply = await askAdvisor(question, scopeSymbol ? [scopeSymbol] : [], scopeFilingRef);
    setMessages((prev) => [...prev, reply]);
    setIsSending(false);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const question = draft.trim();
    setDraft("");
    void submitQuestion(question);
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        aria-label="Close advisor panel"
        onClick={close}
        className="absolute inset-0 bg-ink/20 backdrop-blur-[1px]"
      />
      <div
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
            <p className="text-xs text-ink-faint">
              {scopeFilingRef
                ? `Grounded in filing ${scopeFilingRef.accessionNumber} — never tells you what to do`
                : "Explains what's relevant — never tells you what to do"}
            </p>
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
                  onClick={() => void submitQuestion(GENERAL_SUGGESTED_PROMPT)}
                  className="rounded-lg border border-border bg-paper px-3 py-2 text-left text-sm text-ink transition-colors hover:border-border-strong"
                >
                  {GENERAL_SUGGESTED_PROMPT}
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
              {isSending && (
                <li className="flex justify-start">
                  <div className="max-w-[92%] rounded-2xl rounded-bl-sm border border-border bg-paper px-3.5 py-2.5 text-sm text-ink-faint">
                    Thinking…
                  </div>
                </li>
              )}
            </ol>
          )}
        </div>

        <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-border p-3.5">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={scopeSymbol ? `Ask about ${scopeSymbol}` : "Ask a question about your holdings"}
            disabled={isSending}
            className="flex-1 rounded-full border border-border bg-paper px-4 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={isSending || draft.trim().length === 0}
            className="rounded-full bg-accent px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-ink disabled:opacity-60"
          >
            Ask
          </button>
        </form>
      </div>
    </div>
  );
}
