/**
 * Proxies the client-side advisor chat to `POST /advisor/chat` on the
 * FastAPI backend. This indirection (rather than the browser calling the
 * backend directly) is what keeps `RUNDOWN_API_BEARER_TOKEN` server-side
 * only (CLAUDE.md hard rule 3) while still letting the interactive
 * "use client" AdvisorPanel send messages.
 */

import { RundownApiError, postAdvisorChat } from "@/lib/rundown-api";

interface ChatRequestBody {
  question: string;
  symbols?: string[];
  filingRef?: { symbol: string; accessionNumber: string };
}

function parseFilingRef(raw: unknown): ChatRequestBody["filingRef"] {
  if (typeof raw !== "object" || raw === null) return undefined;
  const { symbol, accessionNumber } = raw as { symbol?: unknown; accessionNumber?: unknown };
  if (typeof symbol !== "string" || typeof accessionNumber !== "string") return undefined;
  return { symbol, accessionNumber };
}

function parseBody(body: unknown): ChatRequestBody | null {
  if (typeof body !== "object" || body === null) return null;
  const { question, symbols, filingRef } = body as { question?: unknown; symbols?: unknown; filingRef?: unknown };
  if (typeof question !== "string" || question.trim().length === 0) return null;
  const symbolList = Array.isArray(symbols) ? symbols.filter((s): s is string => typeof s === "string") : undefined;
  return { question, symbols: symbolList, filingRef: parseFilingRef(filingRef) };
}

export async function POST(request: Request) {
  let raw: unknown;
  try {
    raw = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const parsed = parseBody(raw);
  if (!parsed) {
    return Response.json({ error: "Expected a JSON body with a non-empty string `question` field." }, { status: 400 });
  }

  try {
    const result = await postAdvisorChat(parsed);
    return Response.json(result);
  } catch (err) {
    if (err instanceof RundownApiError) {
      return Response.json({ error: err.message }, { status: err.status || 502 });
    }
    return Response.json({ error: "Unexpected error contacting the advisor." }, { status: 500 });
  }
}
