"use client";

import { useWorkspace } from "../workspace/WorkspaceProvider";

export function Composer() {
  const { draft, setDraft, composerRef, typedSymbols, held, answer, ask } = useWorkspace();
  const isAsking = answer.status === "asking";
  const question = draft.trim();

  const scope =
    typedSymbols.length > 0
      ? `About ${typedSymbols.join(", ")}`
      : `All ${new Set(held.map((position) => position.symbol)).size} positions`;

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (question && !isAsking) ask(question);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div className="flex flex-col gap-0.5 rounded-2xl border border-border-strong bg-surface py-1 pl-4 pr-1.5 focus-within:border-ink">
        <label htmlFor="ask-rundown" className="sr-only">
          Ask Rundown about your portfolio
        </label>
        <input
          id="ask-rundown"
          ref={composerRef}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask about a position, a filing, or a headline"
          autoComplete="off"
          className="h-11 w-full bg-transparent text-base text-ink outline-none placeholder:text-ink-faint"
        />
        <div className="flex items-center justify-between gap-2 pb-1">
          <p className="truncate font-mono text-xs text-ink-secondary">{scope}</p>
          <button
            type="submit"
            disabled={isAsking || question.length === 0}
            className="h-10 shrink-0 rounded-full bg-ink px-5 text-sm font-medium text-white transition-colors hover:bg-ink/85 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:opacity-60"
          >
            Ask
          </button>
        </div>
      </div>
      <p className="text-center text-xs text-ink-faint">
        Explains what&apos;s relevant. Never tells you what to do.
      </p>
    </form>
  );
}
