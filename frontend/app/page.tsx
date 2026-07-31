import { AdvisorPanel } from "@/components/advisor/AdvisorPanel";
import { AdvisorProvider } from "@/components/advisor/AdvisorProvider";
import { AdvisorTrigger } from "@/components/advisor/AdvisorTrigger";
import { HoldingsList } from "@/components/holdings/HoldingsList";
import { PageHeader } from "@/components/PageHeader";
import { PortfolioSummary } from "@/components/PortfolioSummary";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingSkeleton } from "@/components/states/LoadingSkeleton";
import { loadDashboard } from "@/lib/dashboard";
import { ACCOUNT, getHoldings, getPortfolioTotals, getPositionsFreshness } from "@/lib/fixtures";
import type { DashboardState } from "@/lib/types";

type PreviewState = Exclude<DashboardState, "ready">;

function resolvePreviewState(raw: string | string[] | undefined): PreviewState | null {
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (value === "loading" || value === "empty" || value === "error" || value === "stale") return value;
  return null;
}

export default async function Home(props: PageProps<"/">) {
  const searchParams = await props.searchParams;
  const preview = resolvePreviewState(searchParams.state);

  if (preview) return <PreviewDashboard state={preview} />;

  const result = await loadDashboard();

  return (
    <AdvisorProvider>
      <main className="mx-auto w-full max-w-[720px] flex-1 px-5 py-10 sm:px-6 sm:py-14">
        <PageHeader />

        {result.kind === "empty" && <EmptyState />}
        {result.kind === "error" && <ErrorState />}
        {result.kind === "ready" && (
          <>
            <PortfolioSummary
              holdings={result.holdings}
              totals={result.totals}
              account={result.account}
              freshness={result.freshness}
            />
            <HoldingsList holdings={result.holdings} />
          </>
        )}
      </main>

      {result.kind === "ready" && <AdvisorTrigger />}
      <AdvisorPanel />
    </AdvisorProvider>
  );
}

/**
 * `?state=loading|empty|error|stale` design-preview override: renders each
 * UI state on demand from synthetic fixtures, for design QA without a live
 * backend connection. The default (no `state` param) always uses real data.
 */
function PreviewDashboard({ state }: { state: PreviewState }) {
  const holdings = getHoldings();
  const totals = getPortfolioTotals(holdings);
  const freshness = getPositionsFreshness(state === "stale");

  return (
    <AdvisorProvider>
      <main className="mx-auto w-full max-w-[720px] flex-1 px-5 py-10 sm:px-6 sm:py-14">
        <PageHeader />

        {state === "loading" && <LoadingSkeleton />}
        {state === "empty" && <EmptyState />}
        {state === "error" && <ErrorState />}
        {state === "stale" && (
          <>
            <PortfolioSummary holdings={holdings} totals={totals} account={ACCOUNT} freshness={freshness} />
            <HoldingsList holdings={holdings} />
          </>
        )}
      </main>

      {state === "stale" && <AdvisorTrigger />}
      <AdvisorPanel />
    </AdvisorProvider>
  );
}
