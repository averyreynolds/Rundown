/**
 * Which held positions a draft question mentions, for the instant typing
 * highlight. Mirrors `backend/app/domain/symbol_matching.py`, with the same
 * test cases. It only ever affects highlighting: what an answer actually uses
 * comes from the backend.
 */

export interface HeldPosition {
  symbol: string;
  companyName?: string | null;
}

const SUFFIX_PATTERN =
  /[,.]?\s*\b(incorporated|inc|corporation|corp|co|company|ltd|limited|llc|plc|holdings?|class\s+[abc])\b\.?\s*$/i;

export function matchHoldings(draft: string, held: readonly HeldPosition[]): string[] {
  if (!draft) return [];

  const matched = new Set<string>();
  for (const { symbol, companyName } of held) {
    if (matched.has(symbol)) continue;

    const name = companyName ? normalizeCompanyName(companyName) : "";
    if (wordPattern(symbol).test(draft) || (name && wordPattern(name).test(draft))) {
      matched.add(symbol);
    }
  }
  return [...matched];
}

function normalizeCompanyName(name: string): string {
  let stripped = name.trim();
  while (true) {
    const withoutSuffix = stripped
      .replace(SUFFIX_PATTERN, "")
      .trim()
      .replace(/[,.]+$/, "");
    if (withoutSuffix === stripped) return stripped;
    stripped = withoutSuffix;
  }
}

function wordPattern(phrase: string): RegExp {
  const words = phrase.split(/\s+/).filter(Boolean).map(escapeRegExp);
  return new RegExp(`\\b${words.join("\\s+")}\\b`, "i");
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
