"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type RefObject,
} from "react";

import {
  INITIAL_ANSWER,
  answerFocus,
  answerReducer,
  displayedSizing,
  readAnswerEvents,
  readingSymbols,
  sizingNote,
  type AnswerAction,
  type AnswerState,
} from "@/lib/answer-stream";
import { matchHoldings, type HeldPosition } from "@/lib/match-holdings";
import type { AdvisorFilingRef } from "@/lib/rundown-api";
import type { MapSizing } from "@/lib/types";

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
  stop: () => void;
  reset: () => void;
  hoveredSymbols: readonly string[];
  setHoveredSymbols: (symbols: readonly string[]) => void;
  focusedSymbols: readonly string[];
  readingSymbols: readonly string[];
  sizing: MapSizing;
  setSizing: (sizing: MapSizing) => void;
  sizingNote: string | null;
  selectedSymbol: string | null;
  select: (symbol: string) => void;
  clearSelection: () => void;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

/**
 * Streams one answer into `dispatch` through the same-origin proxy
 * (`app/api/advisor/chat/stream/route.ts`), never the backend directly.
 * `isCurrent` turns false as soon as a newer question or Stop replaces this one,
 * so anything still in flight from it is dropped.
 */
async function streamAnswer(
  question: string,
  filingRef: AdvisorFilingRef | null,
  signal: AbortSignal,
  isCurrent: () => boolean,
  dispatch: (action: AnswerAction) => void,
): Promise<void> {
  try {
    const res = await fetch("/api/advisor/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // The backend works out which held symbols a question mentions. The typing
      // highlight only ever affects the map, never what an answer is built from.
      body: JSON.stringify({
        question,
        symbols: filingRef ? [filingRef.symbol] : [],
        filingRef: filingRef ?? undefined,
      }),
      signal,
    });

    if (!res.ok || !res.body) {
      const body = (await res.json().catch(() => null)) as { error?: string } | null;
      if (isCurrent()) {
        dispatch({
          type: "failed",
          message: body?.error ?? "Rundown is temporarily unavailable.",
        });
      }
      return;
    }

    for await (const event of readAnswerEvents(res.body)) {
      if (!isCurrent()) return;
      dispatch({ type: "event", event });
    }
    if (isCurrent()) dispatch({ type: "streamLost" });
  } catch {
    // An abort is deliberate, and `isCurrent` is already false for one.
    if (!isCurrent()) return;
    dispatch({ type: "streamLost" });
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
  const [answer, dispatch] = useReducer(answerReducer, INITIAL_ANSWER);
  const [hoveredSymbols, setHoveredSymbols] = useState<readonly string[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const composerRef = useRef<HTMLInputElement | null>(null);
  const currentRun = useRef<AbortController | null>(null);

  const cancelCurrent = useCallback(() => {
    currentRun.current?.abort();
    currentRun.current = null;
  }, []);

  useEffect(() => cancelCurrent, [cancelCurrent]);

  const writeQuestion = useCallback((question: string) => {
    setDraft(question);
    composerRef.current?.focus();
  }, []);

  const ask = useCallback(
    (question: string, filingRef?: AdvisorFilingRef) => {
      cancelCurrent();
      const run = new AbortController();
      currentRun.current = run;

      const ref = filingRef ?? null;
      setDraft("");
      setHoveredSymbols([]);
      dispatch({ type: "start", question, filingRef: ref });
      void streamAnswer(question, ref, run.signal, () => currentRun.current === run, dispatch);
    },
    [cancelCurrent],
  );

  const stop = useCallback(() => {
    cancelCurrent();
    dispatch({ type: "stop" });
  }, [cancelCurrent]);

  const reset = useCallback(() => {
    cancelCurrent();
    dispatch({ type: "reset" });
    setDraft("");
  }, [cancelCurrent]);

  const setSizing = useCallback((sizing: MapSizing) => {
    dispatch({ type: "setSizing", sizing });
  }, []);

  const select = useCallback((symbol: string) => {
    setSelectedSymbol((current) => (current === symbol ? null : symbol));
  }, []);
  const clearSelection = useCallback(() => setSelectedSymbol(null), []);

  const typedSymbols = useMemo(() => matchHoldings(draft, held), [draft, held]);
  const answerSymbols = useMemo(() => answerFocus(answer), [answer]);
  const reading = useMemo(() => readingSymbols(answer), [answer]);

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
      stop,
      reset,
      hoveredSymbols,
      setHoveredSymbols,
      focusedSymbols,
      readingSymbols: reading,
      sizing: displayedSizing(answer),
      setSizing,
      sizingNote: sizingNote(answer),
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
      stop,
      reset,
      hoveredSymbols,
      focusedSymbols,
      reading,
      setSizing,
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
