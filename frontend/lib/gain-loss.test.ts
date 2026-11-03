import { describe, expect, it } from "vitest";

import { GAIN_LOSS_LEGEND, gainLossStep } from "./gain-loss";

describe("gainLossStep", () => {
  it.each([
    [1.9, "flat"],
    [-1.9, "flat"],
    [0, "flat"],
    [2, "gain-1"],
    [-2, "loss-1"],
    [9.99, "gain-1"],
    [10, "gain-2"],
    [-10, "loss-2"],
    [29.99, "gain-2"],
    [30, "gain-3"],
    [-30, "loss-3"],
    [85.37, "gain-3"],
  ])("maps %d%% to %s", (percent, step) => {
    expect(gainLossStep(percent)).toBe(step);
  });

  it("treats an unknown percent as flat rather than a gain", () => {
    expect(gainLossStep(null)).toBe("flat");
  });

  it("treats a non-finite percent as flat", () => {
    expect(gainLossStep(Number.NaN)).toBe("flat");
  });
});

describe("GAIN_LOSS_LEGEND", () => {
  it("runs from the strongest loss through flat to the strongest gain", () => {
    expect(GAIN_LOSS_LEGEND).toEqual([
      "loss-3",
      "loss-2",
      "loss-1",
      "flat",
      "gain-1",
      "gain-2",
      "gain-3",
    ]);
  });
});
