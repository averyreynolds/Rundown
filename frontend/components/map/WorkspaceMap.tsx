"use client";

import { useWorkspace } from "../workspace/WorkspaceProvider";
import { PortfolioMap, type PortfolioSummaryLine } from "./PortfolioMap";
import type { PortfolioRollup, SourcedValue } from "@/lib/types";

export type { PortfolioSummaryLine };

/** Connects the map to the workspace: typing, sentences, and tiles all share one focus. */
export function WorkspaceMap({
  rollup,
  names,
  summary,
  tableView,
}: {
  rollup: SourcedValue<PortfolioRollup>;
  names: Readonly<Record<string, string>>;
  summary: PortfolioSummaryLine;
  tableView: React.ReactNode;
}) {
  const {
    focusedSymbols,
    readingSymbols,
    sizing,
    setSizing,
    sizingNote,
    setHoveredSymbols,
    writeQuestion,
    select,
  } = useWorkspace();

  return (
    <PortfolioMap
      rollup={rollup}
      names={names}
      summary={summary}
      tableView={tableView}
      focusedSymbols={focusedSymbols}
      readingSymbols={readingSymbols}
      sizing={sizing}
      onSizingChange={setSizing}
      sizingNote={sizingNote}
      tileAction="Ask about this position."
      onTileSelect={(symbol) => writeQuestion(`What's relevant to my ${symbol} position?`)}
      onTileHover={(symbol) => setHoveredSymbols(symbol ? [symbol] : [])}
      onTileDetails={select}
    />
  );
}
