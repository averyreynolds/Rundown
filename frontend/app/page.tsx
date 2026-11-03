import { AdvisorPanel } from "@/components/advisor/AdvisorPanel";
import { AdvisorProvider } from "@/components/advisor/AdvisorProvider";
import { AdvisorTrigger } from "@/components/advisor/AdvisorTrigger";
import { DashboardMap } from "@/components/map/DashboardMap";
import { HoldingDetailPanel } from "@/components/holdings/HoldingDetailPanel";
import { HoldingSelectionProvider } from "@/components/holdings/HoldingSelectionProvider";
import { HoldingsList } from "@/components/holdings/HoldingsList";
import { PageHeader } from "@/components/PageHeader";
import { PortfolioSummary } from "@/components/PortfolioSummary";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingSkeleton } from "@/components/states/LoadingSkeleton";
import { loadDashboard } from "@/lib/dashboard";
import { ACCOUNT, getHoldings, getPortfolioTotals, getPositionsFreshness, getRollupFixture } from "@/lib/fixtures";
import type { DashboardState, HoldingDetail, PortfolioRollup, SourcedValue } from "@/lib/types";

function resolvePreviewState(raw: string | string[] | undefined): DashboardState | null {
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (
    value === "ready" ||
    value === "dense" ||
    value === "loading" ||
    value === "empty" ||
    value === "error" ||
    value === "stale"
  ) {
    return value;
  }
  return null;
}

function ReadyLayout({
  holdings,
  children,
}: {
  holdings: HoldingDetail[];
  children: React.ReactNode;
}) {
  return (
    <HoldingSelectionProvider>
      <div className="lg:grid lg:grid-cols-[720px_1fr] lg:items-start lg:gap-8">
        <div className="min-w-0">{children}</div>
        <HoldingDetailPanel holdings={holdings} />
      </div>
    </HoldingSelectionProvider>
  );
}

/** Temporary home for the map, until the workspace layout replaces this page's dashboard. */
function PortfolioSection({
  holdings,
  rollup,
}: {
  holdings: HoldingDetail[];
  rollup: SourcedValue<PortfolioRollup> | null;
}) {
  const list = <HoldingsList holdings={holdings} />;
  if (!rollup) return <div className="mt-10">{list}</div>;

  const names = Object.fromEntries(holdings.map((h) => [h.position.symbol, h.name]));
  return (
    <div className="mt-10 min-[901px]:h-[680px]">
      <DashboardMap rollup={rollup} names={names} tableView={list} />
    </div>
  );
}

export default async function Home(props: PageProps<"/">) {
  const searchParams = await props.searchParams;
  const preview = resolvePreviewState(searchParams.state);

  if (preview) return <PreviewDashboard state={preview} />;

  const result = await loadDashboard();

  return (
    <AdvisorProvider>
      <main
        className={`mx-auto w-full max-w-[720px] flex-1 px-5 py-10 sm:px-6 sm:py-14 ${
          result.kind === "ready" ? "lg:max-w-[1180px]" : ""
        }`}
      >
        <PageHeader />

        {result.kind === "empty" && <EmptyState />}
        {result.kind === "error" && <ErrorState />}
        {result.kind === "ready" && (
          <ReadyLayout holdings={result.holdings}>
            <PortfolioSummary
              holdings={result.holdings}
              totals={result.totals}
              account={result.account}
              freshness={result.freshness}
            />
            <PortfolioSection holdings={result.holdings} rollup={result.rollup} />
          </ReadyLayout>
        )}
      </main>

      {result.kind === "ready" && <AdvisorTrigger />}
      <AdvisorPanel />
    </AdvisorProvider>
  );
}

/**
 * `?state=ready|dense|loading|empty|error|stale` design-preview override: renders each
 * UI state on demand from synthetic fixtures, for design QA without a live
 * backend connection. The default (no `state` param) always uses real data.
 */
function PreviewDashboard({ state }: { state: DashboardState }) {
  const isStale = state === "stale";
  const hasPositions = isStale || state === "ready" || state === "dense";
  const holdings = getHoldings(isStale, state === "dense");
  const totals = getPortfolioTotals(holdings);
  const freshness = getPositionsFreshness(isStale);

  return (
    <AdvisorProvider>
      <main
        className={`mx-auto w-full max-w-[720px] flex-1 px-5 py-10 sm:px-6 sm:py-14 ${
          hasPositions ? "lg:max-w-[1180px]" : ""
        }`}
      >
        <PageHeader />

        {state === "loading" && <LoadingSkeleton />}
        {state === "empty" && <EmptyState />}
        {state === "error" && <ErrorState />}
        {hasPositions && (
          <ReadyLayout holdings={holdings}>
            <PortfolioSummary holdings={holdings} totals={totals} account={ACCOUNT} freshness={freshness} />
            <PortfolioSection holdings={holdings} rollup={getRollupFixture(holdings, isStale)} />
          </ReadyLayout>
        )}
      </main>

      {hasPositions && <AdvisorTrigger />}
      <AdvisorPanel />
    </AdvisorProvider>
  );
}
