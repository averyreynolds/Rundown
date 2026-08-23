function Bar({ className }: { className: string }) {
  return <div className={`animate-pulse rounded-md bg-border ${className}`} />;
}

export function LoadingSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading portfolio">
      <section className="rounded-2xl border border-border bg-surface p-6 sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-5">
          <div className="space-y-2.5">
            <Bar className="h-4 w-24" />
            <Bar className="h-9 w-44" />
            <Bar className="h-3.5 w-56" />
          </div>
          <div className="space-y-2.5">
            <Bar className="h-4 w-32" />
            <Bar className="h-5 w-28" />
          </div>
        </div>
        <div className="mt-6">
          <Bar className="h-3.5 w-40" />
        </div>
        <div className="mt-6">
          <Bar className="h-2.5 w-full rounded-full" />
        </div>
      </section>

      <section className="mt-8">
        <Bar className="mb-2 h-4 w-20" />
        <div className="rounded-2xl border border-border bg-surface px-5 sm:px-6">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 border-b border-border py-4 last:border-b-0">
              <div className="h-9 w-9 shrink-0 animate-pulse rounded-full bg-border" />
              <div className="flex-1 space-y-2">
                <Bar className="h-3.5 w-24" />
                <Bar className="h-3 w-32" />
              </div>
              <Bar className="h-4 w-16" />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
