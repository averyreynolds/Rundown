/**
 * Proxies the client-side advisor chat to `POST /advisor/chat` on the
 * FastAPI backend. This indirection (rather than the browser calling the
 * backend directly) is what keeps `RUNDOWN_API_BEARER_TOKEN` server-side
 * only (CLAUDE.md hard rule 3). The workspace now asks through
 * `chat/stream/route.ts`, and this stays until streaming has proven itself.
 */

import { parseAdvisorRequest } from "@/lib/advisor-request";
import { RundownApiError, postAdvisorChat } from "@/lib/rundown-api";

export async function POST(request: Request) {
  let raw: unknown;
  try {
    raw = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const parsed = parseAdvisorRequest(raw);
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
