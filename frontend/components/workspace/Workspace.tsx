import { AssistantPanel } from "../assistant/AssistantPanel";
import { HoldingDetailPanel } from "../holdings/HoldingDetailPanel";
import { HoldingsList } from "../holdings/HoldingsList";
import { WorkspaceMap, type PortfolioSummaryLine } from "../map/WorkspaceMap";
import { WorkspaceProvider } from "./WorkspaceProvider";
import type { HoldingDetail, PortfolioRollup, SourcedValue } from "@/lib/types";

/** The home screen with positions: the assistant beside the portfolio map. See "Layout" in DESIGN.md. */
export function Workspace({
  holdings,
  rollup,
  summary,
}: {
  holdings: HoldingDetail[];
  /** `null` when the rollup fetch failed: the holdings list stands in for the map. */
  rollup: SourcedValue<PortfolioRollup> | null;
  summary: PortfolioSummaryLine;
}) {
  const held = holdings.map((h) => ({ symbol: h.position.symbol, companyName: h.name }));
  const names = Object.fromEntries(holdings.map((h) => [h.position.symbol, h.name]));
  const largest = holdings.reduce<HoldingDetail | null>(
    (current, h) => (!current || h.position.marketValue > current.position.marketValue ? h : current),
    null,
  );
  const list = <HoldingsList holdings={holdings} />;

  return (
    <WorkspaceProvider held={held}>
      <div className="w-full min-[901px]:grid min-[901px]:h-dvh min-[901px]:grid-cols-[minmax(0,520px)_minmax(0,1fr)] min-[901px]:overflow-hidden">
        <AssistantPanel largestSymbol={largest?.position.symbol ?? null} />
        <div className="min-w-0 border-border bg-surface p-3 max-[900px]:border-t min-[901px]:h-dvh min-[901px]:overflow-y-auto min-[901px]:border-l">
          {rollup ? (
            <WorkspaceMap rollup={rollup} names={names} summary={summary} tableView={list} />
          ) : (
            list
          )}
        </div>
      </div>
      <HoldingDetailPanel holdings={holdings} />
    </WorkspaceProvider>
  );
}
