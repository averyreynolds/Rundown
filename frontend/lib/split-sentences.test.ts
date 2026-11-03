import { describe, expect, it } from "vitest";

import { splitSentences } from "./split-sentences";

describe("splitSentences", () => {
  it("splits on sentence endings", () => {
    expect(splitSentences("NVDA is up. It cost less. Why? Costs fell!")).toEqual([
      "NVDA is up.",
      "It cost less.",
      "Why?",
      "Costs fell!",
    ]);
  });

  it("keeps figures and decimals in one sentence", () => {
    expect(splitSentences("That's $3,756.50 of your $8,207.20 total. It grew 85.4% overall.")).toEqual([
      "That's $3,756.50 of your $8,207.20 total.",
      "It grew 85.4% overall.",
    ]);
  });

  it.each(["U.S.", "Inc.", "Corp.", "Co.", "Ltd.", "vs.", "e.g.", "i.e."])(
    "doesn't end a sentence after %s",
    (abbreviation) => {
      const text = `Compare ${abbreviation} Others here. Next one.`;
      expect(splitSentences(text)).toEqual([`Compare ${abbreviation} Others here.`, "Next one."]);
    },
  );

  it("keeps a bold span with its closing markers", () => {
    expect(splitSentences("**Margins fell.** Revenue rose.")).toEqual([
      "**Margins fell.**",
      "Revenue rose.",
    ]);
  });

  it("doesn't split inside a bold span", () => {
    expect(splitSentences("**Margins fell. Revenue rose.** Next.")).toEqual([
      "**Margins fell. Revenue rose.**",
      "Next.",
    ]);
  });

  it("treats each list item as one unit, keeping its marker", () => {
    expect(splitSentences("Here's what stands out.\n- UNH fell. It filed.\n- XOM filed.\n1. First.")).toEqual([
      "Here's what stands out.",
      "- UNH fell. It filed.",
      "- XOM filed.",
      "1. First.",
    ]);
  });

  it("separates paragraphs and ignores blank lines", () => {
    expect(splitSentences("First para.\n\n  Second para.  \n")).toEqual(["First para.", "Second para."]);
  });

  it("keeps a final fragment with no ending", () => {
    expect(splitSentences("One sentence. And a fragment")).toEqual(["One sentence.", "And a fragment"]);
  });

  it("doesn't split before a lowercase word", () => {
    expect(splitSentences("See the 10-Q. for details.")).toEqual(["See the 10-Q. for details."]);
  });

  it("returns nothing for empty text", () => {
    expect(splitSentences("")).toEqual([]);
    expect(splitSentences("  \n ")).toEqual([]);
  });
});
