import Link from "next/link";

export function ErrorState() {
  return (
    <section className="rounded-2xl border border-status-error/25 bg-status-error-soft p-8 text-center sm:p-12">
      <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-surface">
        <svg width="18" height="18" viewBox="0 0 16 16" fill="none" aria-hidden>
          <path
            d="M8 5.5v3.25M8 11h.007M2 8a6 6 0 1 1 12 0A6 6 0 0 1 2 8Z"
            stroke="currentColor"
            strokeWidth="1.3"
            strokeLinecap="round"
            className="text-status-error"
          />
        </svg>
      </div>
      <h2 className="mt-4 text-base font-medium text-ink">Couldn&apos;t reach your portfolio data</h2>
      <p className="mx-auto mt-1.5 max-w-sm text-sm text-ink-secondary">
        The last request to SnapTrade failed. Your positions haven&apos;t loaded, and nothing you see reflects
        current data.
      </p>
      <Link
        href="/"
        className="mt-5 inline-block rounded-full bg-ink px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-ink/85"
      >
        Try again
      </Link>
    </section>
  );
}
