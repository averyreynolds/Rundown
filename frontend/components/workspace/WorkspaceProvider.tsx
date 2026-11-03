"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from "react";

import { matchHoldings, type HeldPosition } from "@/lib/match-holdings";
import type { AdvisorFilingRef } from "@/lib/rundown-api";
import type { Citation } from "@/lib/types";

/** Each question stands alone, so only the latest one is ever held here. */
export type AnswerState =
  | { status: "idle" }
  | { status: "asking"; question: string; filingRef: AdvisorFilingRef | null }
  | {
      status: "answered";
      question: string;
      filingRef: AdvisorFilingRef | null;
      answer: string;
      citations: Citation[];
    }
  | { status: "failed"; question: string; filingRef: AdvisorFilingRef | null; message: string };

interface WorkspaceContextValue {
  held: readonly HeldPosition[];
  draft: string;
  setDraft: (draft: string) => void;
  /** Writes a question into the composer without sending it. */
  writeQuestion: (question: string) => void;
  composerRef: RefObject<HTMLInputElement | null>;
  typedSymbols: readonly string[];
  answer: AnswerState;
  ask: (question: string, filingRef?: AdvisorFilingRef) => void;
  reset: () => void;
  hoveredSymbols: readonly string[];
  setHoveredSymbols: (symbols: readonly string[]) => void;
  focusedSymbols: readonly string[];
  selectedSymbol: string | null;
  select: (symbol: string) => void;
  clearSelection: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

/** Calls the same-origin proxy (`app/api/advisor/chat/route.ts`), never the backend directly. */
async function requestAnswer(
  question: string,
  filingRef: AdvisorFilingRef | null,
): Promise<AnswerState> {
  try {
    const res = await fetch("/api/advisor/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // The backend works out which held symbols a question mentions. The typing
      // highlight only ever affects the map, never what an answer is built from.
      body: JSON.stringify({
        question,
        symbols: filingRef ? [filingRef.symbol] : [],
        filingRef: filingRef ?? undefined,
      }),
    });
    const body = (await res.json()) as { answer?: string; citations?: Citation[]; error?: string };
    if (!res.ok || typeof body.answer !== "string") {
      return {
        status: "failed",
        question,
        filingRef,
        message: body.error ?? "Rundown is temporarily unavailable.",
      };
    }
    return { status: "answered", question, filingRef, answer: body.answer, citations: body.citations ?? [] };
  } catch {
    return {
      status: "failed",
      question,
      filingRef,
      message: "Couldn't reach Rundown. Check that the backend is running.",
    };
  }
}

export function WorkspaceProvider({
  held,
  children,
}: {
  held: readonly HeldPosition[];
  children: React.ReactNode;
}) {
  const [draft, setDraft] = useState("");
  const [answer, setAnswer] = useState<AnswerState>({ status: "idle" });
  const [hoveredSymbols, setHoveredSymbols] = useState<readonly string[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const composerRef = useRef<HTMLInputElement | null>(null);
  const isAsking = useRef(false);

  const writeQuestion = useCallback((question: string) => {
    setDraft(question);
    composerRef.current?.focus();
  }, []);

  const ask = useCallback((question: string, filingRef?: AdvisorFilingRef) => {
    if (isAsking.current) return;
    isAsking.current = true;

    const ref = filingRef ?? null;
    setDraft("");
    setHoveredSymbols([]);
    setAnswer({ status: "asking", question, filingRef: ref });
    void requestAnswer(question, ref).then((result) => {
      isAsking.current = false;
      setAnswer(result);
    });
  }, []);

  const reset = useCallback(() => {
    if (isAsking.current) return;
    setAnswer({ status: "idle" });
    setDraft("");
  }, []);

  const select = useCallback((symbol: string) => {
    setSelectedSymbol((current) => (current === symbol ? null : symbol));
  }, []);
  const clearSelection = useCallback(() => setSelectedSymbol(null), []);

  const typedSymbols = useMemo(() => matchHoldings(draft, held), [draft, held]);

  const answerSymbols = useMemo(() => {
    if (answer.status === "idle") return [];
    const inQuestion = matchHoldings(answer.question, held);
    if (answer.status !== "answered") return inQuestion;
    const inAnswer = matchHoldings(answer.answer, held);
    return inAnswer.length > 0 ? inAnswer : inQuestion;
  }, [answer, held]);

  const focusedSymbols = useMemo(() => {
    if (hoveredSymbols.length > 0) return hoveredSymbols;
    return typedSymbols.length > 0 ? typedSymbols : answerSymbols;
  }, [hoveredSymbols, typedSymbols, answerSymbols]);

  const value = useMemo(
    () => ({
      held,
      draft,
      setDraft,
      writeQuestion,
      composerRef,
      typedSymbols,
      answer,
      ask,
      reset,
      hoveredSymbols,
      setHoveredSymbols,
      focusedSymbols,
      selectedSymbol,
      select,
      clearSelection,
    }),
    [
      held,
      draft,
      writeQuestion,
      typedSymbols,
      answer,
      ask,
      reset,
      hoveredSymbols,
      focusedSymbols,
      selectedSymbol,
      select,
      clearSelection,
    ],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}
