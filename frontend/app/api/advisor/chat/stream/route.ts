/**
 * Proxies the streamed advisor answer from `POST /advisor/chat/stream`, so the
 * browser never holds `RUNDOWN_API_BEARER_TOKEN` (CLAUDE.md hard rule 3). The
 * body passes through untouched: every sentence in it has already been checked
 * by the backend. Aborting the request here aborts the backend's, which ends the
 * Claude request behind it.
 */

import { parseAdvisorRequest } from "@/lib/advisor-request";
import { RundownApiError, openAdvisorStream } from "@/lib/rundown-api";

export async function POST(request: Request) {
  let raw: unknown;
  try {
    raw = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const parsed = parseAdvisorRequest(raw);
  if (!parsed) {
    return Response.json(
      { error: "Expected a JSON body with a non-empty string `question` field." },
      { status: 400 },
    );
  }

  try {
    const upstream = await openAdvisorStream(parsed, request.signal);
    return new Response(upstream, {
      headers: {
        "Content-Type": "text/event-stream",
        // `no-transform` keeps compression from holding sentences back in a buffer.
        "Cache-Control": "no-store, no-transform",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (err) {
    if (err instanceof RundownApiError) {
      return Response.json({ error: err.message }, { status: err.status || 502 });
    }
    return Response.json({ error: "Unexpected error contacting the advisor." }, { status: 500 });
  }
}
