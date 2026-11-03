import type { MapSizing } from "@/lib/types";

const OPTIONS: { id: MapSizing; label: string }[] = [
  { id: "value", label: "Value" },
  { id: "cost", label: "Cost" },
  { id: "gain", label: "Gain or loss" },
];

export function SizingControl({
  sizing,
  onChange,
}: {
  sizing: MapSizing;
  onChange: (sizing: MapSizing) => void;
}) {
  return (
    <div role="group" aria-label="Size tiles by" className="flex gap-0.5 rounded-full bg-paper p-0.5">
      {OPTIONS.map(({ id, label }) => {
        const isPressed = sizing === id;
        return (
          <button
            key={id}
            type="button"
            aria-pressed={isPressed}
            onClick={() => onChange(id)}
            className={`min-h-9 rounded-full px-3 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink ${
              isPressed ? "bg-ink text-white" : "text-ink-secondary hover:text-ink"
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
