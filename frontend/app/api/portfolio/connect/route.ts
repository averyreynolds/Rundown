/**
 * Proxies `POST /portfolio/connect` on the FastAPI backend, so the
 * client-side "Connect your brokerage" button doesn't need the bearer
 * token. Read-only connection portal URL only -- see CLAUDE.md hard rule 7
 * (no trade execution) and `backend/app/services/snaptrade_service.py`.
 */

import { RundownApiError, connectPortfolio } from "@/lib/rundown-api";

export async function POST() {
  try {
    const result = await connectPortfolio();
    return Response.json(result);
  } catch (err) {
    if (err instanceof RundownApiError) {
      return Response.json({ error: err.message }, { status: err.status || 502 });
    }
    return Response.json({ error: "Unexpected error contacting the backend." }, { status: 500 });
  }
}
