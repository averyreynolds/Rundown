export function PageHeader({ tagline = "Does this matter?" }: { tagline?: string | null }) {
  return (
    <header className="mb-10">
      <h1 className="text-xl font-semibold tracking-tight text-ink">Rundown</h1>
      {tagline && <p className="mt-1 text-sm text-ink-secondary">{tagline}</p>}
    </header>
  );
}
