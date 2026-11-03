"use client";

import ReactMarkdown from "react-markdown";

import { useWorkspace } from "../workspace/WorkspaceProvider";
import type { AnswerSentence } from "@/lib/answer-stream";

/** Answers are prose the model formats itself (bold, short lists). These keep it in the type scale. */
const MARKDOWN_COMPONENTS = {
  p: ({ children }: { children?: React.ReactNode }) => <p>{children}</p>,
  ul: ({ children }: { children?: React.ReactNode }) => <ul className="list-disc pl-5">{children}</ul>,
  ol: ({ children, start }: { children?: React.ReactNode; start?: number }) => (
    <ol start={start} className="list-decimal pl-5">
      {children}
    </ol>
  ),
  strong: ({ children }: { children?: React.ReactNode }) => (
    <strong className="font-semibold">{children}</strong>
  ),
};

/** Each sentence's `focus` comes from the backend, so a link can only be to a held position. */
export function AnswerSentences({ sentences }: { sentences: readonly AnswerSentence[] }) {
  const { hoveredSymbols, setHoveredSymbols } = useWorkspace();
  const isHovering = hoveredSymbols.length > 0;

  return (
    <div className="flex flex-col gap-0.5">
      {sentences.map(({ text, focus }, index) => {
        const isLinked = focus.some((symbol) => hoveredSymbols.includes(symbol));
        return (
          <div
            key={index}
            tabIndex={0}
            data-linked={isLinked}
            onMouseEnter={() => setHoveredSymbols(focus)}
            onMouseLeave={() => setHoveredSymbols([])}
            onFocus={() => setHoveredSymbols(focus)}
            onBlur={() => setHoveredSymbols([])}
            className={`-mx-3 rounded-lg px-3 py-2 text-base leading-[1.45] transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink motion-reduce:transition-none ${
              isLinked ? "bg-gain-loss-flat text-ink" : isHovering ? "text-ink-secondary" : "text-ink"
            }`}
          >
            <ReactMarkdown components={MARKDOWN_COMPONENTS}>{text}</ReactMarkdown>
          </div>
        );
      })}
    </div>
  );
}
