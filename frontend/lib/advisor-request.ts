/** Validates what the browser sends to the advisor's same-origin proxy routes. */

import type { AdvisorChatInput } from "./rundown-api";

function parseFilingRef(raw: unknown): AdvisorChatInput["filingRef"] {
  if (typeof raw !== "object" || raw === null) return undefined;
  const { symbol, accessionNumber } = raw as { symbol?: unknown; accessionNumber?: unknown };
  if (typeof symbol !== "string" || typeof accessionNumber !== "string") return undefined;
  return { symbol, accessionNumber };
}

export function parseAdvisorRequest(body: unknown): AdvisorChatInput | null {
  if (typeof body !== "object" || body === null) return null;
  const { question, symbols, filingRef } = body as {
    question?: unknown;
    symbols?: unknown;
    filingRef?: unknown;
  };
  if (typeof question !== "string" || question.trim().length === 0) return null;
  const symbolList = Array.isArray(symbols)
    ? symbols.filter((s): s is string => typeof s === "string")
    : undefined;
  return { question, symbols: symbolList, filingRef: parseFilingRef(filingRef) };
}
