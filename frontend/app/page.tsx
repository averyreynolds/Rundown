import { AdvisorPanel } from "@/components/advisor/AdvisorPanel";
import { AdvisorProvider } from "@/components/advisor/AdvisorProvider";
import { AdvisorTrigger } from "@/components/advisor/AdvisorTrigger";
import { HoldingsList } from "@/components/holdings/HoldingsList";
import { PageHeader } from "@/components/PageHeader";
import { PortfolioSummary } from "@/components/PortfolioSummary";
import { EmptyState } from "@/components/states/EmptyState";
import { ErrorState } from "@/components/states/ErrorState";
import { LoadingSkeleton } from "@/components/states/LoadingSkeleton";
import { ACCOUNT, getHoldings, getPortfolioTotals, getPositionsFreshness } from "@/lib/fixtures";
import type { DashboardState } from "@/lib/types";

function resolveState(raw: string | string[] | undefined): DashboardState {
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (value === "loading" || value === "empty" || value === "error" || value === "stale") return value;
  return "ready";
}

export default async function Home(props: PageProps<"/">) {
  const searchParams = await props.searchParams;
  const state = resolveState(searchParams.state);

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
        {(state === "ready" || state === "stale") && (
          <>
            <PortfolioSummary holdings={holdings} totals={totals} account={ACCOUNT} freshness={freshness} />
            <HoldingsList holdings={holdings} />
          </>
        )}
      </main>

      {(state === "ready" || state === "stale") && <AdvisorTrigger />}
      <AdvisorPanel />
    </AdvisorProvider>
  );
}
