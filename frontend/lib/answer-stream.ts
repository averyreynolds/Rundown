/**
 * The client's model of one streamed answer: parsing the backend's events, and a
 * pure reducer from those events to the answer states in the Living Map plan.
 * Everything here has already passed the backend's directive guard. Nothing
 * reaches this code unchecked, which is why a retract can simply replace it.
 */

import type { AdvisorFilingRef } from "./rundown-api";
import type { Citation, MapSizing } from "./types";

export interface SourceReading {
  source: string;
  asOf: string | null;
  status: "used" | "stale" | "unavailable";
}

export interface AnswerSentence {
  text: string;
  focus: string[];
  sizing: MapSizing;
}

export type AnswerStreamEvent =
  | { type: "scope"; symbols: string[] }
  | ({ type: "reading" } & SourceReading)
  | ({ type: "sentence"; citations: Citation[] } & AnswerSentence)
  | { type: "retract"; message: string }
  | { type: "done"; sources: SourceReading[]; citations: Citation[]; followUps: string[] }
  | { type: "interrupted"; reason: "unavailable" | "declined"; citations: Citation[] }
  | { type: "incomplete"; sources: SourceReading[]; citations: Citation[] };

export type AnswerStatus =
  | "idle"
  | "reading"
  | "writing"
  | "done"
  | "stopped"
  | "interrupted"
  | "incomplete"
  | "retracted"
  | "failed";

export interface AnswerState {
  status: AnswerStatus;
  question: string;
  filingRef: AdvisorFilingRef | null;
  scope: string[];
  readings: SourceReading[];
  sentences: AnswerSentence[];
  citations: Citation[];
  sources: SourceReading[];
  followUps: string[];
  /** Why the answer isn't whole, or the fallback that replaced it. */
  message: string | null;
  /** A sizing the user chose, which an answer then leaves alone for that turn. */
  userSizing: MapSizing | null;
}

export type AnswerAction =
  | { type: "start"; question: string; filingRef: AdvisorFilingRef | null }
  | { type: "event"; event: AnswerStreamEvent }
  | { type: "stop" }
  | { type: "streamLost" }
  | { type: "failed"; message: string }
  | { type: "reset" }
  | { type: "setSizing"; sizing: MapSizing };

const STOPPED_MESSAGE = "You stopped this answer, so it's incomplete.";
const LENGTH_LIMIT_MESSAGE = "This answer reached its length limit, so it's incomplete.";
const UNAVAILABLE_MESSAGE = "Rundown couldn't finish this answer, so it's incomplete.";
const UNAVAILABLE_BEFORE_TEXT = "Rundown couldn't answer that. Try asking again.";
const DECLINED_MESSAGE = "The model declined to continue this answer, so it's incomplete.";
const DECLINED_BEFORE_TEXT = "The model declined to answer that. Try rephrasing your question.";

export const INITIAL_ANSWER: AnswerState = {
  status: "idle",
  question: "",
  filingRef: null,
  scope: [],
  readings: [],
  sentences: [],
  citations: [],
  sources: [],
  followUps: [],
  message: null,
  userSizing: null,
};

export function isAnswerRunning(state: AnswerState): boolean {
  return state.status === "reading" || state.status === "writing";
}

export function answerReducer(state: AnswerState, action: AnswerAction): AnswerState {
  switch (action.type) {
    case "start":
      return {
        ...INITIAL_ANSWER,
        status: "reading",
        question: action.question,
        filingRef: action.filingRef,
      };
    case "event":
      return isAnswerRunning(state) ? applyEvent(state, action.event) : state;
    case "stop":
      if (state.status === "reading") return { ...INITIAL_ANSWER };
      if (state.status === "writing") {
        return { ...state, status: "stopped", message: STOPPED_MESSAGE };
      }
      return state;
    case "streamLost":
      return isAnswerRunning(state) ? interrupt(state, "unavailable", []) : state;
    case "failed":
      return { ...state, status: "failed", message: action.message };
    case "reset":
      return { ...INITIAL_ANSWER, userSizing: state.userSizing };
    case "setSizing":
      return { ...state, userSizing: action.sizing };
  }
}

function applyEvent(state: AnswerState, event: AnswerStreamEvent): AnswerState {
  switch (event.type) {
    case "scope":
      return { ...state, scope: event.symbols };
    case "reading": {
      const { source, asOf, status } = event;
      return { ...state, readings: [...state.readings, { source, asOf, status }] };
    }
    case "sentence": {
      const { text, focus, sizing, citations } = event;
      return {
        ...state,
        status: "writing",
        sentences: [...state.sentences, { text, focus, sizing }],
        citations: [...state.citations, ...citations],
      };
    }
    case "retract":
      return {
        ...state,
        status: "retracted",
        sentences: [],
        citations: [],
        sources: [],
        followUps: [],
        message: event.message,
        userSizing: null,
      };
    case "done":
      return {
        ...state,
        status: "done",
        sources: event.sources,
        citations: [...state.citations, ...event.citations],
        followUps: event.followUps,
      };
    case "incomplete":
      return {
        ...state,
        status: "incomplete",
        sources: event.sources,
        citations: [...state.citations, ...event.citations],
        message: LENGTH_LIMIT_MESSAGE,
      };
    case "interrupted":
      return interrupt(state, event.reason, event.citations);
  }
}

function interrupt(
  state: AnswerState,
  reason: "unavailable" | "declined",
  citations: Citation[],
): AnswerState {
  const hasSentences = state.sentences.length > 0;
  const message =
    reason === "declined"
      ? hasSentences
        ? DECLINED_MESSAGE
        : DECLINED_BEFORE_TEXT
      : hasSentences
        ? UNAVAILABLE_MESSAGE
        : UNAVAILABLE_BEFORE_TEXT;
  return {
    ...state,
    status: hasSentences ? "interrupted" : "failed",
    citations: [...state.citations, ...citations],
    message,
  };
}

/** The tiles an answer is about: the current sentence's while writing, then all of them. */
export function answerFocus(state: AnswerState): string[] {
  if (state.status === "writing") return state.sentences.at(-1)?.focus ?? [];
  return [...new Set(state.sentences.flatMap((sentence) => sentence.focus))];
}

export function readingSymbols(state: AnswerState): string[] {
  return state.status === "reading" ? state.scope : [];
}

export function displayedSizing(state: AnswerState): MapSizing {
  return state.userSizing ?? state.sentences.at(-1)?.sizing ?? "value";
}

export function sizingNote(state: AnswerState): string | null {
  return state.userSizing === null && displayedSizing(state) !== "value"
    ? "Rundown changed this to match its answer"
    : null;
}

interface RawReading {
  source: string;
  as_of: string | null;
  status: SourceReading["status"];
}

interface RawCitation {
  source: string;
  quote: string;
  as_of: string;
}

function mapReading(raw: RawReading): SourceReading {
  return { source: raw.source, asOf: raw.as_of, status: raw.status };
}

function mapCitations(raw: RawCitation[] | undefined): Citation[] {
  return (raw ?? []).map((c) => ({ source: c.source, quote: c.quote, asOf: c.as_of }));
}

function mapSizing(raw: unknown): MapSizing {
  return raw === "cost" || raw === "gain" ? raw : "value";
}

function mapEvent(raw: Record<string, unknown>): AnswerStreamEvent | null {
  switch (raw.type) {
    case "scope":
      return { type: "scope", symbols: raw.symbols as string[] };
    case "reading":
      return { type: "reading", ...mapReading(raw as unknown as RawReading) };
    case "sentence":
      return {
        type: "sentence",
        text: raw.text as string,
        focus: raw.focus as string[],
        sizing: mapSizing(raw.sizing),
        citations: mapCitations(raw.citations as RawCitation[]),
      };
    case "retract":
      return { type: "retract", message: raw.message as string };
    case "done":
      return {
        type: "done",
        sources: (raw.sources as RawReading[]).map(mapReading),
        citations: mapCitations(raw.citations as RawCitation[]),
        followUps: raw.follow_ups as string[],
      };
    case "incomplete":
      return {
        type: "incomplete",
        sources: (raw.sources as RawReading[]).map(mapReading),
        citations: mapCitations(raw.citations as RawCitation[]),
      };
    case "interrupted":
      return {
        type: "interrupted",
        reason: raw.reason === "declined" ? "declined" : "unavailable",
        citations: mapCitations(raw.citations as RawCitation[]),
      };
    default:
      return null;
  }
}

/** Parses every complete server-sent event in `buffer`, returning any unfinished remainder. */
export function parseFrames(buffer: string): { events: AnswerStreamEvent[]; rest: string } {
  const frames = buffer.split("\n\n");
  const rest = frames.pop() ?? "";
  const events: AnswerStreamEvent[] = [];

  for (const frame of frames) {
    const data = frame.split("\n").find((line) => line.startsWith("data: "));
    if (!data) continue;
    try {
      const event = mapEvent(JSON.parse(data.slice("data: ".length)) as Record<string, unknown>);
      if (event) events.push(event);
    } catch {
      // A frame that can't be parsed carries nothing that was checked to show.
    }
  }
  return { events, rest };
}

export async function* readAnswerEvents(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<AnswerStreamEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) return;
      // `stream: true` holds back a multibyte character split across two chunks.
      const parsed = parseFrames(buffer + decoder.decode(value, { stream: true }));
      buffer = parsed.rest;
      yield* parsed.events;
    }
  } finally {
    reader.releaseLock();
  }
}
