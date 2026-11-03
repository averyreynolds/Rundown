"use client";

import { useMemo } from "react";
import ReactMarkdown from "react-markdown";

import { useWorkspace } from "../workspace/WorkspaceProvider";
import { matchHoldings, type HeldPosition } from "@/lib/match-holdings";
import { splitSentences } from "@/lib/split-sentences";

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

interface LinkedSentence {
  text: string;
  symbols: readonly string[];
}

/** A sentence that names no position stays with the last one that did. */
function linkSentences(answer: string, held: readonly HeldPosition[]): LinkedSentence[] {
  let previous: readonly string[] = [];
  return splitSentences(answer).map((text) => {
    const named = matchHoldings(text, held);
    const symbols = named.length > 0 ? named : previous;
    previous = symbols;
    return { text, symbols };
  });
}

export function AnswerSentences({ answer }: { answer: string }) {
  const { held, hoveredSymbols, setHoveredSymbols } = useWorkspace();
  const sentences = useMemo(() => linkSentences(answer, held), [answer, held]);
  const isHovering = hoveredSymbols.length > 0;

  return (
    <div className="flex flex-col gap-0.5">
      {sentences.map(({ text, symbols }, index) => {
        const isLinked = symbols.some((symbol) => hoveredSymbols.includes(symbol));
        return (
          <div
            key={index}
            tabIndex={0}
            data-linked={isLinked}
            onMouseEnter={() => setHoveredSymbols(symbols)}
            onMouseLeave={() => setHoveredSymbols([])}
            onFocus={() => setHoveredSymbols(symbols)}
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
