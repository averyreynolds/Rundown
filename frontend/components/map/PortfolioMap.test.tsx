import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { HoldingsList } from "../holdings/HoldingsList";
import { WorkspaceProvider } from "../workspace/WorkspaceProvider";
import { PortfolioMap } from "./PortfolioMap";
import { getHoldings, getRollupFixture } from "@/lib/fixtures";
import { formatCurrency, formatSignedCurrency } from "@/lib/format";
import type { PortfolioRollup, PositionRollup, SourcedValue } from "@/lib/types";

const SUMMARY = { totalValue: 5000, includesCash: true, gainPercent: 33.33 };
const NAMES = { NVDA: "NVIDIA Corp.", UNH: "UnitedHealth Group Inc." };

function rollupOf(positions: PositionRollup[], isStale = false): SourcedValue<PortfolioRollup> {
  return {
    value: { positions, totalMarketValue: 4000, totalCostBasis: 3000, netGainDollars: 1000 },
    source: "SnapTrade",
    asOf: "2026-07-30T13:05:00Z",
    isStale,
  };
}

function row(overrides: Partial<PositionRollup> & { symbol: string }): PositionRollup {
  return {
    quantity: 10,
    marketValue: 2000,
    costBasis: 1500,
    gainDollars: 500,
    gainPercent: 33.33,
    shareOfValuePct: 50,
    shareOfCostPct: 50,
    shareOfNetGainPct: 50,
    ...overrides,
  };
}

const NVDA = row({
  symbol: "NVDA",
  marketValue: 3000,
  costBasis: 1000,
  gainDollars: 2000,
  gainPercent: 200,
  shareOfValuePct: 75,
  shareOfCostPct: 33.3,
});
const UNH = row({
  symbol: "UNH",
  marketValue: 1000,
  costBasis: 2000,
  gainDollars: -1000,
  gainPercent: -50,
  shareOfValuePct: 25,
  shareOfCostPct: 66.7,
});

function renderMap(
  props: Partial<React.ComponentProps<typeof PortfolioMap>> = {},
  positions: PositionRollup[] = [NVDA, UNH],
) {
  return render(
    <PortfolioMap
      rollup={rollupOf(positions)}
      names={NAMES}
      summary={SUMMARY}
      tableView={<p>table view</p>}
      tileAction="View details."
      {...props}
    />,
  );
}

const tile = (symbol: string) => screen.getByRole("button", { name: new RegExp(`^${symbol},`) });

describe("PortfolioMap", () => {
  it("shows ticker, signed figure, and arrow, with the fill matching the percent", () => {
    renderMap();

    const nvda = tile("NVDA");
    expect(nvda).toHaveTextContent("NVDA");
    expect(nvda).toHaveTextContent("75.0%");
    expect(nvda).toHaveTextContent("▲ +200.0%");
    expect(nvda).toHaveClass("bg-gain-3");

    const unh = tile("UNH");
    expect(unh).toHaveTextContent("▼ −50.0%");
    expect(unh).toHaveClass("bg-loss-3");
  });

  it("names the full figures for assistive technology", () => {
    renderMap();

    expect(tile("UNH")).toHaveAccessibleName(
      "UNH, UnitedHealth Group Inc.. 25.0% of portfolio, −50.0% since cost, −$1,000.00. View details.",
    );
  });

  it("changes tile sizes and labels by gain or loss, and marks the control as pressed", async () => {
    const user = userEvent.setup();
    renderMap();
    const before = tile("UNH").style.width;
    const beforeHeight = tile("UNH").style.height;

    const gain = screen.getByRole("button", { name: "Gain or loss" });
    expect(gain).toHaveAttribute("aria-pressed", "false");
    await user.click(gain);

    expect(gain).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Value" })).toHaveAttribute("aria-pressed", "false");
    expect(tile("UNH")).toHaveTextContent("▼ −$1,000.00");
    expect(tile("NVDA")).toHaveTextContent("▲ +$2,000.00");
    expect(`${tile("UNH").style.width} ${tile("UNH").style.height}`).not.toBe(
      `${before} ${beforeHeight}`,
    );
  });

  it("labels share of cost when sized by cost", async () => {
    const user = userEvent.setup();
    renderMap();

    await user.click(screen.getByRole("button", { name: "Cost" }));

    expect(tile("NVDA")).toHaveTextContent("33.3% of cost");
  });

  it("gives focused gain and loss tiles the same outline", () => {
    renderMap({ focusedSymbols: ["NVDA", "UNH"] });
    const outlineOf = (element: HTMLElement) =>
      [...element.classList].filter((name) => name.startsWith("shadow-"));

    expect(outlineOf(tile("NVDA"))).toEqual(["shadow-[inset_0_0_0_3px_var(--color-ink)]"]);
    expect(outlineOf(tile("UNH"))).toEqual(outlineOf(tile("NVDA")));
    expect(tile("UNH")).toHaveClass("bg-loss-3");
  });

  it("dims tiles outside the focus by removing their fill", () => {
    renderMap({ focusedSymbols: ["NVDA"] });

    expect(tile("NVDA")).toHaveAttribute("aria-current", "true");
    expect(tile("UNH")).toHaveClass("bg-map-dimmed");
    expect(tile("UNH")).not.toHaveClass("bg-loss-3");
  });

  it("treats a position with no cost basis as unknown, not a gain", async () => {
    const user = userEvent.setup();
    const noBasis = row({
      symbol: "XFER",
      costBasis: 0,
      gainDollars: 500,
      gainPercent: null,
      shareOfCostPct: null,
    });
    renderMap({}, [NVDA, noBasis]);

    expect(tile("XFER")).toHaveClass("bg-gain-loss-flat");
    expect(tile("XFER")).not.toHaveTextContent("▲");
    expect(tile("XFER")).toHaveAccessibleName(expect.stringContaining("no cost basis recorded"));

    await user.click(screen.getByRole("button", { name: "Gain or loss" }));
    expect(tile("XFER")).toHaveTextContent("No cost basis");
    expect(tile("XFER")).not.toHaveTextContent("$500");
  });

  it("reports which tile was activated", async () => {
    const user = userEvent.setup();
    const onTileSelect = vi.fn();
    renderMap({ onTileSelect });

    await user.click(tile("UNH"));

    expect(onTileSelect).toHaveBeenCalledWith("UNH");
  });

  it("offers details only on a focused tile, without triggering the tile itself", async () => {
    const user = userEvent.setup();
    const onTileSelect = vi.fn();
    const onTileDetails = vi.fn();
    renderMap({ focusedSymbols: ["UNH"], onTileSelect, onTileDetails });

    expect(screen.queryByRole("button", { name: "NVDA details" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "UNH details" }));

    expect(onTileDetails).toHaveBeenCalledWith("UNH");
    expect(onTileSelect).not.toHaveBeenCalled();
  });

  it("reports hover and keyboard focus on a tile", async () => {
    const user = userEvent.setup();
    const onTileHover = vi.fn();
    renderMap({ onTileHover });

    await user.hover(tile("UNH"));
    expect(onTileHover).toHaveBeenLastCalledWith("UNH");
    await user.unhover(tile("UNH"));
    expect(onTileHover).toHaveBeenLastCalledWith(null);

    tile("NVDA").focus();
    expect(onTileHover).toHaveBeenLastCalledWith("NVDA");
  });

  it("summarizes the whole portfolio under the map", () => {
    renderMap();

    expect(screen.getByText(/\$5,000\.00 total including cash/)).toBeInTheDocument();
    expect(screen.getByText(/\+33\.33%\) since cost/)).toBeInTheDocument();
  });

  it("doesn't claim cash is included when none is known", () => {
    renderMap({ summary: { ...SUMMARY, includesCash: false } });

    expect(screen.queryByText(/including cash/)).not.toBeInTheDocument();
  });

  it("shows source and as-of, with no stale chip on fresh data", () => {
    renderMap();

    expect(screen.getByText(/SnapTrade · as of/)).toBeInTheDocument();
    expect(screen.queryByText("Data is stale")).not.toBeInTheDocument();
  });

  it("shows the stale chip and the older as-of on stale data", () => {
    const stale = getRollupFixture(getHoldings(true), true);
    renderMap({ rollup: stale });

    expect(screen.getByText("Data is stale")).toBeInTheDocument();
    expect(screen.getByText(/as of Jul 28/)).toBeInTheDocument();
  });

  it("shows the legend, and no minimum-size note when every tile is proportional", () => {
    renderMap();

    expect(screen.getByRole("img", { name: /change since cost/ })).toBeInTheDocument();
    expect(screen.queryByText(/minimum size/)).not.toBeInTheDocument();
  });

  it("says so when small positions are drawn at the minimum size", () => {
    const holdings = getHoldings(false, true);
    renderMap({ rollup: getRollupFixture(holdings) });

    expect(screen.getByText("Small positions are shown at a minimum size.")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /View details/ })).toHaveLength(30);
  });

  it("renders only the table when there are no positions", () => {
    renderMap({}, []);

    expect(screen.getByText("table view")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Portfolio map" })).not.toBeInTheDocument();
  });

  it("shows the same positions and figures in the table view", async () => {
    const user = userEvent.setup();
    const holdings = getHoldings();
    const rollup = getRollupFixture(holdings);
    render(
      <WorkspaceProvider held={[]}>
        <PortfolioMap
          rollup={rollup}
          names={Object.fromEntries(holdings.map((h) => [h.position.symbol, h.name]))}
          summary={SUMMARY}
          tableView={<HoldingsList holdings={holdings} />}
          tileAction="View details."
        />
      </WorkspaceProvider>,
    );

    const area = screen.getByTestId("map-area");
    const table = screen.getByTestId("table-area");
    expect(table).toHaveClass("min-[901px]:hidden");
    expect(within(area).getAllByRole("button")).toHaveLength(rollup.value.positions.length);

    await user.click(screen.getByRole("button", { name: "table" }));

    expect(table).not.toHaveClass("min-[901px]:hidden");
    expect(area).toHaveClass("hidden");
    expect(area).not.toHaveClass("min-[901px]:block");
    expect(screen.queryByRole("group", { name: "Size tiles by" })).not.toBeInTheDocument();

    for (const { position } of holdings) {
      const listRow = within(table).getByRole("button", {
        name: new RegExp(`^${position.symbol.replace(".", "\\.")} —`),
      });
      const rolledUp = rollup.value.positions.find((c) => c.symbol === position.symbol);
      expect(rolledUp).toBeDefined();
      expect(listRow).toHaveTextContent(formatCurrency(rolledUp?.marketValue ?? Number.NaN));
      expect(listRow).toHaveTextContent(formatSignedCurrency(rolledUp?.gainDollars ?? Number.NaN));
    }
  });
});
