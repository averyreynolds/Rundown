# Rundown

**A portfolio intelligence dashboard that transforms raw brokerage data into digestible signal.**

Rundown connects to your real brokerage account and becomes the layer between your holdings and informed decisions. The tool surfaces fundamentals, filings, and personalized news for the equities you own with a conversational AI advisor that explains what changed day-to-day and why it matters.

---

## Rundown's purpose

Brokerage apps like Schwab and Fidelity are built to serve every audience at once. Creating a platform that includes retirees, day traders, options sellers, and casual investors leads to a crowded UI that displays plenty of data without really communicating anything meaningful to its users. You should be able to see that a stock moved and easily answer: **"does this matter?"**

The gap between the data and consumers is synthesis of info, not a lack of data. Therefore, Rundown provides one location for fundamentals, filings, and news for your specific, personal holdings.

Rundown exists to cater towards investors who are engaged but time-constrained. These are people who already know what they own and are concerned with keeping up with what changed and if it matters.

---

## Core features

- **Syncs your real portfolio**: connects to your brokerage (w/ SnapTrade) and populates holdings, cost basis, and positions automatically.
- **Communicates insights on every screen**: a portfolio dashboard that communicates concentration risk, allocation, and P&L in a way your brokerage app doesn't.
- **Explains the fundamentals**: key ratios per holding (P/E, FCF yield, debt/equity, margins) alongside plain English and summaries of the latest 10-K / 10-Q filings.
- **Talks to you about your portfolio**: an AI advisor (text for MVP, voice after) that answers user questions about their portfolio with actual data. However, the chatbot exclusively explains and contextualizes without ever prescribing.

---

## AI Advisor

**What it does:**
- *"Your position in X is now 18% of your portfolio, up from 11% three months ago — mostly price appreciation, not new buys."*
- *"This 10-Q shows revenue growth decelerating from 22% to 9% year-over-year."*
- *"This news is about a company you watch, not one you hold — flagging in case you're weighing whether to add it."*

**What it never does:**
- Tell you to buy, sell, or reallocate. No directives framed as advice.

**Why the boundary exists:** providing personalized investment advice in the US for compensation can trigger registration requirements under the Investment Advisers Act. The philosophy "explains, doesn't prescribe" means the architecture never has to be reduced if Rundown grows beyond personal use.

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js (React, TypeScript) | Web-first dashboard |
| Backend | Python (FastAPI) | Orchestrates data sources, portfolio math, LLM calls |
| Brokerage data | [SnapTrade](https://snaptrade.com) | Free personal tier; covers 30+ brokerages (incl. Schwab, my personal brokerage) |
| Fundamentals | Financial Modeling Prep + SEC EDGAR | Ratios from FMP; authoritative filing text from EDGAR |
| News | Finnhub | Filtered against your holdings & watchlist |
| AI advisor | Anthropic Claude API | Reasons only over data explicitly provided to it |

---

## Mermaid Diagram

```
┌─────────────────┐        ┌──────────────────────┐
│  Next.js (React)│ ─────▶ │   FastAPI backend    │
│  Dashboard UI   │  HTTP  │  (orchestration)     │
└─────────────────┘        └──────────┬───────────┘
                                       │
             ┌─────────────┬───────────┼───────────┬─────────────┐
             ▼             ▼           ▼           ▼             ▼
        ┌─────────┐  ┌──────────┐ ┌─────────┐ ┌────────┐  ┌──────────┐
        │SnapTrade│  │   FMP    │ │  EDGAR  │ │Finnhub │  │  Claude  │
        │(holdings)│  │(ratios) │ │(filings)│ │ (news) │  │(advisor) │
        └─────────┘  └──────────┘ └─────────┘ └────────┘  └──────────┘
```

---

## Status

MVP, single-user, greenfield. Both services run and are wired end-to-end: the dashboard fetches real positions, fundamentals, news, and filings from the backend, and the AI advisor answers questions grounded in that same data. What's not yet built: a company-name source for holdings (displayed by ticker for now) and a concentration/"worth a look" signal. See `frontend/README.md` and `backend/README.md` for exact gaps.

## Getting started

Two services, run separately. Full detail lives in each service's own README ([`backend/README.md`](backend/README.md), [`frontend/README.md`](frontend/README.md)) -- this is the short version.

```bash
# 1. Backend
cd backend
uv sync
cp .env.example .env   # fill in real API keys -- see backend/README.md
uv run uvicorn app.main:app --reload

# 2. Frontend (separate terminal)
cd frontend
npm install
cp .env.local.example .env.local   # RUNDOWN_API_BEARER_TOKEN must match backend/.env
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). With no brokerage connected yet you'll land on an empty state with a "Connect your brokerage" button (SnapTrade, read-only); once connected, the dashboard and AI advisor both run on your real data.

---
 
## License
 
Released under the [MIT License](LICENSE). Copyright © 2026 averyreynolds
 
---
 
*Rundown is a personal project and does not constitute financial advice. Data may be delayed or inaccurate; always verify against your brokerage of record before making decisions.*
