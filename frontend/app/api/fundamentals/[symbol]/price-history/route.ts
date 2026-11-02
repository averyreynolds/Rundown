/**
 * Proxies `GET /fundamentals/{symbol}/price-history` on the FastAPI backend,
 * so the client-side sidebar chart (window switching needs to be
 * interactive, hence a client component) doesn't need the bearer token --
 * same indirection as `app/api/advisor/chat/route.ts`.
 */

import type { NextRequest } from "next/server";
import { RundownApiError, getPriceHistory } from "@/lib/rundown-api";
import type { PriceWindow } from "@/lib/types";

const VALID_WINDOWS: readonly PriceWindow[] = ["1D", "1W", "1M", "3M", "YTD", "1Y", "ALL"];

function parseWindow(raw: string | null): PriceWindow {
  return (VALID_WINDOWS as readonly string[]).includes(raw ?? "") ? (raw as PriceWindow) : "ALL";
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const window = parseWindow(request.nextUrl.searchParams.get("window"));

  try {
    const result = await getPriceHistory(symbol, window);
    return Response.json(result);
  } catch (err) {
    if (err instanceof RundownApiError) {
      return Response.json({ error: err.message }, { status: err.status || 502 });
    }
    return Response.json({ error: "Unexpected error contacting the backend." }, { status: 500 });
  }
}
