import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HoldingDetailPanel } from "../holdings/HoldingDetailPanel";
import { HoldingsList } from "../holdings/HoldingsList";
import { WorkspaceMap } from "../map/WorkspaceMap";
import { WorkspaceProvider } from "../workspace/WorkspaceProvider";
import { AssistantPanel } from "./AssistantPanel";
import { getHoldings, getRollupFixture } from "@/lib/fixtures";

const STREAM_URL = "/api/advisor/chat/stream";
const fetchMock = vi.fn<typeof fetch>();
const encoder = new TextEncoder();

type RawEvent = Record<string, unknown> & { type: string };

const frame = (event: RawEvent) => `event: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`;

const sentence = (
  text: string,
  focus: string[] = [],
  sizing = "value",
  citations: unknown[] = [],
): RawEvent => ({ type: "sentence", text, focus, sizing, citations });

const DONE: RawEvent = { type: "done", sources: [], citations: [], follow_ups: [] };

/** A stream the test feeds by hand, so it can assert mid-answer states. */
function openStream() {
  let controller: ReadableStreamDefaultController<Uint8Array> | undefined;
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
    cancel() {
      controller = undefined;
    },
  });
  fetchMock.mockImplementationOnce(async (_url, init) => {
    init?.signal?.addEventListener("abort", () => {
      try {
        controller?.error(new DOMException("Aborted", "AbortError"));
      } catch {
        // Already closed.
      }
    });
    return new Response(body, { status: 200 });
  });
  return {
    send: (...events: RawEvent[]) =>
      act(async () => {
        for (const event of events) {
          try {
            controller?.enqueue(encoder.encode(frame(event)));
          } catch {
            // The client has already gone: exactly what a late event looks like.
          }
        }
        await new Promise((resolve) => setTimeout(resolve, 0));
      }),
    close: () =>
      act(async () => {
        controller?.close();
        await new Promise((resolve) => setTimeout(resolve, 0));
      }),
  };
}

function respondWith(...events: RawEvent[]) {
  fetchMock.mockResolvedValueOnce(new Response(events.map(frame).join(""), { status: 200 }));
}

function chatCalls() {
  return fetchMock.mock.calls.filter(([url]) => url === STREAM_URL);
}

function sentBody(call = 0) {
  return JSON.parse(chatCalls()[call][1]?.body as string) as Record<string, unknown>;
}

function renderWorkspace() {
  const holdings = getHoldings();
  return render(
    <WorkspaceProvider
      held={holdings.map((h) => ({ symbol: h.position.symbol, companyName: h.name }))}
    >
      <AssistantPanel largestSymbol="AAPL" />
      <WorkspaceMap
        rollup={getRollupFixture(holdings)}
        names={Object.fromEntries(holdings.map((h) => [h.position.symbol, h.name]))}
        summary={{ totalValue: 64000, includesCash: true, gainPercent: 15.21 }}
        tableView={<HoldingsList holdings={holdings} />}
      />
      <HoldingDetailPanel holdings={holdings} />
    </WorkspaceProvider>,
  );
}

const tile = (symbol: string) => screen.getByRole("button", { name: new RegExp(`^${symbol},`) });
const composer = () => screen.getByRole("textbox", { name: "Ask Rundown about your portfolio" });
const sizingButton = (name: string) => screen.getByRole("button", { name });

async function askAndAnswer(user: ReturnType<typeof userEvent.setup>, ...events: RawEvent[]) {
  respondWith(...events, DONE);
  await user.type(composer(), "Tell me about my holdings{Enter}");
  await screen.findByRole("button", { name: "Start over" });
}

const LINKED_ANSWER = [
  sentence("NVDA makes up most of your gain.", ["NVDA"]),
  sentence("The position cost $4,400.", ["NVDA"]),
  sentence("UNH is down.", ["UNH"]),
];

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("typing", () => {
  it("focuses a named position's tile and shows it in scope, with no network request", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    expect(screen.getByText("All 11 positions")).toBeInTheDocument();

    await user.type(composer(), "nvidia");

    expect(tile("NVDA")).toHaveAttribute("aria-current", "true");
    expect(tile("AAPL")).toHaveClass("bg-map-dimmed");
    expect(screen.getByText("About NVDA")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns to no focus when the draft no longer names a position", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    await user.type(composer(), "nvda");
    await user.clear(composer());

    expect(tile("NVDA")).not.toHaveAttribute("aria-current");
    expect(tile("AAPL")).not.toHaveClass("bg-map-dimmed");
  });
});

describe("tiles", () => {
  it("writes a question into the composer without sending it", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(tile("UNH"));

    expect(composer()).toHaveValue("What's relevant to my UNH position?");
    expect(composer()).toHaveFocus();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("opens the holding's details from the control on a focused tile", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async () => Response.json({ error: "no history" }, { status: 404 }));
    renderWorkspace();

    await user.type(composer(), "UNH");
    await user.click(screen.getByRole("button", { name: "UNH details" }));

    expect(await screen.findByRole("dialog", { name: "UNH details" })).toBeInTheDocument();
    expect(chatCalls()).toHaveLength(0);
  });

  it("keeps the details control reachable when tabbing from its tile", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async () => Response.json({ error: "no history" }, { status: 404 }));
    renderWorkspace();

    act(() => tile("UNH").focus());
    await user.tab();

    const details = screen.getByRole("button", { name: "UNH details" });
    expect(details).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("dialog", { name: "UNH details" })).toBeInTheDocument();
  });

  it("clears the tile's focus when tabbing past it", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    act(() => tile("UNH").focus());
    await user.tab();
    await user.tab();

    expect(screen.queryByRole("button", { name: "UNH details" })).not.toBeInTheDocument();
    expect(tile("UNH")).not.toHaveAttribute("aria-current");
  });
});

describe("linked sentences", () => {
  it("focuses a sentence's tile on hover, using the backend's focus", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await askAndAnswer(user, ...LINKED_ANSWER);

    await user.hover(screen.getByText("UNH is down."));
    expect(tile("UNH")).toHaveAttribute("aria-current", "true");
    expect(tile("NVDA")).not.toHaveAttribute("aria-current");

    await user.hover(screen.getByText("The position cost $4,400."));
    expect(tile("NVDA")).toHaveAttribute("aria-current", "true");
    expect(tile("UNH")).not.toHaveAttribute("aria-current");
  });

  it("highlights a tile's sentences on hover", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await askAndAnswer(user, ...LINKED_ANSWER);
    const linkOf = (text: string) => screen.getByText(text).closest("[data-linked]");

    await user.hover(tile("NVDA"));

    expect(linkOf("NVDA makes up most of your gain.")).toHaveAttribute("data-linked", "true");
    expect(linkOf("The position cost $4,400.")).toHaveAttribute("data-linked", "true");
    expect(linkOf("UNH is down.")).toHaveAttribute("data-linked", "false");
  });

  it("makes the same links from keyboard focus", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await askAndAnswer(user, ...LINKED_ANSWER);

    act(() => screen.getByText("UNH is down.").closest<HTMLElement>("[data-linked]")?.focus());
    await waitFor(() => expect(tile("NVDA")).not.toHaveAttribute("aria-current"));
    expect(tile("UNH")).toHaveAttribute("aria-current", "true");

    act(() => tile("NVDA").focus());
    await waitFor(() =>
      expect(
        screen.getByText("NVDA makes up most of your gain.").closest("[data-linked]"),
      ).toHaveAttribute("data-linked", "true"),
    );
  });

  it("renders the model's markdown", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    await askAndAnswer(user, sentence("**Margins fell.**"));

    expect(screen.getByText("Margins fell.").tagName).toBe("STRONG");
  });
});

describe("a streamed answer", () => {
  it("moves through reading and writing to done, with the map following each sentence", async () => {
    const user = userEvent.setup();
    const stream = openStream();
    renderWorkspace();

    await user.type(composer(), "How is my gain?{Enter}");
    expect(screen.getByText("Reading your data…")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop" })).toBeInTheDocument();

    await stream.send({ type: "scope", symbols: ["NVDA", "UNH"] });
    expect(tile("NVDA")).toHaveClass("map-tile-reading");
    expect(tile("AAPL")).not.toHaveClass("map-tile-reading");

    await stream.send({
      type: "reading",
      source: "SnapTrade positions",
      as_of: "2026-07-30T13:05:00Z",
      status: "used",
    });
    expect(
      within(screen.getByRole("list", { name: "What Rundown read" })).getByText(
        /SnapTrade positions · as of/,
      ),
    ).toBeInTheDocument();

    await stream.send(sentence("NVDA makes up 46% of your gain.", ["NVDA"], "gain"));
    expect(screen.getByText("NVDA makes up 46% of your gain.")).toBeInTheDocument();
    expect(tile("NVDA")).not.toHaveClass("map-tile-reading");
    expect(tile("NVDA")).toHaveAttribute("aria-current", "true");
    expect(tile("UNH")).toHaveClass("bg-map-dimmed");
    expect(sizingButton("Gain or loss")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Rundown changed this to match its answer")).toBeInTheDocument();

    await stream.send(sentence("UNH cost $3,960.", ["UNH"], "cost"));
    expect(tile("UNH")).toHaveAttribute("aria-current", "true");
    expect(tile("NVDA")).not.toHaveAttribute("aria-current");
    expect(sizingButton("Cost")).toHaveAttribute("aria-pressed", "true");

    await stream.send({ ...DONE, follow_ups: ["What's relevant to my AAPL position?"] });
    await stream.close();

    expect(screen.getByRole("button", { name: "Ask" })).toBeInTheDocument();
    expect(tile("NVDA")).toHaveAttribute("aria-current", "true");
    expect(tile("UNH")).toHaveAttribute("aria-current", "true");
    expect(
      screen.getByRole("button", { name: "What's relevant to my AAPL position?" }),
    ).toBeInTheDocument();
  });

  it("shows a source it couldn't reach, and stale data as stale", async () => {
    const user = userEvent.setup();
    const stream = openStream();
    renderWorkspace();

    await user.type(composer(), "How?{Enter}");
    await stream.send(
      { type: "reading", source: "Finnhub news", as_of: null, status: "unavailable" },
      {
        type: "reading",
        source: "SnapTrade positions",
        as_of: "2026-07-28T09:40:00Z",
        status: "stale",
      },
    );

    expect(screen.getByText("Finnhub news couldn't be reached")).toBeInTheDocument();
    expect(screen.getByText(/SnapTrade positions · as of .* · stale/)).toBeInTheDocument();
  });

  it("replaces everything with only the fallback on a retract", async () => {
    const user = userEvent.setup();
    const stream = openStream();
    renderWorkspace();

    await user.type(composer(), "Should I sell UNH?{Enter}");
    await stream.send(sentence("UNH is down.", ["UNH"], "gain"));
    expect(screen.getByText("UNH is down.")).toBeInTheDocument();

    await stream.send({ type: "retract", message: "I can't share that response as phrased." });

    expect(screen.queryByText("UNH is down.")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("I can't share that response as phrased.");
    expect(tile("UNH")).not.toHaveAttribute("aria-current");
    expect(sizingButton("Value")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Ask" })).toBeInTheDocument();
  });

  it("returns to idle when stopped during reading, aborting the request", async () => {
    const user = userEvent.setup();
    openStream();
    renderWorkspace();

    await user.type(composer(), "How?{Enter}");
    await user.click(screen.getByRole("button", { name: "Stop" }));

    expect(chatCalls()[0][1]?.signal?.aborted).toBe(true);
    expect(screen.getByText(/What do you want to know/)).toBeInTheDocument();
  });

  it("keeps released sentences, labeled incomplete, when stopped during writing", async () => {
    const user = userEvent.setup();
    const stream = openStream();
    renderWorkspace();

    await user.type(composer(), "How?{Enter}");
    await stream.send(sentence("A whole sentence."));
    await user.click(screen.getByRole("button", { name: "Stop" }));

    expect(chatCalls()[0][1]?.signal?.aborted).toBe(true);
    expect(screen.getByText("A whole sentence.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/incomplete/);
  });

  it("aborts the old stream for a new question and ignores its late events", async () => {
    const user = userEvent.setup();
    const first = openStream();
    renderWorkspace();

    await user.type(composer(), "First?{Enter}");
    await first.send(sentence("From the first answer.", ["NVDA"]));
    expect(screen.getByText("From the first answer.")).toBeInTheDocument();

    fetchMock.mockImplementation(async () => Response.json({}, { status: 404 }));
    act(() => tile("XOM").focus());
    await user.tab();
    await user.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog", { name: "XOM details" });
    // Opened only now, so the panel's own chart requests don't consume it.
    const second = openStream();
    await user.click(within(dialog).getByRole("button", { name: /Ask about this position/ }));

    expect(chatCalls()[0][1]?.signal?.aborted).toBe(true);
    expect(screen.queryByText("From the first answer.")).not.toBeInTheDocument();

    await first.send(sentence("A late straggler."));
    await second.send(sentence("From the second answer.", ["XOM"]));

    expect(screen.queryByText("A late straggler.")).not.toBeInTheDocument();
    expect(screen.getByText("From the second answer.")).toBeInTheDocument();
  });

  it("stops following the answer's sizing after a manual change", async () => {
    const user = userEvent.setup();
    const stream = openStream();
    renderWorkspace();

    await user.type(composer(), "How?{Enter}");
    await stream.send(sentence("A.", [], "gain"));
    await user.click(sizingButton("Value"));
    await stream.send(sentence("B.", [], "cost"));

    expect(sizingButton("Value")).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText(/changed this to match/)).not.toBeInTheDocument();
  });

  it("asks a follow-up as a new question", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    respondWith(sentence("First."), { ...DONE, follow_ups: ["How much of my gain comes from UNH?"] });
    await user.type(composer(), "How?{Enter}");

    respondWith(sentence("Second."), DONE);
    await user.click(await screen.findByRole("button", { name: "How much of my gain comes from UNH?" }));

    expect(await screen.findByText("Second.")).toBeInTheDocument();
    expect(screen.queryByText("First.")).not.toBeInTheDocument();
    expect(sentBody(1).question).toBe("How much of my gain comes from UNH?");
  });
});

describe("asking", () => {
  it("doesn't send what the typing highlight matched, leaving scope to the backend", async () => {
    const user = userEvent.setup();
    respondWith(sentence("Here it is."), DONE);
    renderWorkspace();

    await user.type(composer(), "How is nvidia doing?{Enter}");
    await screen.findByText("Here it is.");

    expect(sentBody()).toEqual({ question: "How is nvidia doing?", symbols: [] });
    expect(composer()).toHaveValue("");
  });

  it("sends a directive question unchanged and shows the grounded reframe", async () => {
    const user = userEvent.setup();
    respondWith(sentence("Here's what's relevant to your UNH position.", ["UNH"]), DONE);
    renderWorkspace();

    await user.type(composer(), "Should I sell UNH?{Enter}");

    expect(await screen.findByText("Here's what's relevant to your UNH position.")).toBeInTheDocument();
    expect(sentBody().question).toBe("Should I sell UNH?");
    expect(screen.getByText(/Never tells you what to do/)).toBeInTheDocument();
  });

  it("asks a starter question directly", async () => {
    const user = userEvent.setup();
    respondWith(sentence("About AAPL."), DONE);
    renderWorkspace();

    await user.click(screen.getByRole("button", { name: "What's relevant to my AAPL position?" }));

    await screen.findByText("About AAPL.");
    expect(sentBody().question).toBe("What's relevant to my AAPL position?");
  });

  it("offers no directive wording in its starters", () => {
    renderWorkspace();

    const starters = within(screen.getByRole("main"))
      .getAllByRole("button")
      .map((button) => button.textContent ?? "");
    for (const starter of starters) {
      expect(starter).not.toMatch(/\b(should|buy|sell|trim)\b/i);
    }
  });

  it("returns to the starters on Start over", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await askAndAnswer(user, sentence("An answer here.", ["AAPL"]));

    await user.click(screen.getByRole("button", { name: "Start over" }));

    expect(screen.queryByText("An answer here.")).not.toBeInTheDocument();
    expect(screen.getByText(/What do you want to know about your 11 positions/)).toBeInTheDocument();
    expect(tile("AAPL")).not.toHaveAttribute("aria-current");
  });
});

describe("failures", () => {
  it("shows the backend's message and leaves the map usable", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      Response.json({ error: "The advisor is rate limited." }, { status: 429 }),
    );
    renderWorkspace();

    await user.type(composer(), "How is UNH?{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("The advisor is rate limited.");
    await user.click(tile("XOM"));
    expect(composer()).toHaveValue("What's relevant to my XOM position?");
  });

  it("says so when the proxy can't be reached", async () => {
    const user = userEvent.setup();
    fetchMock.mockRejectedValueOnce(new TypeError("network down"));
    renderWorkspace();

    await user.type(composer(), "How is UNH?{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("couldn't answer");
  });

  it("labels an answer whose stream was lost partway, keeping its sentences", async () => {
    const user = userEvent.setup();
    const stream = openStream();
    renderWorkspace();

    await user.type(composer(), "How?{Enter}");
    await stream.send(sentence("A whole sentence."));
    await stream.close();

    expect(screen.getByText("A whole sentence.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/couldn't finish/);
    expect(screen.getByRole("button", { name: "Ask" })).toBeInTheDocument();
  });

  it("labels an answer that hit the length limit", async () => {
    const user = userEvent.setup();
    respondWith(sentence("A sentence."), { type: "incomplete", sources: [], citations: [] });
    renderWorkspace();

    await user.type(composer(), "How?{Enter}");

    expect(await screen.findByRole("status")).toHaveTextContent(/length limit/);
    expect(screen.getByText("A sentence.")).toBeInTheDocument();
  });

  it("can ask again after a failure", async () => {
    const user = userEvent.setup();
    fetchMock.mockRejectedValueOnce(new TypeError("network down"));
    renderWorkspace();
    await user.type(composer(), "How is UNH?{Enter}");
    await screen.findByRole("alert");

    respondWith(sentence("Back now."), DONE);
    await user.type(composer(), "How is UNH?{Enter}");

    expect(await screen.findByText("Back now.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("filing questions", () => {
  it("sends the filing reference and shows quoted citations", async () => {
    const user = userEvent.setup();
    const citation = {
      source: "SEC EDGAR 10-Q",
      quote: "Net income declined year over year.",
      as_of: "2026-07-30T06:00:00Z",
    };
    fetchMock.mockImplementation(async (url) =>
      url === STREAM_URL
        ? new Response(
            [sentence("The XOM 10-Q covers this.", ["XOM"], "value", [citation]), DONE]
              .map(frame)
              .join(""),
            { status: 200 },
          )
        : Response.json({ error: "no history" }, { status: 404 }),
    );
    renderWorkspace();

    await user.type(composer(), "XOM");
    await user.click(screen.getByRole("button", { name: "XOM details" }));
    const dialog = await screen.findByRole("dialog", { name: "XOM details" });
    await user.click(within(dialog).getByRole("button", { name: /Ask about this position/ }));

    expect(await screen.findByText("The XOM 10-Q covers this.")).toBeInTheDocument();
    expect(sentBody()).toEqual({
      question: "What's relevant to my XOM position right now?",
      symbols: ["XOM"],
      filingRef: { symbol: "XOM", accessionNumber: "0000034088-26-000045" },
    });
    expect(composer()).toHaveValue("");

    const sources = screen.getByRole("region", { name: "Sources" });
    expect(within(sources).getByText(/SEC EDGAR 10-Q · as of/)).toBeInTheDocument();
    expect(within(sources).getByText(/Net income declined year over year/)).toBeInTheDocument();
    expect(screen.getByText("Grounded in filing 0000034088-26-000045")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
