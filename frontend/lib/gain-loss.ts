/**
 * The fixed scale behind the map's fills: change since cost, never a forecast
 * or a rating. See "The Gain/Loss Color Rule" in DESIGN.md. Step names match
 * the `--color-gain-*`, `--color-loss-*`, and `--color-gain-loss-flat` tokens.
 */

export type GainLossStep =
  | "loss-3"
  | "loss-2"
  | "loss-1"
  | "flat"
  | "gain-1"
  | "gain-2"
  | "gain-3";

export const GAIN_LOSS_LEGEND: readonly GainLossStep[] = [
  "loss-3",
  "loss-2",
  "loss-1",
  "flat",
  "gain-1",
  "gain-2",
  "gain-3",
];

/** `null` means no recorded cost basis, which is unknown, not a gain. */
export function gainLossStep(percentSinceCost: number | null): GainLossStep {
  if (percentSinceCost === null || !Number.isFinite(percentSinceCost)) return "flat";

  const size = Math.abs(percentSinceCost);
  if (size < 2) return "flat";

  const direction = percentSinceCost > 0 ? "gain" : "loss";
  if (size < 10) return `${direction}-1`;
  if (size < 30) return `${direction}-2`;
  return `${direction}-3`;
}
