# Rundown Frontend

Next.js (App Router, React, TypeScript) dashboard for Rundown. See the [root README](../README.md) for product framing and [`backend/README.md`](../backend/README.md) for the API this talks to. Per `CLAUDE.md`, this app never calls a third-party data provider directly and holds no API keys of its own -- every request goes through the Rundown FastAPI backend.

---

## How it's wired to the backend

- The dashboard (`app/page.tsx`) is a Server Component that fetches `GET /portfolio/positions` and `GET /portfolio/accounts` directly from the backend at render time, using a shared-secret bearer token that lives only in server-side env vars (`lib/env.ts`, `lib/rundown-api.ts`) -- it's never sent to the browser.
- Interactive client components (the advisor chat, the "Connect your brokerage" button) can't hold that token, so they call same-origin Next.js Route Handlers instead (`app/api/advisor/chat/route.ts`, `app/api/portfolio/connect/route.ts`), which proxy the request to the backend server-side and attach the token there.
- Per-holding fundamentals, news, and the latest filing are fetched best-effort per symbol (`lib/dashboard.ts`); a failure on any one of those (e.g. a placeholder FMP/Finnhub/EDGAR key) degrades just that card to "not available" rather than failing the page. The core positions/accounts fetch is the only load-bearing call.

**Known gaps in the current contract** (not bugs, just not built yet):
- No company-name source exists on the backend yet (`PositionView` has no `name` field), so holdings currently display by ticker only.
- There's no backend "worth a look" / concentration-flag signal yet, so the "Worth a look" badge never shows for real data (it's still visible only in the fixture-based design preview below).

## Setup

```bash
npm install
cp .env.local.example .env.local
```

Fill in `.env.local`:

| Variable | Value |
|---|---|
| `RUNDOWN_API_BASE_URL` | Where the backend is running, e.g. `http://127.0.0.1:8000` |
| `RUNDOWN_API_BEARER_TOKEN` | Must exactly match `backend/.env`'s `API_BEARER_TOKEN` |

Both are server-only (no `NEXT_PUBLIC_` prefix) -- see CLAUDE.md hard rule 3.

## Running the dev server

The backend must already be running (see `backend/README.md`) -- this app has no data of its own.

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

- No SnapTrade connection yet: you'll see the "No brokerage connected yet" empty state. Click "Connect your brokerage" to start the (read-only) SnapTrade portal flow via `POST /portfolio/connect`.
- Backend unreachable, misconfigured token, etc.: you'll see the error state.
- Once connected, the dashboard renders real positions, fundamentals, news, and filings, and the advisor panel answers questions grounded in that same data via `POST /advisor/chat`.

### Design-preview mode

Every UI state can be forced from synthetic fixtures (`lib/fixtures.ts`), without a live backend connection, via a `state` query param:

```
http://localhost:3000/?state=loading
http://localhost:3000/?state=empty
http://localhost:3000/?state=error
http://localhost:3000/?state=stale
```

Omitting `state` always uses real data from the backend.

## Checks

```bash
npm run lint
npm run build   # also runs the TypeScript compiler
```

## Architecture at a glance

- `app/page.tsx` -- the dashboard Server Component; real-data path vs. `?state=` preview path.
- `app/api/` -- Route Handlers that proxy authenticated requests to the backend for client components.
- `lib/env.ts`, `lib/rundown-api.ts` -- server-only backend client: base URL/token, snake_case -> camelCase mapping (see file docstring for which backend schemas alias differently), typed error handling.
- `lib/dashboard.ts` -- server-only assembly of one page's worth of dashboard data, with best-effort per-holding enrichment.
- `lib/fixtures.ts` -- synthetic demo data for the `?state=` design-preview path only. Never real account/holding data (CLAUDE.md hard rule 5).
- `components/` -- presentational components, split into the main dashboard surface, `holdings/`, `advisor/`, and `states/` (loading/empty/error).
