import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingSkeleton } from "@/components/states/LoadingSkeleton";
import { Workspace } from "@/components/workspace/Workspace";
import { loadDashboard } from "@/lib/dashboard";
import { ACCOUNT, getHoldings, getPortfolioTotals, getRollupFixture } from "@/lib/fixtures";
import type { DashboardState } from "@/lib/types";

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

/** The states with no positions to show yet: no assistant or map, just what happened and what's next. */
function NoPositions({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-[720px] flex-1 px-5 py-10 sm:px-6 sm:py-14">
      <PageHeader />
      {children}
    </main>
  );
}

export default async function Home(props: PageProps<"/">) {
  const searchParams = await props.searchParams;
  const preview = resolvePreviewState(searchParams.state);

  if (preview) return <PreviewDashboard state={preview} />;

  const result = await loadDashboard();

  if (result.kind === "empty") return <NoPositions><EmptyState /></NoPositions>;
  if (result.kind === "error") return <NoPositions><ErrorState /></NoPositions>;

  return (
    <Workspace
      holdings={result.holdings}
      rollup={result.rollup}
      summary={{
        totalValue: result.totals.totalValue,
        includesCash: result.account.cash !== null,
        gainPercent: result.totals.unrealizedPnlPercent,
      }}
    />
  );
}

/**
 * `?state=ready|dense|loading|empty|error|stale` design-preview override: renders each
 * UI state on demand from synthetic fixtures, for design QA without a live
 * backend connection. The default (no `state` param) always uses real data.
 */
function PreviewDashboard({ state }: { state: DashboardState }) {
  if (state === "loading") return <NoPositions><LoadingSkeleton /></NoPositions>;
  if (state === "empty") return <NoPositions><EmptyState /></NoPositions>;
  if (state === "error") return <NoPositions><ErrorState /></NoPositions>;

  const isStale = state === "stale";
  const holdings = getHoldings(isStale, state === "dense");
  const totals = getPortfolioTotals(holdings);

  return (
    <Workspace
      holdings={holdings}
      rollup={getRollupFixture(holdings, isStale)}
      summary={{
        totalValue: totals.totalValue,
        includesCash: ACCOUNT.cash !== null,
        gainPercent: totals.unrealizedPnlPercent,
      }}
    />
  );
}
