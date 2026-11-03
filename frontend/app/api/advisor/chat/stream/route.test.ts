// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

const TOKEN = "synthetic-bearer-token";
const fetchMock = vi.fn<typeof fetch>();

function request(body: unknown, signal?: AbortSignal): Request {
  return new Request("http://localhost/api/advisor/chat/stream", {
    method: "POST",
    body: typeof body === "string" ? body : JSON.stringify(body),
    signal,
  });
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("RUNDOWN_API_BEARER_TOKEN", TOKEN);
  vi.stubEnv("RUNDOWN_API_BASE_URL", "http://backend.test");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("POST /api/advisor/chat/stream", () => {
  it("adds the token server-side and never sends it to the browser", async () => {
    const frame = 'event: scope\ndata: {"type":"scope","symbols":[]}\n\n';
    fetchMock.mockResolvedValueOnce(new Response(frame, { status: 200 }));

    const response = await POST(request({ question: "How?", symbols: [] }));

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://backend.test/advisor/chat/stream");
    expect(new Headers(init?.headers).get("Authorization")).toBe(`Bearer ${TOKEN}`);
    expect(JSON.parse(init?.body as string)).toEqual({
      question: "How?",
      context_refs: { symbols: [], filing_ref: null },
    });

    const text = await response.text();
    expect(text).toBe(frame);
    expect(text).not.toContain(TOKEN);
    for (const [, value] of response.headers) expect(value).not.toContain(TOKEN);
  });

  it("marks the response so nothing buffers it", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 200 }));

    const response = await POST(request({ question: "How?" }));

    expect(response.headers.get("Content-Type")).toBe("text/event-stream");
    expect(response.headers.get("Cache-Control")).toContain("no-transform");
    expect(response.headers.get("X-Accel-Buffering")).toBe("no");
  });

  it("passes the body through chunk by chunk, not all at once", async () => {
    const encoder = new TextEncoder();
    let controller: ReadableStreamDefaultController<Uint8Array> | undefined;
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        controller = c;
      },
    });
    fetchMock.mockResolvedValueOnce(new Response(body, { status: 200 }));

    const response = await POST(request({ question: "How?" }));
    const reader = response.body?.getReader();

    controller?.enqueue(encoder.encode("first"));
    const first = await reader?.read();
    expect(new TextDecoder().decode(first?.value)).toBe("first");

    controller?.enqueue(encoder.encode("second"));
    const second = await reader?.read();
    expect(new TextDecoder().decode(second?.value)).toBe("second");
    controller?.close();
  });

  it("forwards the browser's abort to the backend request", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 200 }));
    const browser = new AbortController();

    await POST(request({ question: "How?" }, browser.signal));

    const signal = fetchMock.mock.calls[0][1]?.signal;
    expect(signal?.aborted).toBe(false);
    browser.abort();
    expect(signal?.aborted).toBe(true);
  });

  it.each([
    [422, "No context is available."],
    [502, "Claude is unavailable."],
    [401, "Invalid API bearer token."],
  ])("returns the backend's %i for a failure before streaming", async (status, detail) => {
    fetchMock.mockResolvedValueOnce(Response.json({ detail }, { status }));

    const response = await POST(request({ question: "How?" }));

    expect(response.status).toBe(status);
    expect(await response.json()).toEqual({ error: detail });
  });

  it("returns 502 when the backend can't be reached, without revealing the token", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("connection refused"));

    const response = await POST(request({ question: "How?" }));

    expect(response.status).toBe(502);
    expect(JSON.stringify(await response.json())).not.toContain(TOKEN);
  });

  it.each([["not json"], [{ question: "   " }], [{ nope: 1 }]])(
    "rejects a bad request without calling the backend: %j",
    async (body) => {
      const response = await POST(request(body));

      expect(response.status).toBe(400);
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );
});
