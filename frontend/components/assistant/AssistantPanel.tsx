"use client";

import { useWorkspace, type AnswerState } from "../workspace/WorkspaceProvider";
import { AnswerSentences } from "./AnswerSentences";
import { Composer } from "./Composer";
import { formatAsOf } from "@/lib/format";
import type { Citation } from "@/lib/types";

function Starters({ largestSymbol }: { largestSymbol: string | null }) {
  const { held, ask } = useWorkspace();
  const positionCount = new Set(held.map((position) => position.symbol)).size;
  const starters = [
    ...(largestSymbol ? [`What's relevant to my ${largestSymbol} position?`] : []),
    "What's changed in my portfolio recently?",
  ];

  return (
    <section className="flex flex-1 flex-col justify-center gap-6">
      <h2 className="text-balance text-[2.5rem] font-semibold leading-[1.06] tracking-[-0.03em] text-ink">
        What do you want to know about your {positionCount} position{positionCount === 1 ? "" : "s"}?
      </h2>
      <div className="flex flex-col gap-2">
        <p className="text-xs font-medium text-ink-secondary">Start with a question</p>
        {starters.map((starter) => (
          <button
            key={starter}
            type="button"
            onClick={() => ask(starter)}
            className="min-h-11 rounded-2xl border border-border bg-surface px-3.5 py-2 text-left text-sm text-ink transition-colors hover:border-border-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            {starter}
          </button>
        ))}
      </div>
    </section>
  );
}

function Citations({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <section aria-label="Sources" className="border-t border-border pt-3">
      <p className="text-xs font-medium text-ink-secondary">Sources</p>
      <ul className="mt-2 flex flex-col gap-3">
        {citations.map((citation, index) => (
          <li key={index} className="text-xs text-ink-faint">
            <p className="font-mono">
              {citation.source} · as of {formatAsOf(citation.asOf)}
            </p>
            <blockquote className="mt-1 border-l-2 border-border pl-2 italic leading-relaxed text-ink-secondary">
              &ldquo;{citation.quote}&rdquo;
            </blockquote>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Turn({ answer }: { answer: Exclude<AnswerState, { status: "idle" }> }) {
  return (
    <section className="flex flex-col gap-4" aria-live="polite">
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-ink px-3 py-2 text-[15px] leading-[1.4] text-white">
          {answer.question}
        </p>
      </div>
      {answer.filingRef && (
        <p className="font-mono text-xs text-ink-secondary">
          Grounded in filing {answer.filingRef.accessionNumber}
        </p>
      )}
      {answer.status === "asking" && <p className="text-sm text-ink-faint">Thinking…</p>}
      {answer.status === "failed" && (
        <p role="alert" className="rounded-lg bg-status-error-soft px-3 py-2 text-sm text-status-error">
          {answer.message}
        </p>
      )}
      {answer.status === "answered" && (
        <>
          <AnswerSentences answer={answer.answer} />
          <Citations citations={answer.citations} />
        </>
      )}
    </section>
  );
}

export function AssistantPanel({ largestSymbol }: { largestSymbol: string | null }) {
  const { answer, reset } = useWorkspace();

  return (
    <main className="flex min-w-0 flex-col max-[900px]:min-h-dvh min-[901px]:h-dvh">
      <header className="flex min-h-11 items-center justify-between gap-4 px-4 pt-4 min-[901px]:px-8">
        <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Rundown</h1>
        {answer.status === "answered" || answer.status === "failed" ? (
          <button
            type="button"
            onClick={reset}
            className="min-h-11 text-[13px] text-ink-secondary hover:text-ink hover:underline"
          >
            Start over
          </button>
        ) : null}
      </header>
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-4 py-6 min-[901px]:px-8">
        {answer.status === "idle" ? <Starters largestSymbol={largestSymbol} /> : <Turn answer={answer} />}
      </div>
      <div className="sticky bottom-0 border-t border-border bg-paper px-4 pb-4 pt-3 min-[901px]:px-8">
        <Composer />
      </div>
    </main>
  );
}
