---
name: Rundown
description: A portfolio dashboard that answers "does this matter?" — consumer-fintech calm, played straight, no invented world.
colors:
  paper: "#f7f7f5"
  surface: "#ffffff"
  ink: "#14161a"
  ink-secondary: "#5b6068"
  ink-faint: "#6b7280"
  border: "#e6e5e1"
  border-strong: "#d4d3ce"
  accent: "#3654d6"
  accent-ink: "#2743b3"
  accent-soft: "#eef1fc"
  status-stale: "#92640a"
  status-stale-soft: "#fbf1dc"
  status-error: "#a83f3f"
  status-error-soft: "#fbecec"
typography:
  display:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "2.25rem"
    fontWeight: 600
    lineHeight: "1"
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: "1.2"
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: "1.5"
  label:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: "1.3"
  mono:
    fontFamily: "Geist Mono, ui-monospace, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
rounded:
  sm: "8px"
  md: "16px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  card-surface:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "24px 28px"
  card-nested:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.sm}"
    padding: "12px 14px"
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "#ffffff"
    rounded: "{rounded.full}"
    padding: "10px 20px"
  button-primary-hover:
    backgroundColor: "rgba(20,22,26,0.85)"
  button-accent:
    backgroundColor: "{colors.accent}"
    textColor: "#ffffff"
    rounded: "{rounded.full}"
    padding: "10px 16px"
  button-accent-hover:
    backgroundColor: "{colors.accent-ink}"
  chip-stale:
    backgroundColor: "{colors.status-stale-soft}"
    textColor: "{colors.status-stale}"
    rounded: "{rounded.full}"
    padding: "4px 10px"
  chip-error:
    backgroundColor: "{colors.status-error-soft}"
    textColor: "{colors.status-error}"
    rounded: "{rounded.full}"
    padding: "4px 10px"
  chip-flag:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.full}"
    padding: "4px 10px"
---

# Design System: Rundown

## Overview

Rundown is the category standard, executed at full commitment: a consumer-fintech portfolio dashboard in the register of Robinhood, Copilot Money, and Wealthfront, deliberately chosen over two invented visual worlds (a newsroom rundown sheet, an airport split-flap board) during the direction pass recorded in `PRODUCT.md`. There is no named metaphor here by design — the brief was to play the convention straight, not to smuggle a quirk into it. The system reads as calm, trustworthy, and slightly clinical: neutral paper-and-ink surfaces, one restrained accent, confident tabular numerals, and generous card padding, closer to a well-made banking app than to a trading terminal.

The one place this system departs hardest from category convention is deliberate, not accidental: gain/loss is never color-coded red or green. `components/PnlValue.tsx` carries its own inline comment explaining why — CLAUDE.md's hard rule that the AI advisor (and, by extension, the UI it lives in) must never read as implicit buy/sell guidance. A stoplight-colored P&L figure is exactly that kind of implicit directive, so the system uses neutral ink with a small directional glyph instead. This is a compliance-grounded rule, not a taste preference, and it should not be "fixed" back to red/green by a future editor who doesn't have this context.

Rundown is light-mode only for now. This was chosen from the use-scene stated in the surface brief — checked on a laptop at a desk in normal daylight — not defaulted to because dark mode wasn't built yet. Dark mode is a reasonable follow-on, not a gap.

**Key Characteristics:**
- Neutral paper/ink palette with a single blue-indigo accent, used sparingly (links, the advisor's brand touches, one chip tone)
- A second, structurally separate status-color pair (amber for stale, red for error) reserved exclusively for data freshness — never repurposed for gain/loss
- Flat, bordered cards at rest; shadow appears only on floating/overlay elements (the advisor drawer and its trigger)
- Tabular numerals everywhere a number appears in a column or is compared across rows
- Every provider-sourced data point carries a `source · as of [timestamp]` line, rendered in the same faint, low-emphasis type

## Colors

The palette is restrained: warm-neutral paper and ink carry almost the entire surface, one blue-indigo accent marks interactivity and brand presence, and a wholly separate amber/red pair exists only to flag data trustworthiness.

### Primary
- **Rundown Blue** (`#3654d6`): the single accent. Used for the allocation bar's fill, the advisor's user-message bubble and submit button, focus rings on inputs, and the "worth a look" flag chip (via its soft tint). Appears on a small fraction of any given screen.
- **Rundown Blue, Deep** (`#2743b3`): hover/pressed state for accent buttons, and the color of inline text links ("Ask about this position →").
- **Rundown Blue, Soft** (`#eef1fc`): tint background for the accent-toned "flag" chip only — never a full-bleed surface color.

### Secondary — Status (restricted)
A structurally separate pair from the primary accent, used exclusively for data freshness and error states. Never reused for gain/loss, and never blended with the primary accent's role.
- **Stale Amber** (`#92640a` on `#fbf1dc`): the "data is stale" chip and the stale-data card border/wash on `ErrorState`-adjacent surfaces. Signals "trust this less," not "bad."
- **Error Red** (`#a83f3f` on `#fbecec`): the error-state card and its icon. Signals a failed fetch, never a loss.

### Neutral
- **Paper** (`#f7f7f5`): the page background, and the background of nested detail cards (fundamentals/news/filing panels) sitting inside a surface card — a tonal step down, not a border, to distinguish nesting.
- **Surface** (`#ffffff`): card backgrounds (summary card, holdings list, advisor drawer).
- **Ink** (`#14161a`): primary text, and the fill color for high-emphasis buttons (Connect your brokerage, Try again, the advisor's floating trigger).
- **Ink Secondary** (`#5b6068`): secondary text — labels above figures, percent-in-parens on P&L, section subheads.
- **Ink Faint** (`#6b7280`): the lowest-emphasis text tier — timestamps, source lines, row metadata, placeholder text.
- **Border** (`#e6e5e1`): default 1px card and divider borders.
- **Border Strong** (`#d4d3ce`): hover state for bordered elements, and the "Other" segment of the allocation bar.

### Named Rules
**The Neutral P&L Rule.** Gain/loss is never rendered in red or green. It is always neutral ink (`#14161a` for the figure, `#5b6068` for the percent) with a small `▲`/`▼` glyph in ink-faint. This is a compliance boundary, not a stylistic restraint — see `components/PnlValue.tsx`'s own comment and CLAUDE.md hard rule 1. Do not reintroduce stoplight coloring here even if it "looks more like a trading app."

**The Two-Color-System Rule.** The accent (`#3654d6` family) and the status pair (amber/red) never cross roles. Accent means brand/interactive/flagged-for-attention; status means "how much should you trust this data right now." A future component must not borrow status red for a "negative" value or accent blue for a "fresh" badge.

## Typography

**Display/Body/Label Font:** Geist (via `next/font/google`), falling back to `ui-sans-serif, system-ui, sans-serif`.
**Mono Font:** Geist Mono — used narrowly, for filing accession numbers and citation source strings in the advisor panel.

**Character:** A single workhorse system-sans family used at a narrow, disciplined weight range (400/500/600). No display serif, no editorial voice — the type itself is meant to disappear behind the numbers.

### Hierarchy
- **Display** (600, 2.25rem/36px, leading-none, −0.02em tracking, tabular-nums): the single largest figure on the page — total portfolio value. Used exactly once per view.
- **Title** (600, 1.125rem/18px, tight tracking): the page wordmark ("Rundown") in `PageHeader`; also 500-weight 1rem for state headings (empty/error/loading captions).
- **Body** (400–500, 0.875rem/14px, 1.5 leading): row text, chat messages, descriptive copy — the working size for nearly everything.
- **Label** (500, 0.75rem/12px): chips, section eyebrows ("Holdings", "Fundamentals"), source/as-of lines, dt labels in the expanded holding detail.

All numeric values that appear in a column or are compared across rows (currency, percentages, quantities) use `tabular-nums` — this is applied consistently across `PortfolioSummary`, `HoldingRow`, and `AllocationBar`, and should be treated as a hard convention for any new numeric field, not an occasional nicety.

### Named Rules
**The Tabular Numerals Rule.** Any number a user might scan down a column or compare across rows renders with `tabular-nums`. No numeric column may use proportional figures.

## Layout

The page is a single centered column, `max-w-[720px]`, with `mx-auto` and responsive padding (`px-5 py-10` on mobile, `sm:px-6 sm:py-14` at larger widths). There is no multi-column dashboard grid — this is a narrow, scannable rundown, not a data-dense terminal layout, consistent with the consumer-fintech craft bar (Robinhood/Copilot/Wealthfront) over enterprise-SaaS density.

Vertical rhythm is section-level: page header, then the portfolio summary card, then the holdings list, each separated by `mt-8`. Inside cards, spacing steps in a tight, consistent scale (`gap-x-4`, `gap-y-1.5`, `mt-1.5`, `mt-6`) that reads as Tailwind's default 4px base — no bespoke spacing scale beyond that.

Holdings rows collapse from a three-column grid (`ticker/name` | `value/weight` | `P&L`) at `sm:` breakpoints to a two-row stacked layout below it, per the surface brief's mobile requirement that the summary stay pinned and the holdings list become the primary scroll surface. The holdings list itself does not paginate at the stated 5–30 position range — it scrolls.

## Elevation & Depth

Rundown is flat by default: cards are distinguished by a 1px border (`--color-border`) and a background-color step (surface vs. paper), never by a drop shadow. Shadow is reserved for elements that are literally floating above the page — the advisor's slide-in drawer (`shadow-xl`) and its floating action trigger (`shadow-lg shadow-ink/10`). Everything embedded in the normal document flow, including nested detail cards inside an expanded holding row, uses border + tonal background instead.

### Named Rules
**The Flat-At-Rest Rule.** Surfaces embedded in page flow never carry a shadow. Shadow only appears on elements that overlay the page (modals, drawers, floating triggers) — it signals "this is not part of the page," not "this card is important."

## Shapes

Two radius steps carry the whole system: a large radius (16px, `rounded-2xl`) for primary cards — the portfolio summary card, the holdings list container, the advisor drawer's message bubbles — and a smaller radius (8px, `rounded-lg`) for content nested one level inside those cards (fundamentals/news/filing detail boxes, loading-skeleton bars). Fully round (`rounded-full`) is reserved for anything pill- or dot-shaped: chips, primary/accent buttons, the ticker-initial avatar, the allocation bar and its legend dots, the advisor's floating trigger and input field.

Borders are uniformly 1px and low-contrast (`border-border` at rest, stepping up to `border-border-strong` on hover). There is no heavy-border or outlined-button treatment anywhere in the system.

## Components

### Buttons
- **Shape:** fully round (`rounded-full`) at every size used.
- **Primary (ink):** `bg-ink` (#14161a) with white text — used for state-recovery actions ("Connect your brokerage," "Try again") and the advisor's floating trigger. Hover softens to ~85% opacity.
- **Accent:** `bg-accent` (#3654d6) with white text — used narrowly, for the advisor chat's "Ask" submit button, where the accent doubles as the assistant's brand touch. Hover deepens to `accent-ink`.
- **Ghost/Text:** accent-ink colored text with `hover:underline`, no background — used for the single in-context "Ask about this position →" link inside an expanded holding row.

### Chips
- **Style:** `rounded-full`, `px-2.5 py-1`, `text-xs font-medium`, soft-tint background with matching darker text — never a solid/saturated fill.
- **Tones:** `stale` (amber), `error` (red), `flag` (accent). Each tone's soft background and ink color come from the same pair (e.g. `status-stale` / `status-stale-soft`) — there is no fourth tone, and status tones never apply to gain/loss.

### Cards / Containers
- **Corner Style:** 16px (`rounded-2xl`) for top-level cards; 8px (`rounded-lg`) for nested detail boxes.
- **Background:** `surface` (white) for top-level cards; `paper` (the page background) for content nested one level inside a surface card — this tonal step, not a border, is what signals nesting depth.
- **Shadow Strategy:** none at rest; see Elevation & Depth.
- **Border:** 1px `border-border` on every card, `border-border-strong` on hover for interactive nested cards (e.g. the news-item link).
- **Internal Padding:** `p-6`/`p-7` (24–28px) for top-level cards; `px-3.5 py-3` (14/12px) for nested detail boxes; `px-1 py-4` per holdings row.

### Inputs / Fields
- **Style:** `rounded-full`, `border-border`, `bg-paper`, `px-4 py-2.5` — used for the single text input in the advisor chat composer.
- **Focus:** border shifts to `accent` (#3654d6), no glow/ring.

### Status Chip (signature component)
`StatusChip` is the system's one reusable semantic-color primitive: a three-tone pill (`stale` / `error` / `flag`) that is the *only* place status color and accent color are allowed to render as a filled background. Every other component either uses neutral ink or the accent's text-only forms. Any new status meaning should extend this component's tone set rather than inventing a new color pairing elsewhere.

### Provenance line (signature pattern)
Every provider-sourced value — portfolio freshness, fundamentals, news, filings — renders a trailing `text-xs text-ink-faint` line reading `{source} · as of {formatAsOf(timestamp)}` (or `{source} · {relative}` for news bylines). This mirrors the backend's `SourcedValue<T>` wrapper (`backend/app/schemas/common.py`) directly in the type layer (`lib/types.ts`) and is a hard product rule, not a nice-to-have — CLAUDE.md requires provenance and freshness on anything shown to the user. Any new data-bearing component must carry this line.

### Navigation
There is no persistent nav chrome on this surface — `PageHeader` is a static wordmark + tagline, not a nav bar. The advisor is the one persistent cross-cutting affordance: a floating circular trigger (bottom-right, `bg-ink`) that opens a right-side drawer, reachable globally or scoped to a specific position from within a holding row.

## Do's and Don'ts

### Do:
- **Do** render gain/loss in neutral ink with a `▲`/`▼` glyph only — never red or green (`components/PnlValue.tsx`).
- **Do** apply `tabular-nums` to every number that appears in a column or is compared row-to-row.
- **Do** attach a `{source} · as of {timestamp}` line to any value fetched from a provider, using `formatAsOf` for timestamped values.
- **Do** format date-only values (no time-of-day component, e.g. a filing date) with `formatDate`'s explicit `timeZone: "UTC"` — this is intentional, not a bug: a bare `YYYY-MM-DD` string parses as UTC midnight, and formatting it in the viewer's local zone can roll it back a day west of UTC. Don't remove the `timeZone: "UTC"` option.
- **Do** use the paper/surface tonal step (not a border) to distinguish content nested inside a card.
- **Do** keep shadows reserved for overlay elements (drawer, floating trigger) and flat borders for everything in normal page flow.

### Don't:
- **Don't** color-code P&L red/green, or otherwise let a visual treatment read as implicit buy/sell guidance — this is a legal boundary (Investment Advisers Act, CLAUDE.md hard rule 1), not a style call, and it constrains any future component that touches gain/loss, not just `PnlValue`.
- **Don't** reuse the status-color pair (amber/red) for anything other than data freshness or fetch errors. It must never double as a gain/loss or sentiment color.
- **Don't** ship a data point without a source and as-of timestamp, even in a compact or secondary UI placement.
- **Don't** introduce a second accent hue. The system's "Restrained" color strategy (per `PRODUCT.md`'s Brand Commitments) means one accent, used sparingly — not a rotating brand palette.
- **Don't** design new screens against dark mode yet; the system is light-mode only by a deliberate use-scene decision, not an oversight, and dark values haven't been established.
