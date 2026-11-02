import type { PriceWindow } from "@/lib/types";

const WINDOWS: { value: PriceWindow; label: string }[] = [
  { value: "1D", label: "1D" },
  { value: "1W", label: "1W" },
  { value: "1M", label: "1M" },
  { value: "3M", label: "3M" },
  { value: "YTD", label: "YTD" },
  { value: "1Y", label: "1Y" },
  { value: "ALL", label: "All" },
];

export function WindowSelector({ value, onChange }: { value: PriceWindow; onChange: (window: PriceWindow) => void }) {
  return (
    <div role="group" aria-label="Chart time window" className="flex gap-0.5">
      {WINDOWS.map((w) => (
        <button
          key={w.value}
          type="button"
          aria-pressed={value === w.value}
          onClick={() => onChange(w.value)}
          className={`rounded-md px-1.5 py-0.5 text-xs font-medium transition-colors ${
            value === w.value ? "bg-accent-soft text-accent-ink" : "text-ink-faint hover:bg-paper hover:text-ink-secondary"
          }`}
        >
          {w.label}
        </button>
      ))}
    </div>
  );
}
