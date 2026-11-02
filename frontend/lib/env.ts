/**
 * Server-only backend connection config. Never import this file (or
 * anything that imports it) from a "use client" component -- the bearer
 * token must never reach the browser (CLAUDE.md hard rule 3).
 */

export function getRundownApiBaseUrl(): string {
  return process.env.RUNDOWN_API_BASE_URL ?? "http://127.0.0.1:8000";
}

export function getRundownApiBearerToken(): string {
  const token = process.env.RUNDOWN_API_BEARER_TOKEN;
  if (!token) {
    throw new Error(
      "Missing RUNDOWN_API_BEARER_TOKEN. Copy frontend/.env.local.example to " +
        "frontend/.env.local and set it to the same value as backend/.env's API_BEARER_TOKEN."
    );
  }
  return token;
}
