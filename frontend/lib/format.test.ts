import { describe, expect, it } from "vitest";

import { formatSignedCurrencyAbbreviated } from "./format";

describe("formatSignedCurrencyAbbreviated", () => {
  it.each([
    [137.5, "+$138"],
    [660, "+$660"],
    [-294, "−$294"],
    [3756.5, "+$3.8K"],
    [-1223.2, "−$1.2K"],
    [0, "+$0"],
  ])("formats %d as %s", (value, expected) => {
    expect(formatSignedCurrencyAbbreviated(value)).toBe(expected);
  });
});
