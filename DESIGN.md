---
name: Rundown
description: An assistant beside a living map of your portfolio that answers "does this matter?" — consumer-fintech calm, played straight, no invented world.
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
  gain-1: "#d5efe9"
  gain-2: "#9bdccf"
  gain-3: "#4fbfab"
  loss-1: "#fbe0d5"
  loss-2: "#f7b59d"
  loss-3: "#ee8259"
  gain-loss-flat: "#e8eaee"
  map-dimmed: "#f1f2f4"
typography:
  display:
    fontFamily: "Schibsted Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "2.5rem"
    fontWeight: 600
    lineHeight: "1.06"
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Schibsted Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: "1.12"
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Schibsted Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: "1.2"
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Schibsted Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: "1.45"
  body-small:
    fontFamily: "Schibsted Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: "1.5"
  label:
    fontFamily: "Schibsted Grotesk, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: "1.3"
  mono:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
rounded:
  xs: "6px"
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
  map-tile:
    rounded: "{rounded.xs}"
    padding: "8px 10px"
    minWidth: "76px"
    minHeight: "44px"
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

Rundown is an assistant beside a living map of your portfolio. A conversation panel sits next to a full-height map, and the map reacts to what you type and to each sentence of an answer. The assistant is the product; holdings, fundamentals, filings, and news are its evidence.

The visual register is still the category standard, executed at full commitment: consumer fintech in the manner of Robinhood, Copilot Money, and Wealthfront, deliberately chosen over two invented visual worlds (a newsroom rundown sheet, an airport split-flap board) during the direction pass recorded in `PRODUCT.md`. There is no named metaphor. The system reads as calm, trustworthy, and slightly clinical: neutral surfaces, ink for primary actions, one restrained accent, and confident tabular numerals, closer to a well-made banking app than to a trading terminal.

Gain/loss color is allowed, within limits. This system used to ban it, reading CLAUDE.md hard rule 1 to mean that any colored P&L figure was an implicit buy/sell signal. Avery overturned that reading on 2026-11-02 for the assistant-first Living Map direction: a color showing a past, factual change is not by itself a directive. Hard rule 1 still applies in full to what the assistant and the UI say, and The Gain/Loss Color Rule below is what keeps color descriptive. This was a product decision, not a legal review, so revisit it before Rundown goes beyond personal use.

This document leads the code for now. The Living Map isn't built yet, so the layout, motion, and component sections below describe the target, and the current dashboard, drawer, and summary card remain in the app until the overhaul replaces them.

Rundown is light-mode only. This was chosen from the use-scene stated in the surface brief — checked on a laptop at a desk in normal daylight — and reconfirmed for the Living Map on 2026-11-02, since the gain/loss scale is only defined and tested on light surfaces. Dark mode is a reasonable follow-on, not a gap.

**Key Characteristics:**
- Neutral paper/ink palette with a single blue-indigo accent, used sparingly (links, focus on inputs, one chip tone)
- A second, structurally separate status-color pair (amber for stale, red for error) reserved exclusively for data freshness — never repurposed for gain/loss
- Flat surfaces at rest; shadow appears only on overlay elements (the holding detail panel on smaller screens)
- Tabular numerals everywhere a number appears in a column or is compared across rows
- Every provider-sourced data point carries a `source · as of [timestamp]` line, rendered in the same faint, low-emphasis type

## Colors

The palette is restrained: warm-neutral paper and ink carry almost the entire surface, one blue-indigo accent marks interactivity and brand presence, and a wholly separate amber/red pair exists only to flag data trustworthiness.

### Primary
- **Rundown Blue** (`#3654d6`): the single accent. Used for focus on inputs and the "worth a look" flag chip (via its soft tint). Appears on a small fraction of any given screen. Primary actions, including Ask, are ink.
- **Rundown Blue, Deep** (`#2743b3`): hover/pressed state for accent buttons, and the color of inline text links ("Ask about this position →").
- **Rundown Blue, Soft** (`#eef1fc`): tint background for the accent-toned "flag" chip only — never a full-bleed surface color.

### Secondary — Status (restricted)
A structurally separate pair from the primary accent, used exclusively for data freshness and error states. Never reused for gain/loss, and never blended with the primary accent's role.
- **Stale Amber** (`#92640a` on `#fbf1dc`): the "data is stale" chip and the stale-data card border/wash on `ErrorState`-adjacent surfaces. Signals "trust this less," not "bad."
- **Error Red** (`#a83f3f` on `#fbecec`): the error-state card and its icon. Signals a failed fetch, never a loss.

### Gain/Loss (restricted)
A diverging scale used only as a fill behind ink text, to show change since cost. See The Gain/Loss Color Rule.
- **Gain Teal** (`#d5efe9`, `#9bdccf`, `#4fbfab`): gains of 2–10%, 10–30%, and 30% or more.
- **Loss Vermilion** (`#fbe0d5`, `#f7b59d`, `#ee8259`): losses of 2–10%, 10–30%, and 30% or more.
- **Flat** (`#e8eaee`): changes under 2% in either direction.

### Neutral
- **Paper** (`#f7f7f5`): the page background, and the background of nested detail cards (fundamentals/news/filing panels) sitting inside a surface card — a tonal step down, not a border, to distinguish nesting.
- **Surface** (`#ffffff`): the map pane, the composer, and card backgrounds.
- **Ink** (`#14161a`): primary text, the fill color for primary actions (Ask, Get today's rundown, Connect your brokerage, Try again), and the focus outline on map tiles.
- **Ink Secondary** (`#5b6068`): secondary text — labels above figures, percent-in-parens on P&L, section subheads.
- **Ink Faint** (`#6b7280`): the lowest-emphasis text tier — timestamps, source lines, row metadata, placeholder text.
- **Border** (`#e6e5e1`): default 1px card and divider borders.
- **Border Strong** (`#d4d3ce`): hover state for bordered elements.
- **Map Dimmed** (`#f1f2f4`): tiles outside the current focus, with `ink-secondary` text. This removes their gain/loss fill while another tile is focused, so dimming never reads as a change in value.

### Named Rules
**The Gain/Loss Color Rule.** Color may show gain/loss only as a description of what already happened:
- **It shows one fact.** Color encodes change since cost on the fixed scale above, with a legend on screen. It never encodes a forecast, a rating, or sentiment. Any other measure needs its own legend.
- **It uses teal and vermilion, not green and red.** Under deuteranopia the teal/vermilion pair stays distinct (ΔE 11.1), while the tested green/red pair nearly merges (ΔE 3.0).
- **It's a fill, not text.** Figures stay ink (`#14161a`) and always carry their sign and a `▲`/`▼` glyph, so color is never the only signal.
- **It doesn't direct attention.** Focus, flags, and "stands out" use an ink outline that looks the same on a gain or a loss. A loss must not look like an alert.
- **The words stay neutral.** The assistant and UI copy never use color as an argument, such as "in the red." Hard rule 1 still forbids anything directive.

**The Separate-Roles Rule.** The accent (`#3654d6` family), the status pair (amber/red), and the gain/loss scale never cross roles. Accent means brand/interactive/flagged-for-attention; status means "how much should you trust this data right now"; gain/loss means change since cost. A future component must not borrow status red for a "negative" value, a gain/loss color for a "fresh" badge, or accent blue for either.

## Typography

**Sans Font:** Schibsted Grotesk (via `next/font/google`), falling back to `ui-sans-serif, system-ui, sans-serif`.
**Mono Font:** JetBrains Mono, used for what Rundown read and where it came from: reading steps, source lines, the composer's scope line, and map labels. It marks provenance and figures, never prose.

**Character:** One grotesque family at a disciplined weight range (400/500/600/700), with mono as the data voice. No display serif and no editorial voice. The answer's words lead, and the type stays out of the way of the numbers.

### Hierarchy
- **Display** (600, 2.5rem/40px, 1.06 leading, −0.03em tracking): the opening question on the home screen. Used at most once per view.
- **Headline** (600, 1.75rem/28px, 1.12 leading, −0.025em tracking): the headline of an answer or rundown.
- **Title** (700, 1.25rem/20px, −0.02em tracking): the page wordmark ("Rundown").
- **Body** (400, 1rem/16px, 1.45 leading): answer sentences and the composer. Never smaller on a phone, so the input doesn't zoom.
- **Body Small** (400–500, 0.875rem/14px, 1.5 leading): holdings rows, detail panel text, suggested questions.
- **Label** (500, 0.75rem/12px): chips, section eyebrows, legend, sizing notes.
- **Mono** (400, 0.75rem/12px, down to 11px for source lines): reading steps, source and as-of lines, tile figures.
- **Tile ticker** (700, −0.02em tracking): 28px at 10% or more of the current measure, 20px at 5% or more, otherwise 15px.

All numeric values that appear in a column or are compared across rows (currency, percentages, quantities) use `tabular-nums`. This is a hard convention for any new numeric field. The `tabular-nums` utility also sets the mono face, because Schibsted Grotesk's tabular figures widen its punctuation (`$8 , 207 . 20`).

### Named Rules
**The Tabular Numerals Rule.** Any number a user might scan down a column or compare across rows renders with `tabular-nums`. No numeric column may use proportional figures.

## Layout

**Above 900px wide,** the home screen is two full-height panes that scroll independently: the conversation panel on the left (`minmax(0, 520px)`) and the map pane filling the rest. The page itself never scrolls.

- **Conversation panel:** wordmark, then the scrolling thread, then the composer pinned to the bottom with its scope line and the note "Explains what's relevant. Never tells you what to do."
- **Map pane:** the view toggle, sizing control, and legend pinned at the top, the tile area in the middle, and the total and provenance line pinned at the bottom.

**At 900px and below,** the layout is a single column with the conversation first and the composer pinned to the bottom. The header shows the wordmark and the total value; tapping the total opens the holdings list, which is the portfolio view on a phone. There is no treemap at these widths, because a 390px map runs out of room for labeled tiles almost immediately. The composer's scope line ("About NVDA") does the job the typing highlight does on the map.

### Map density
Every position keeps its own tile. There is no grouping into an "N smaller" tile.

- **Minimum tile size is 76×44px**, enough for a ticker and a figure and for a reliable pointer target. Touch-sized targets at phone widths come from the holdings list, not the map.
- **Tile area scrolls vertically when it has to.** Tiles fill the pane when they fit. A column of many small positions can need more height than the pane has, as 30 positions do in a typical laptop window, and then the tile area grows past one screen and only that area scrolls. The map never scrolls horizontally: the number of columns is limited by the pane's width.
- **Columns come from value and hold across sizing modes**, so tiles resize rather than jump. They're recomputed only when the positions or the pane's width change.
- **Minimum-size tiles aren't proportional.** When any tile is drawn larger than its share, the map says so next to the legend: "Small positions are shown at a minimum size." The figures on the tile stay exact.

### States
- **Empty (no brokerage linked):** no map or composer, since there's nothing to ask about yet. A centered card explains what connecting does and offers Connect your brokerage.
- **Loading:** static neutral placeholder tiles, with no shimmer.
- **Error (positions failing, nothing cached):** no map. An error card says what failed and offers Try again.
- **Stale:** the map renders normally, with the stale chip and the older as-of time on the provenance line. Stale data is never unlabeled.
- **Answer states:** reading, writing, done, stopped, and retracted are specified in the overhaul plan's client state table. A retraction clears focus, returns to value sizing, and shows only the safe fallback.

### Holdings list and detail
The holdings list is the map's table view, reached by a toggle in the map pane, and shows the same positions and figures. It's also how small tiles stay easy to reach by keyboard or assistive technology. A details control on a focused tile opens `HoldingDetailPanel`, which overlays the map pane rather than taking a permanent column. Holdings rows keep their responsive grid: three columns from the `sm:` breakpoint, two stacked rows below it.

## Elevation & Depth

Rundown is flat by default: surfaces are distinguished by a 1px border (`--color-border`) and a background-color step (surface vs. paper), never by a drop shadow. Shadow is reserved for elements that are literally floating above the page, such as `HoldingDetailPanel` when it overlays the map pane (`shadow-xl`). Everything embedded in the normal document flow, including map tiles and nested detail cards, uses a border or tonal background instead.

### Named Rules
**The Flat-At-Rest Rule.** Surfaces embedded in page flow never carry a shadow. Shadow only appears on elements that overlay the page (modals, overlaid panels) — it signals "this is not part of the page," not "this card is important."

## Motion

Motion explains what the assistant is doing, and only then. Nothing animates on page load.

- **Tile resizing** (800ms, `cubic-bezier(0.16, 1, 0.3, 1)`): tiles change size when the sizing mode changes, whether the user or an answer changed it. A window resize or the first layout snaps instead.
- **Fill and outline changes** (160–220ms, ease): focus and dimming as sentences arrive or the pointer moves.
- **Reading pulse** (1000ms, opacity to 0.5, staggered 70ms per tile): in-scope tiles while Rundown reads.

`prefers-reduced-motion: reduce` removes all of it: results appear in their final state, nothing pulses, and tiles change size instantly.

### Named Rules
**The Motion-Follows-Meaning Rule.** Every animation must correspond to a change in what the assistant is doing or what the map is showing. Don't add entrance animation, count-ups, or staggered reveals. This replaces the earlier One-Moment Rule, which belonged to the dashboard's summary card.

**The Answer-Owns-Sizing-Until-You-Touch-It Rule.** An answer may change the sizing mode as its sentences arrive, and the map says so. If the user changes sizing during an answer, the answer stops changing it for that turn.

## Shapes

Three radius steps carry the system: a large radius (16px, `rounded-2xl`) for primary cards, the composer, and the holdings list container; a smaller radius (8px, `rounded-lg`) for content nested one level inside those cards (fundamentals/news/filing detail boxes, loading placeholders); and the smallest (6px, `rounded-md`) for map tiles, which sit 4px apart and read as one field. Fully round (`rounded-full`) is reserved for anything pill- or dot-shaped: chips, buttons, and the ticker-initial avatar.

Borders are uniformly 1px and low-contrast (`border-border` at rest, stepping up to `border-border-strong` on hover). There is no heavy-border or outlined-button treatment anywhere in the system.

## Components

### Buttons
- **Shape:** fully round (`rounded-full`) at every size used.
- **Primary (ink):** `bg-ink` (#14161a) with white text, for Ask, Stop, Get today's rundown, Connect your brokerage, and Try again. Hover softens to ~85% opacity.
- **Suggested question:** white with a 1px border, 44px minimum height, left-aligned text, for starter questions and follow-ups. Hover strengthens the border.
- **Ghost/Text:** accent-ink colored text with `hover:underline`, no background, for inline links.

### Chips
- **Style:** `rounded-full`, `px-2.5 py-1`, `text-xs font-medium`, soft-tint background with matching darker text — never a solid/saturated fill.
- **Tones:** `stale` (amber), `error` (red), `flag` (accent). Each tone's soft background and ink color come from the same pair (e.g. `status-stale` / `status-stale-soft`) — there is no fourth tone, and status tones never apply to gain/loss.

### Cards / Containers
- **Corner Style:** 16px (`rounded-2xl`) for top-level cards; 8px (`rounded-lg`) for nested detail boxes.
- **Background:** `surface` (white) for top-level cards; `paper` (the page background) for content nested one level inside a surface card — this tonal step, not a border, is what signals nesting depth.
- **Shadow Strategy:** none at rest; see Elevation & Depth.
- **Border:** 1px `border-border` on every card, `border-border-strong` on hover for interactive nested cards (e.g. the news-item link).
- **Internal Padding:** `p-6`/`p-7` (24–28px) for top-level cards; `px-3.5 py-3` (14/12px) for nested detail boxes; `px-1 py-4` per holdings row.

### Composer
A single text input and Ask button in a `rounded-2xl`, 1px-bordered surface pinned to the bottom of the conversation. Below the input, a mono scope line shows "All 11 positions" or "About NVDA" as the user types. The input's border shifts to ink on focus, with no glow. While an answer is running, Ask becomes Stop.

### Portfolio Map (signature component)
Tiles are real buttons with full accessible names, such as "NVDA, NVIDIA Corp. 13.1% of portfolio, +85.4% since cost. Ask about this position." Each shows a ticker and a figure in ink: weight and change since cost by value, percent of cost by cost, and signed dollars by gain or loss. Figures carry a sign and a `▲`/`▼` glyph. Narrow tiles shorten the figure (change since cost, percent of cost, or abbreviated dollars such as `+$3.8K`) and tighten their padding to 4×6px, and the exact figures stay in the accessible name. A position with no recorded cost basis says so rather than showing a gain, and takes the minimum size when sized by gain or loss. Clicking a tile writes a question into the composer without sending it. Focus is a 3px inset ink outline, identical on a gain or a loss. The sizing control is a three-part segmented control (Value, Cost, Gain or loss) that marks the pressed mode, with "Rundown changed this to match its answer" beside it when an answer did so.

### Answer
A question bubble, then reading steps in mono, one per source, each saying what was read, its as-of time, and whether it was unavailable. Then the headline and sentences, which link to tiles in both directions on hover and keyboard focus. Sources are stated once for the answer, not per sentence, because the backend can't tie an arbitrary sentence to a source. Filing citations are the exception: they quote the source passage and link to the filing. A stopped or interrupted answer keeps its released sentences and is labeled incomplete. When an answer finishes, up to three suggested questions follow it. They come from fixed templates, never the model, and each names its position in full because questions carry no memory.

**Copy the prototype used that isn't supported, and must not ship:** "that you haven't opened yet" (Rundown stores no read state, so filing signals say when something was filed) and per-sentence source lines. "Nothing new" may only be said about sources actually checked.

### Status Chip (signature component)
`StatusChip` is the system's one reusable semantic-color primitive: a three-tone pill (`stale` / `error` / `flag`) that is the *only* place status color and accent color are allowed to render as a filled background. Every other component either uses neutral ink or the accent's text-only forms. Any new status meaning should extend this component's tone set rather than inventing a new color pairing elsewhere. Gain/loss fills on map tiles are separate and are governed by The Gain/Loss Color Rule.

### Provenance line (signature pattern)
Every provider-sourced value — portfolio freshness, fundamentals, news, filings — renders a trailing `text-xs text-ink-faint` line reading `{source} · as of {formatAsOf(timestamp)}` (or `{source} · {relative}` for news bylines). This mirrors the backend's `SourcedValue<T>` wrapper (`backend/app/schemas/common.py`) directly in the type layer (`lib/types.ts`) and is a hard product rule, not a nice-to-have — CLAUDE.md requires provenance and freshness on anything shown to the user. Any new data-bearing component must carry this line.

### Navigation
There is no persistent nav chrome. The assistant is the home screen, not a drawer: there's no floating trigger, and every path into a question leads to the one composer. In UI copy the assistant is called "Rundown."

### Holding Detail
`HoldingDetailPanel` shows one holding's quantity, price, cost basis, and account, its charts, its flag reason, and its supporting fundamentals, news, and filing. Only one is open at a time, and it never replaces the map as the place to ask a question.

## Do's and Don'ts

### Do:
- **Do** keep gain/loss figures in ink with a sign and a `▲`/`▼` glyph, and put any color behind them as a fill with a legend on screen.
- **Do** apply `tabular-nums` to every number that appears in a column or is compared row-to-row.
- **Do** attach a `{source} · as of {timestamp}` line to any value fetched from a provider, using `formatAsOf` for timestamped values.
- **Do** format date-only values (no time-of-day component, e.g. a filing date) with `formatDate`'s explicit `timeZone: "UTC"` — this is intentional, not a bug: a bare `YYYY-MM-DD` string parses as UTC midnight, and formatting it in the viewer's local zone can roll it back a day west of UTC. Don't remove the `timeZone: "UTC"` option.
- **Do** use the paper/surface tonal step (not a border) to distinguish content nested inside a card.
- **Do** keep shadows reserved for overlay elements and flat borders for everything in normal page flow.
- **Do** give every position its own tile at no less than 76×44px, and let the tile area scroll when they don't all fit.

### Don't:
- **Don't** use gain/loss color for anything beyond the fact it encodes, or use color to signal urgency, approval, or what to do next. Directive advice remains a legal boundary (Investment Advisers Act, CLAUDE.md hard rule 1), and this constrains any component that touches gain/loss.
- **Don't** use green and red for gain/loss. The pair fails the colorblind check, and red belongs to fetch errors.
- **Don't** reuse the status-color pair (amber/red) for anything other than data freshness or fetch errors. It must never double as a gain/loss or sentiment color.
- **Don't** ship a data point without a source and as-of timestamp, even in a compact or secondary UI placement.
- **Don't** introduce a second accent hue. The system's "Restrained" color strategy (per `PRODUCT.md`'s Brand Commitments) means one accent, used sparingly — not a rotating brand palette.
- **Don't** design new screens against dark mode yet; the system is light-mode only by a deliberate use-scene decision, not an oversight, and dark values haven't been established.
- **Don't** let an answer's model output choose what the map shows. Focus and sizing are derived by the backend from released sentences, from a closed set of held symbols and sizing modes.
