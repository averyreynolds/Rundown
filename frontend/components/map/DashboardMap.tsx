"use client";

import { useHoldingSelection } from "../holdings/HoldingSelectionProvider";
import { PortfolioMap } from "./PortfolioMap";
import type { PortfolioRollup, SourcedValue } from "@/lib/types";

/**
 * Connects the map to the current dashboard's holding selection. Temporary:
 * the workspace layout replaces this, and tiles then write a question instead.
 */
export function DashboardMap({
  rollup,
  names,
  tableView,
}: {
  rollup: SourcedValue<PortfolioRollup>;
  names: Readonly<Record<string, string>>;
  tableView: React.ReactNode;
}) {
  const { selectedSymbol, select } = useHoldingSelection();

  return (
    <PortfolioMap
      rollup={rollup}
      names={names}
      tableView={tableView}
      focusedSymbols={selectedSymbol ? [selectedSymbol] : []}
      tileAction="View details."
      onTileSelect={select}
    />
  );
}
