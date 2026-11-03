import { describe, expect, it } from "vitest";

import { matchHoldings } from "./match-holdings";

const apple = { symbol: "AAPL", companyName: "Apple Inc." };
const compass = { symbol: "COMP", companyName: "Compass, Inc." };

// The first group mirrors backend/tests/domain/test_symbol_matching.py, so the
// typing highlight and the backend's scoping agree on what a question mentions.
describe("matchHoldings, shared with the backend matcher", () => {
  it("matches a ticker mentioned as a standalone word", () => {
    expect(matchHoldings("What's going on with aapl?", [apple])).toEqual(["AAPL"]);
  });

  it("matches a company name with no ticker mentioned", () => {
    expect(matchHoldings("What's relevant to my Compass position?", [compass])).toEqual(["COMP"]);
  });

  it("returns multiple matches in held order", () => {
    expect(matchHoldings("Compare Compass and AAPL", [apple, compass])).toEqual(["AAPL", "COMP"]);
  });

  it("doesn't match a ticker inside a longer word", () => {
    expect(matchHoldings("I'm going to check my portfolio", [{ symbol: "GO" }])).toEqual([]);
  });

  it("doesn't match a single word of a multi-word name", () => {
    const awk = { symbol: "AWK", companyName: "American Water Works Company, Inc." };
    expect(matchHoldings("I need to top off the water in the tank", [awk])).toEqual([]);
  });

  it("matches a full multi-word name as a phrase", () => {
    const awk = { symbol: "AWK", companyName: "American Water Works Company, Inc." };
    expect(matchHoldings("How is American Water Works doing lately?", [awk])).toEqual(["AWK"]);
  });

  it("matches a single-word name after stripping its suffix", () => {
    const target = { symbol: "TGT", companyName: "Target Corporation" };
    expect(matchHoldings("How is Target doing lately?", [target])).toEqual(["TGT"]);
  });

  it("matches on ticker when no company name is known", () => {
    expect(matchHoldings("How's my VOO position?", [{ symbol: "VOO", companyName: null }])).toEqual([
      "VOO",
    ]);
  });

  it("doesn't match a ticker or name that isn't held", () => {
    expect(matchHoldings("What about MSFT or Microsoft?", [apple])).toEqual([]);
  });

  it("returns nothing when nothing is held", () => {
    expect(matchHoldings("What about AAPL?", [])).toEqual([]);
  });

  it("returns nothing for an empty draft", () => {
    expect(matchHoldings("", [apple])).toEqual([]);
  });

  it("matches a symbol held in two accounts once", () => {
    expect(matchHoldings("What's going on with AAPL?", [apple, apple])).toEqual(["AAPL"]);
  });
});

describe("matchHoldings, while typing", () => {
  const nvidia = { symbol: "NVDA", companyName: "NVIDIA Corp." };
  const berkshire = { symbol: "BRK.B", companyName: "Berkshire Hathaway Inc. Class B" };

  it.each(["nvidia", "NVDA", "nvda's"])("matches %s to NVDA", (draft) => {
    expect(matchHoldings(draft, [nvidia])).toEqual(["NVDA"]);
  });

  it("matches a ticker containing a period", () => {
    expect(matchHoldings("How is BRK.B doing?", [berkshire])).toEqual(["BRK.B"]);
  });

  it("strips stacked suffixes from a company name", () => {
    expect(matchHoldings("berkshire hathaway", [berkshire])).toEqual(["BRK.B"]);
  });

  it("doesn't match a company name inside a longer word", () => {
    expect(matchHoldings("I like pineapple", [apple])).toEqual([]);
  });

  it("matches across extra whitespace in a multi-word name", () => {
    expect(matchHoldings("berkshire   hathaway", [berkshire])).toEqual(["BRK.B"]);
  });

  it("doesn't treat regex characters in a draft or symbol as a pattern", () => {
    expect(matchHoldings("BRKxB", [berkshire])).toEqual([]);
  });
});
