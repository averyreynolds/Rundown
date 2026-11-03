import { describe, expect, it } from "vitest";

import {
  INITIAL_ANSWER,
  answerFocus,
  answerReducer,
  displayedSizing,
  isAnswerRunning,
  parseFrames,
  readAnswerEvents,
  readingSymbols,
  sizingNote,
  type AnswerAction,
  type AnswerState,
  type AnswerStreamEvent,
} from "./answer-stream";

const sentence = (
  text: string,
  focus: string[] = [],
  sizing: "value" | "cost" | "gain" = "value",
): AnswerStreamEvent => ({ type: "sentence", text, focus, sizing, citations: [] });

const RETRACT: AnswerStreamEvent = { type: "retract", message: "Fallback." };

function run(...actions: AnswerAction[]): AnswerState {
  return actions.reduce(answerReducer, INITIAL_ANSWER);
}

const start: AnswerAction = { type: "start", question: "How is NVDA?", filingRef: null };
const event = (e: AnswerStreamEvent): AnswerAction => ({ type: "event", event: e });

describe("answerReducer", () => {
  it("moves from idle through reading and writing to done, with focus following the sentence", () => {
    const reading = run(start, event({ type: "scope", symbols: ["NVDA", "UNH"] }));
    expect(reading.status).toBe("reading");
    expect(isAnswerRunning(reading)).toBe(true);
    expect(readingSymbols(reading)).toEqual(["NVDA", "UNH"]);

    const first = answerReducer(reading, event(sentence("NVDA is up.", ["NVDA"], "gain")));
    expect(first.status).toBe("writing");
    expect(readingSymbols(first)).toEqual([]);
    expect(answerFocus(first)).toEqual(["NVDA"]);
    expect(displayedSizing(first)).toBe("gain");

    const second = answerReducer(first, event(sentence("UNH is down.", ["UNH"], "cost")));
    expect(answerFocus(second)).toEqual(["UNH"]);
    expect(displayedSizing(second)).toBe("cost");

    const done = answerReducer(
      second,
      event({ type: "done", sources: [], citations: [], followUps: ["Next?"] }),
    );
    expect(done.status).toBe("done");
    expect(isAnswerRunning(done)).toBe(false);
    expect(done.followUps).toEqual(["Next?"]);
    expect(answerFocus(done)).toEqual(["NVDA", "UNH"]);
  });

  it("collects reading steps in order", () => {
    const state = run(
      start,
      event({ type: "reading", source: "SnapTrade positions", asOf: "2026-07-30", status: "used" }),
      event({ type: "reading", source: "Finnhub news", asOf: null, status: "unavailable" }),
    );

    expect(state.readings.map((r) => r.status)).toEqual(["used", "unavailable"]);
  });

  it("gathers citations from sentences and from the final event", () => {
    const quote = (text: string) => ({ source: "SEC EDGAR", quote: text, asOf: "2026-07-30" });
    const state = run(
      start,
      event({ type: "sentence", text: "A.", focus: [], sizing: "value", citations: [quote("One")] }),
      event({ type: "done", sources: [], citations: [quote("Two")], followUps: [] }),
    );

    expect(state.citations.map((c) => c.quote)).toEqual(["One", "Two"]);
  });

  it("replaces everything with the fallback on a retract", () => {
    const state = run(
      start,
      event(sentence("NVDA is up.", ["NVDA"], "gain")),
      { type: "setSizing", sizing: "cost" },
      event(RETRACT),
    );

    expect(state.status).toBe("retracted");
    expect(state.sentences).toEqual([]);
    expect(state.citations).toEqual([]);
    expect(state.message).toBe("Fallback.");
    expect(answerFocus(state)).toEqual([]);
    expect(displayedSizing(state)).toBe("value");
    expect(isAnswerRunning(state)).toBe(false);
  });

  it("returns to idle when stopped during reading", () => {
    expect(run(start, event({ type: "scope", symbols: ["NVDA"] }), { type: "stop" }).status).toBe(
      "idle",
    );
  });

  it("keeps released sentences, labeled, when stopped during writing", () => {
    const state = run(start, event(sentence("NVDA is up.", ["NVDA"])), { type: "stop" });

    expect(state.status).toBe("stopped");
    expect(state.sentences.map((s) => s.text)).toEqual(["NVDA is up."]);
    expect(state.message).toBeTruthy();
    expect(answerFocus(state)).toEqual(["NVDA"]);
  });

  it("ignores late events once stopped", () => {
    const stopped = run(start, event(sentence("NVDA is up.")), { type: "stop" });

    const late = [
      sentence("Late."),
      RETRACT,
      { type: "done", sources: [], citations: [], followUps: ["Next?"] },
    ] as AnswerStreamEvent[];
    for (const e of late) {
      expect(answerReducer(stopped, event(e))).toBe(stopped);
    }
  });

  it("starts clean, dropping everything from the previous answer", () => {
    const state = run(
      start,
      event(sentence("NVDA is up.", ["NVDA"], "gain")),
      { type: "setSizing", sizing: "cost" },
      event({ type: "done", sources: [], citations: [], followUps: ["Next?"] }),
      { type: "start", question: "Again?", filingRef: null },
    );

    expect(state.status).toBe("reading");
    expect(state.question).toBe("Again?");
    expect(state.sentences).toEqual([]);
    expect(state.followUps).toEqual([]);
    expect(displayedSizing(state)).toBe("value");
  });

  it("stops following the answer's sizing after a manual change", () => {
    const state = run(
      start,
      event(sentence("A.", [], "gain")),
      { type: "setSizing", sizing: "cost" },
      event(sentence("B.", [], "value")),
      event(sentence("C.", [], "gain")),
    );

    expect(displayedSizing(state)).toBe("cost");
    expect(sizingNote(state)).toBeNull();
  });

  it("notes when the answer changed sizing, but not when it stayed on value", () => {
    expect(sizingNote(run(start, event(sentence("A.", [], "value"))))).toBeNull();
    expect(sizingNote(run(start, event(sentence("A.", [], "gain"))))).toBe(
      "Rundown changed this to match its answer",
    );
  });

  it("remembers a sizing chosen while idle until the next question", () => {
    const idle = run({ type: "setSizing", sizing: "gain" });
    expect(displayedSizing(idle)).toBe("gain");
    expect(displayedSizing(answerReducer(idle, start))).toBe("value");
  });

  it("labels an interruption after some sentences, keeping them", () => {
    const state = run(
      start,
      event(sentence("A whole sentence.")),
      event({ type: "interrupted", reason: "unavailable", citations: [] }),
    );

    expect(state.status).toBe("interrupted");
    expect(state.sentences).toHaveLength(1);
    expect(state.message).toMatch(/couldn't finish/i);
  });

  it("treats an interruption before any sentence as a failure", () => {
    const state = run(start, event({ type: "interrupted", reason: "unavailable", citations: [] }));

    expect(state.status).toBe("failed");
    expect(state.message).toBeTruthy();
  });

  it("says when the model declined, rather than claiming an outage", () => {
    const state = run(start, event({ type: "interrupted", reason: "declined", citations: [] }));

    expect(state.message).toMatch(/declined/i);
  });

  it("labels an answer cut off at the length limit", () => {
    const state = run(
      start,
      event(sentence("A sentence.")),
      event({ type: "incomplete", sources: [], citations: [] }),
    );

    expect(state.status).toBe("incomplete");
    expect(state.message).toMatch(/length limit/i);
    expect(state.sentences).toHaveLength(1);
  });

  it("treats a stream that ends with no final event as interrupted", () => {
    expect(run(start, event(sentence("A.")), { type: "streamLost" }).status).toBe("interrupted");
    expect(run(start, { type: "streamLost" }).status).toBe("failed");
  });

  it("ignores a lost stream once the answer already finished", () => {
    const done = run(
      start,
      event(sentence("A.")),
      event({ type: "done", sources: [], citations: [], followUps: [] }),
    );

    expect(answerReducer(done, { type: "streamLost" })).toBe(done);
  });

  it("records a failure from the proxy", () => {
    const state = run(start, { type: "failed", message: "Rate limited." });

    expect(state.status).toBe("failed");
    expect(state.message).toBe("Rate limited.");
    expect(state.question).toBe("How is NVDA?");
  });

  it("returns to idle on reset, keeping a sizing the user chose", () => {
    const state = run(start, event(sentence("A.")), { type: "setSizing", sizing: "cost" }, {
      type: "reset",
    });

    expect(state.status).toBe("idle");
    expect(state.sentences).toEqual([]);
    expect(displayedSizing(state)).toBe("cost");
  });
});

describe("parseFrames", () => {
  const frame = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;

  it("maps backend events to the frontend's casing", () => {
    const text = [
      frame("reading", { type: "reading", source: "SnapTrade", as_of: "2026-07-30", status: "used" }),
      frame("done", {
        type: "done",
        sources: [{ source: "SnapTrade", as_of: "2026-07-30", status: "stale" }],
        citations: [{ source: "EDGAR", quote: "Q", as_of: "2026-07-30" }],
        follow_ups: ["Next?"],
      }),
    ].join("");

    expect(parseFrames(text)).toEqual({
      rest: "",
      events: [
        { type: "reading", source: "SnapTrade", asOf: "2026-07-30", status: "used" },
        {
          type: "done",
          sources: [{ source: "SnapTrade", asOf: "2026-07-30", status: "stale" }],
          citations: [{ source: "EDGAR", quote: "Q", asOf: "2026-07-30" }],
          followUps: ["Next?"],
        },
      ],
    });
  });

  it("keeps an unfinished frame for the next chunk", () => {
    const whole = frame("scope", { type: "scope", symbols: ["NVDA"] });
    const { events, rest } = parseFrames(`${whole}event: scope\ndata: {"ty`);

    expect(events).toEqual([{ type: "scope", symbols: ["NVDA"] }]);
    expect(rest).toBe('event: scope\ndata: {"ty');
  });

  it("drops unknown events and malformed frames rather than failing the answer", () => {
    const text = `event: x\ndata: {"type":"mystery"}\n\nevent: y\ndata: not json\n\n`;

    expect(parseFrames(text)).toEqual({ events: [], rest: "" });
  });

  it("only accepts a sizing the map supports", () => {
    const text = frame("sentence", {
      type: "sentence",
      text: "A.",
      focus: [],
      sizing: "vibes",
      citations: [],
    });

    expect(parseFrames(text).events).toEqual([
      { type: "sentence", text: "A.", focus: [], sizing: "value", citations: [] },
    ]);
  });
});

describe("readAnswerEvents", () => {
  it("yields events across chunk boundaries, including a split multibyte character", async () => {
    const whole = new TextEncoder().encode(
      'event: sentence\ndata: {"type":"sentence","text":"Up — a lot.","focus":[],"sizing":"gain","citations":[]}\n\n',
    );
    const middle = whole.indexOf(0xe2) + 1;
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(whole.slice(0, middle));
        controller.enqueue(whole.slice(middle));
        controller.close();
      },
    });

    const events: AnswerStreamEvent[] = [];
    for await (const e of readAnswerEvents(body)) events.push(e);

    expect(events).toEqual([
      { type: "sentence", text: "Up — a lot.", focus: [], sizing: "gain", citations: [] },
    ]);
  });
});
