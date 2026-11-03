import { GAIN_LOSS_LEGEND, type GainLossStep } from "@/lib/gain-loss";

/** Static class names, since Tailwind can't see class names built at runtime. */
export const GAIN_LOSS_FILL: Record<GainLossStep, string> = {
  "loss-3": "bg-loss-3",
  "loss-2": "bg-loss-2",
  "loss-1": "bg-loss-1",
  flat: "bg-gain-loss-flat",
  "gain-1": "bg-gain-1",
  "gain-2": "bg-gain-2",
  "gain-3": "bg-gain-3",
};

export function GainLossLegend() {
  return (
    <div
      role="img"
      aria-label="Tile color shows change since cost, from a 30% loss to a 30% gain"
      className="flex items-center gap-1.5 font-mono text-[11px] text-ink-secondary"
    >
      <span>−30%</span>
      <span className="flex gap-0.5">
        {GAIN_LOSS_LEGEND.map((step) => (
          <span key={step} className={`block h-3 w-[18px] rounded-sm ${GAIN_LOSS_FILL[step]}`} />
        ))}
      </span>
      <span>+30% since cost</span>
    </div>
  );
}
