import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HoldingDetailPanel } from "../holdings/HoldingDetailPanel";
import { HoldingsList } from "../holdings/HoldingsList";
import { WorkspaceMap } from "../map/WorkspaceMap";
import { WorkspaceProvider } from "../workspace/WorkspaceProvider";
import { AssistantPanel } from "./AssistantPanel";
import { getHoldings, getRollupFixture } from "@/lib/fixtures";
import type { Citation } from "@/lib/types";

const fetchMock = vi.fn<typeof fetch>();

function chatResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

function chatCalls() {
  return fetchMock.mock.calls.filter(([url]) => url === "/api/advisor/chat");
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

async function askAndAnswer(user: ReturnType<typeof userEvent.setup>, answer: string) {
  fetchMock.mockResolvedValueOnce(chatResponse({ answer, citations: [] }));
  await user.type(composer(), "Tell me about my holdings{Enter}");
  await screen.findByRole("button", { name: "Start over" });
}

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
    fetchMock.mockImplementation(async () => chatResponse({ error: "no history" }, 404));
    renderWorkspace();

    await user.type(composer(), "UNH");
    await user.click(screen.getByRole("button", { name: "UNH details" }));

    expect(await screen.findByRole("dialog", { name: "UNH details" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.every(([url]) => url !== "/api/advisor/chat")).toBe(true);
  });

  it("keeps the details control reachable when tabbing from its tile", async () => {
    const user = userEvent.setup();
    fetchMock.mockImplementation(async () => chatResponse({ error: "no history" }, 404));
    renderWorkspace();

    tile("UNH").focus();
    await user.tab();

    const details = screen.getByRole("button", { name: "UNH details" });
    expect(details).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("dialog", { name: "UNH details" })).toBeInTheDocument();
  });

  it("clears the tile's focus when tabbing past it", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    tile("UNH").focus();
    await user.tab();
    await user.tab();

    expect(screen.queryByRole("button", { name: "UNH details" })).not.toBeInTheDocument();
    expect(tile("UNH")).not.toHaveAttribute("aria-current");
  });
});

describe("linked sentences", () => {
  const ANSWER = "NVDA makes up most of your gain. The position cost $4,400. UNH is down.";

  it("focuses a sentence's tile on hover, and carries it to a sentence naming nothing", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await askAndAnswer(user, ANSWER);

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
    await askAndAnswer(user, ANSWER);
    const linkOf = (text: string) => screen.getByText(text).closest("[data-linked]");

    await user.hover(tile("NVDA"));

    expect(linkOf("NVDA makes up most of your gain.")).toHaveAttribute("data-linked", "true");
    expect(linkOf("The position cost $4,400.")).toHaveAttribute("data-linked", "true");
    expect(linkOf("UNH is down.")).toHaveAttribute("data-linked", "false");
  });

  it("makes the same links from keyboard focus", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await askAndAnswer(user, ANSWER);

    screen.getByText("UNH is down.").closest<HTMLElement>("[data-linked]")?.focus();
    await waitFor(() => expect(tile("UNH")).toHaveAttribute("aria-current", "true"));
    expect(tile("NVDA")).not.toHaveAttribute("aria-current");

    tile("NVDA").focus();
    await waitFor(() =>
      expect(screen.getByText("NVDA makes up most of your gain.").closest("[data-linked]")).toHaveAttribute(
        "data-linked",
        "true",
      ),
    );
  });

  it("focuses the positions the answer names once nothing is hovered", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    await askAndAnswer(user, ANSWER);

    expect(tile("NVDA")).toHaveAttribute("aria-current", "true");
    expect(tile("UNH")).toHaveAttribute("aria-current", "true");
    expect(tile("AAPL")).toHaveClass("bg-map-dimmed");
  });

  it("renders the model's markdown", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    await askAndAnswer(user, "**Margins fell.** Revenue rose.");

    expect(screen.getByText("Margins fell.").tagName).toBe("STRONG");
  });
});

describe("asking", () => {
  it("doesn't send what the typing highlight matched, leaving scope to the backend", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(chatResponse({ answer: "Here it is.", citations: [] }));
    renderWorkspace();

    await user.type(composer(), "How is nvidia doing?{Enter}");
    await screen.findByText("Here it is.");

    expect(sentBody()).toEqual({ question: "How is nvidia doing?", symbols: [] });
    expect(composer()).toHaveValue("");
  });

  it("sends a directive question unchanged and shows the grounded reframe", async () => {
    const user = userEvent.setup();
    const reframe = "Here's what's relevant to your UNH position. It is 4.4% of the portfolio.";
    fetchMock.mockResolvedValueOnce(chatResponse({ answer: reframe, citations: [] }));
    renderWorkspace();

    await user.type(composer(), "Should I sell UNH?{Enter}");

    expect(await screen.findByText("Here's what's relevant to your UNH position.")).toBeInTheDocument();
    expect(sentBody().question).toBe("Should I sell UNH?");
    expect(screen.getByText(/Never tells you what to do/)).toBeInTheDocument();
  });

  it("asks a starter question directly", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(chatResponse({ answer: "About AAPL.", citations: [] }));
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

  it("sends only one question at a time", async () => {
    const user = userEvent.setup();
    let resolve: (response: Response) => void = () => {};
    fetchMock.mockReturnValueOnce(new Promise((done) => (resolve = done)));
    renderWorkspace();

    await user.type(composer(), "First{Enter}");
    expect(screen.getByText("Thinking…")).toBeInTheDocument();
    await user.type(composer(), "Second{Enter}");

    expect(chatCalls()).toHaveLength(1);
    expect(composer()).toHaveValue("Second");
    resolve(chatResponse({ answer: "Done now.", citations: [] }));
    await screen.findByText("Done now.");
  });

  it("returns to the starters on Start over", async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await askAndAnswer(user, "An answer here.");

    await user.click(screen.getByRole("button", { name: "Start over" }));

    expect(screen.queryByText("An answer here.")).not.toBeInTheDocument();
    expect(screen.getByText(/What do you want to know about your 11 positions/)).toBeInTheDocument();
    expect(tile("AAPL")).not.toHaveClass("bg-map-dimmed");
  });
});

describe("failures", () => {
  it("shows the backend's message and leaves the map usable", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(chatResponse({ error: "The advisor is rate limited." }, 429));
    renderWorkspace();

    await user.type(composer(), "How is UNH?{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("The advisor is rate limited.");
    await user.click(tile("XOM"));
    expect(composer()).toHaveValue("What's relevant to my XOM position?");
  });

  it("says so when the backend can't be reached", async () => {
    const user = userEvent.setup();
    fetchMock.mockRejectedValueOnce(new TypeError("network down"));
    renderWorkspace();

    await user.type(composer(), "How is UNH?{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't reach Rundown");
  });

  it("can ask again after a failure", async () => {
    const user = userEvent.setup();
    fetchMock.mockRejectedValueOnce(new TypeError("network down"));
    renderWorkspace();
    await user.type(composer(), "How is UNH?{Enter}");
    await screen.findByRole("alert");

    fetchMock.mockResolvedValueOnce(chatResponse({ answer: "Back now.", citations: [] }));
    await user.type(composer(), "How is UNH?{Enter}");

    expect(await screen.findByText("Back now.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("filing questions", () => {
  it("sends the filing reference and shows quoted citations", async () => {
    const user = userEvent.setup();
    const citation: Citation = {
      source: "SEC EDGAR 10-Q",
      quote: "Net income declined year over year.",
      asOf: "2026-07-30T06:00:00Z",
    };
    fetchMock.mockImplementation(async (url) =>
      url === "/api/advisor/chat"
        ? chatResponse({ answer: "The XOM 10-Q covers this.", citations: [citation] })
        : chatResponse({ error: "no history" }, 404),
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
