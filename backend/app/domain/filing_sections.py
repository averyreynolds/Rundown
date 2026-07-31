"""Format-agnostic extraction of portfolio-relevant sections from SEC filings.

Pure functions over strings -- no I/O, no provider knowledge -- so the
whole thing is testable against synthetic fixtures without touching
EDGAR (CLAUDE.md's rule for `app/domain/`).

Why this exists
---------------
EDGAR filing HTML varies enormously between filers: inline XBRL wrapped
in `<ix:*>` tags, table-based page layout, `<font>`/`<span>` soup from a
dozen different document generators, hidden XBRL fact blocks, and no
semantic markup whatsoever. There is no `<section id="risk-factors">` to
query for. So this module works in two stages, and only the *second*
one depends on anything being consistent:

1. `filing_html_to_text` -- BeautifulSoup normalizes arbitrary markup
   into plain text. This handles the *markup* variation: it drops
   scripts, styles, and hidden inline-XBRL fact blocks (which the
   previous stdlib `HTMLParser` approach structurally could not, having
   no tree to query), and it inserts separators at block boundaries so
   adjacent table cells stop concatenating into `Revenue$1,234`. Inline
   elements are deliberately joined *without* a separator, since iXBRL
   wraps individual numbers and words mid-sentence -- separating those
   would shred every sentence in the document.

2. `segment_filing` -- regex segmentation on Regulation S-K **Item
   numbering**. This is the actual invariant worth keying on: item
   numbers and their ordering are legally mandated, so `Item 1A` means
   Risk Factors in every 10-K ever filed, regardless of how the filer's
   HTML looks.

Section text is always carried **verbatim**. Nothing here paraphrases,
reflows, or summarizes -- CLAUDE.md hard rule 2 requires filing-derived
claims to be traceable to source passages, which only holds if the text
the advisor cites into is character-for-character what EDGAR served.

What gets kept
--------------
Only the sections that can bear on a personal equity position. Item 1
(Business) and Item 8 (Financial Statements) are deliberately excluded:
Item 1 is long and largely static year to year, and FMP already supplies
the ratios that Item 8 backs. `FilingDocument.omitted_labels` records
what was left out so the advisor can say "Item 1 wasn't included in this
excerpt" rather than the misleading "the filing doesn't mention that."
"""

import re
import warnings
from dataclasses import dataclass
from typing import Any, Literal

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

# --- Stage 1: markup -> text ------------------------------------------------

# Dropped wholesale. The `ix:` entries are inline-XBRL machinery: SEC's
# iXBRL filings carry a large hidden block of tagged facts that renders
# as nothing in a browser but lands in extracted text as thousands of
# lines of context refs and unit declarations.
_DROPPED_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "ix:header",
        "ix:hidden",
        "ix:references",
        "ix:resources",
    }
)

_DISPLAY_NONE = re.compile(r"display\s*:\s*none", re.IGNORECASE)

# Tags after which a newline is inserted, so block structure survives
# into the plain text. Anything *not* listed is treated as inline and
# joined with no separator at all -- see this module's docstring for why
# that matters with inline XBRL.
_BLOCK_TAGS = (
    "p",
    "div",
    "tr",
    "li",
    "ul",
    "ol",
    "table",
    "section",
    "article",
    "header",
    "footer",
    "blockquote",
    "caption",
    "figure",
    "address",
    "center",
    "pre",
    "dl",
    "dt",
    "dd",
    "hr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
)

# Table cells get a tab rather than a newline, keeping a row on one line
# so financial tables stay column-readable instead of exploding into one
# line per cell.
_CELL_TAGS = ("td", "th")

# Non-breaking, figure, narrow and thin spaces -- EDGAR filings are full
# of them, often inside a heading itself ("Item&#160;1A"). Normalized to
# plain spaces so the heading regexes below don't miss on them. Written as
# escapes rather than literals so the distinction stays visible in source.
_UNICODE_SPACES = str.maketrans(dict.fromkeys("\xa0\u2007\u202f\u2009", " "))

_HTML_SNIFF = re.compile(r"<\s*(?:!doctype|html|body|div|p|table|span|font|ix:)", re.IGNORECASE)


def looks_like_html(raw: str) -> bool:
    """`True` if `raw` appears to be an HTML document rather than plain text.

    Pre-2001 EDGAR filings are plain ASCII with no markup at all; running
    them through an HTML parser is wasted work at best.
    """
    return _HTML_SNIFF.search(raw) is not None


def filing_html_to_text(raw: str) -> str:
    """Normalize filing markup (or plain text) into clean, block-structured text.

    Verbatim in content -- only markup, hidden nodes, and redundant
    whitespace are removed. No wording is altered.
    """
    if not looks_like_html(raw):
        return _normalize_whitespace(raw)

    # Filings are XHTML, so bs4 warns that an HTML parser is being used on
    # an XML document. The HTML parser is the deliberate choice: it's the
    # tolerant one, and EDGAR documents are frequently not well-formed.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(raw, "lxml")

    for tag in soup.find_all(True):
        if tag.decomposed:
            continue
        if _should_drop(tag):
            tag.decompose()

    for tag in soup.find_all("br"):
        tag.replace_with("\n")
    for tag in soup.find_all(_CELL_TAGS):
        tag.append("\t")
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.append("\n")

    return _normalize_whitespace(soup.get_text())


def _should_drop(tag: Tag) -> bool:
    if tag.name.lower() in _DROPPED_TAGS:
        return True
    style = tag.get("style")
    return isinstance(style, str) and _DISPLAY_NONE.search(style) is not None


def _normalize_whitespace(text: str) -> str:
    lines = []
    for raw_line in text.translate(_UNICODE_SPACES).split("\n"):
        line = re.sub(r"[ \r\f\v]+", " ", raw_line)
        line = re.sub(r"\t+", "\t", line).strip()
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


# --- Stage 2: text -> Item sections -----------------------------------------

# Anchored at line start, and tolerant of the punctuation drift between
# filers: "Item 1A.", "ITEM 1A -", "Item 1A—Risk Factors", "Item 1A:".
# The trailing lookahead stops "Item 1" from matching inside "Item 10"
# while still allowing a heading that ends the line.
_ITEM_HEADING = re.compile(
    r"^[ \t]*ITEM[ \t.]*(?P<item>\d{1,2}[A-Z]?)(?=[ \t.:)\u2014\u2013\u2010-]|$)",
    re.IGNORECASE | re.MULTILINE,
)

_PART_HEADING = re.compile(
    r"^[ \t]*PART[ \t]+(?P<part>IV|III|II|I)(?=[ \t.:)\u2014\u2013\u2010-]|$)",
    re.IGNORECASE | re.MULTILINE,
)

# A real Item heading sits alone on a short line. This rejects prose that
# happens to begin with a cross-reference ("Item 8 of this Annual Report
# contains ...") from being mistaken for a section boundary.
_MAX_HEADING_LINE_CHARS = 200

# Enough to reject a table-of-contents entry (heading text plus a page
# number, with nothing after it) without discarding a legitimately terse
# section -- "Item 3. Legal Proceedings: see Note 12" is a real filing.
_MIN_SECTION_BODY_CHARS = 40

# SEC rules let a filer satisfy an Item by pointing at content elsewhere
# instead of restating it, and large filers lean on this heavily. In
# JPMorgan's 10-K, Item 7 (MD&A) is 300 characters -- "appears on pages
# 46-160" -- and Item 3 is 76. Segmentation is correct in those cases;
# the section really does say only that. But handing the advisor a page
# reference and labeling it MD&A is the kind of silently-wrong grounding
# CLAUDE.md hard rule 6 exists to prevent, so pointers get flagged.
#
# Length is the detector rather than phrase matching, because the
# phrasing varies far more than the length does. Across 14 real filings
# from 7 filers, deferrals appeared as "incorporated by reference," "refer
# to Note 30," "see Note 13," "appears on pages 46-160," "please refer to
# 'Risk Factors' in Part I," and "no material changes since the 10-K" --
# but every one of those sections was under 800 characters, while the
# smallest genuinely substantive section was 1,283. The threshold sits in
# that gap.
#
# The cost of the two error directions is deliberately asymmetric: a false
# positive adds one hedging sentence to the context, while a false
# negative lets the advisor treat a page number as management's discussion
# of the business. Nothing is dropped either way -- the section text is
# still sent, just labeled for what it is.
_SUBSTANTIVE_MIN_CHARS = 1_000


@dataclass(frozen=True, slots=True)
class FilingSection:
    """One extracted Item section, its text verbatim from the filing."""

    key: str
    label: str
    text: str
    is_pointer: bool = False


def _is_pointer(text: str) -> bool:
    """`True` if this section is too short to be carrying its Item's substance."""
    return len(text) < _SUBSTANTIVE_MIN_CHARS


@dataclass(frozen=True, slots=True)
class SegmentedFiling:
    """Every portfolio-relevant section found in one filing.

    `mode` records how the text was obtained, which callers need in order
    to describe the excerpt honestly:

    - `sections`: Item segmentation succeeded; `sections` is the
      portfolio-relevant subset and `missing_labels` lists wanted
      sections that weren't found.
    - `whole_document`: the form isn't segmented by policy (8-K, which is
      short enough to pass through intact).
    - `unsegmented`: segmentation found no usable Item headings, so the
      whole document is carried as one pseudo-section rather than
      silently returning nothing.
    """

    form: str
    sections: tuple[FilingSection, ...]
    missing_labels: tuple[str, ...]
    policy_excluded_labels: tuple[str, ...]
    mode: Literal["sections", "whole_document", "unsegmented"]

    def to_cacheable(self) -> dict[str, Any]:
        """A JSON-serializable form, for `CacheRepository.set`."""
        return {
            "form": self.form,
            "sections": [
                {"key": s.key, "label": s.label, "text": s.text, "is_pointer": s.is_pointer}
                for s in self.sections
            ],
            "missing_labels": list(self.missing_labels),
            "policy_excluded_labels": list(self.policy_excluded_labels),
            "mode": self.mode,
        }

    @classmethod
    def from_cacheable(cls, payload: dict[str, Any]) -> "SegmentedFiling":
        return cls(
            form=payload["form"],
            sections=tuple(
                FilingSection(
                    key=s["key"], label=s["label"], text=s["text"], is_pointer=s["is_pointer"]
                )
                for s in payload["sections"]
            ),
            missing_labels=tuple(payload["missing_labels"]),
            policy_excluded_labels=tuple(payload["policy_excluded_labels"]),
            mode=payload["mode"],
        )


@dataclass(frozen=True, slots=True)
class _FormPolicy:
    """Which Items to keep for one form type, and in what priority."""

    titles: dict[str, str]
    priority: tuple[str, ...]
    part_scoped: bool
    excluded_labels: tuple[str, ...]


# 10-K Item numbers are unique document-wide, so they need no Part
# anchoring. Priority orders the budget fill: MD&A and Risk Factors are
# the sections a position holder actually needs.
_TEN_K_POLICY = _FormPolicy(
    titles={
        "1A": "Risk Factors",
        "3": "Legal Proceedings",
        "5": (
            "Market for Registrant's Common Equity, Related Stockholder Matters "
            "and Issuer Purchases of Equity Securities"
        ),
        "7": (
            "Management's Discussion and Analysis of Financial Condition and Results of Operations"
        ),
        "7A": "Quantitative and Qualitative Disclosures About Market Risk",
    },
    priority=("7", "1A", "7A", "5", "3"),
    part_scoped=False,
    excluded_labels=(
        "Item 1. Business",
        "Item 8. Financial Statements and Supplementary Data",
        "Items 9-16 (controls, governance, executive compensation, exhibits)",
    ),
)

# A 10-Q reuses Item numbers across Part I and Part II -- "Item 1" is
# Financial Statements in Part I and Legal Proceedings in Part II -- so
# these keys must be Part-anchored to mean anything.
_TEN_Q_POLICY = _FormPolicy(
    titles={
        "I:2": (
            "Management's Discussion and Analysis of Financial Condition and Results of Operations"
        ),
        "I:3": "Quantitative and Qualitative Disclosures About Market Risk",
        "II:1": "Legal Proceedings",
        "II:1A": "Risk Factors",
    },
    priority=("I:2", "II:1A", "I:3", "II:1"),
    part_scoped=True,
    excluded_labels=(
        "Part I, Item 1. Financial Statements",
        "Part I, Item 4 and Part II, Items 2-6 (controls, equity sales, exhibits)",
    ),
)

_POLICIES = {"10-K": _TEN_K_POLICY, "10-Q": _TEN_Q_POLICY}

# 8-Ks are single-event disclosures, typically a few pages, and use an
# entirely different numbering scheme (2.02 Results of Operations, 5.02
# Officer Departures, 8.01 Other Events). Segmenting them would cost more
# than it saves, so they pass through whole.
_WHOLE_DOCUMENT_FORMS = frozenset({"8-K"})


def normalize_form(form: str) -> str:
    """Collapse amendment and legacy suffixes: `10-K/A` and `10-K405` -> `10-K`."""
    normalized = form.strip().upper()
    for base in ("10-K", "10-Q", "8-K"):
        if normalized.startswith(base):
            return base
    return normalized


def segment_filing(raw: str, form: str) -> SegmentedFiling:
    """Extract `form`'s portfolio-relevant Item sections from raw filing text/HTML.

    Args:
        raw: The filing document exactly as EDGAR served it -- HTML,
            inline XBRL, or (for old filings) plain text.
        form: The EDGAR form type, e.g. `"10-K"`. Amendment suffixes are
            normalized away.

    Returns:
        A `SegmentedFiling` whose `sections` are in document order and
        whose text is verbatim. Never raises on unrecognized structure:
        a filing whose Item headings can't be found comes back with
        `mode="unsegmented"` and the whole document as one section.
    """
    text = filing_html_to_text(raw)
    normalized_form = normalize_form(form)

    policy = _POLICIES.get(normalized_form)
    if policy is None or normalized_form in _WHOLE_DOCUMENT_FORMS:
        return SegmentedFiling(
            form=normalized_form,
            sections=(FilingSection(key="full", label=f"{normalized_form} filing", text=text),),
            missing_labels=(),
            policy_excluded_labels=(),
            mode="whole_document",
        )

    candidates = _collect_candidates(text, part_scoped=policy.part_scoped)
    sections = []
    missing = []
    for key in policy.titles:
        label = _format_label(key, policy.titles[key], part_scoped=policy.part_scoped)
        best = candidates.get(key)
        if best is None:
            missing.append(label)
            continue
        sections.append(
            (
                best[0],
                FilingSection(key=key, label=label, text=best[1], is_pointer=_is_pointer(best[1])),
            )
        )

    if not sections:
        return SegmentedFiling(
            form=normalized_form,
            sections=(
                FilingSection(
                    key="full", label=f"{normalized_form} filing (unsegmented)", text=text
                ),
            ),
            missing_labels=tuple(missing),
            policy_excluded_labels=(),
            mode="unsegmented",
        )

    sections.sort(key=lambda pair: pair[0])
    return SegmentedFiling(
        form=normalized_form,
        sections=tuple(section for _, section in sections),
        missing_labels=tuple(missing),
        policy_excluded_labels=policy.excluded_labels,
        mode="sections",
    )


def _format_label(key: str, title: str, *, part_scoped: bool) -> str:
    if part_scoped:
        part, _, item = key.partition(":")
        return f"Part {part}, Item {item}. {title}"
    return f"Item {key}. {title}"


def _collect_candidates(text: str, *, part_scoped: bool) -> dict[str, tuple[int, str]]:
    """Map each Item key to its `(position, body_text)` best occurrence.

    Every Item heading appears at least twice in a real filing -- once in
    the table of contents, once in the body -- and sometimes a third time
    in a trailing cross-reference index. Rather than guessing by
    position, this picks the occurrence with the longest body, which
    rejects both the TOC (whose "body" is a page number) and index
    entries without assuming either sits at a particular place in the
    document.
    """
    markers = _find_markers(text)
    if not markers:
        return {}

    best: dict[str, tuple[int, str]] = {}
    current_part = ""
    for index, (position, body_start, kind, value) in enumerate(markers):
        if kind == "part":
            current_part = value
            continue

        segment_end = markers[index + 1][0] if index + 1 < len(markers) else len(text)
        body = text[body_start:segment_end].strip()
        if len(body) < _MIN_SECTION_BODY_CHARS:
            continue

        key = f"{current_part}:{value}" if part_scoped else value
        if part_scoped and not current_part:
            continue

        existing = best.get(key)
        if existing is None or len(body) > len(existing[1]):
            best[key] = (position, body)

    return best


def _find_markers(text: str) -> list[tuple[int, int, str, str]]:
    """All Part/Item heading positions, in document order.

    Each entry is `(position, body_start, kind, value)`, where
    `body_start` is the offset just past the heading's own line.
    """
    markers: list[tuple[int, int, str, str]] = []
    for kind, pattern, group in (
        ("part", _PART_HEADING, "part"),
        ("item", _ITEM_HEADING, "item"),
    ):
        for match in pattern.finditer(text):
            line_end = text.find("\n", match.start())
            if line_end == -1:
                line_end = len(text)
            if line_end - match.start() > _MAX_HEADING_LINE_CHARS:
                continue
            value = match.group(group).upper()
            markers.append((match.start(), min(line_end + 1, len(text)), kind, value))

    markers.sort(key=lambda marker: marker[0])
    return markers


# --- Assembling the excerpt sent to the model -------------------------------


@dataclass(frozen=True, slots=True)
class FilingDocument:
    """A budget-fitted excerpt plus an honest account of what's in it."""

    text: str
    included_labels: tuple[str, ...]
    omitted_labels: tuple[str, ...]
    pointer_labels: tuple[str, ...]
    was_truncated: bool

    def provenance_note(self) -> str:
        """A line for the model's context describing this excerpt's scope.

        Without this, CLAUDE.md hard rule 2 ("say so when the context
        doesn't cover something") produces a misleading answer: the model
        reports that the *filing* is silent on a topic when in fact only
        the *excerpt* is.
        """
        included = "; ".join(self.included_labels) if self.included_labels else "none"
        note = f"The attached filing excerpt contains these sections only: {included}."
        if self.omitted_labels:
            note += (
                " These sections of the filing were NOT included and you have no "
                f"information about them: {'; '.join(self.omitted_labels)}. If the "
                "question concerns them, say they are outside this excerpt rather "
                "than saying the filing does not address them."
            )
        if self.pointer_labels:
            note += (
                " These sections are included but are too short to contain the "
                "substance of what the Item covers -- filers routinely satisfy an "
                "Item by cross-referencing a financial statement note, an exhibit, "
                "or a prior filing instead of restating it, and the material they "
                f"point to is NOT included here: {'; '.join(self.pointer_labels)}. "
                "Read what they say, but do not treat them as the section's full "
                "content, and say so if asked about them."
            )
        if self.was_truncated:
            note += " The final section is cut off mid-way to fit a length limit."
        return note


def build_filing_document(segmented: SegmentedFiling, max_chars: int) -> FilingDocument:
    """Fit `segmented` into `max_chars`, dropping the least relevant sections first.

    Sections are *selected* in policy priority order (so a filing too
    large to fit loses Legal Proceedings before it loses MD&A) but
    *emitted* in document order. This is the part that replaces a plain
    `text[:max_chars]` head-truncation, which on a large 10-K kept the
    cover page and table of contents and cut off before MD&A entirely.

    Args:
        segmented: Output of `segment_filing`.
        max_chars: Character budget for the assembled excerpt. Must be
            positive.

    Raises:
        ValueError: if `max_chars` is not positive.
    """
    if max_chars <= 0:
        raise ValueError(f"max_chars must be positive, got {max_chars}.")

    policy = _POLICIES.get(segmented.form)
    order = policy.priority if policy is not None else ()
    by_key = {section.key: section for section in segmented.sections}

    ranked = [by_key[key] for key in order if key in by_key]
    ranked.extend(section for section in segmented.sections if section.key not in set(order))

    kept: dict[str, str] = {}
    dropped: list[str] = []
    was_truncated = False
    remaining = max_chars

    for section in ranked:
        # The blank line between sections is part of the final string, so
        # it has to come out of the budget too -- charging it for every
        # section after the first makes the accounting exact against the
        # `_SECTION_SEPARATOR.join` below.
        overhead = len(_section_header(section.label))
        if kept:
            overhead += len(_SECTION_SEPARATOR)
        if remaining - overhead < _MIN_SECTION_BODY_CHARS:
            dropped.append(section.label)
            continue
        budget = remaining - overhead
        if len(section.text) <= budget:
            kept[section.key] = section.text
            remaining -= overhead + len(section.text)
        else:
            kept[section.key] = section.text[:budget]
            remaining = 0
            was_truncated = True

    parts = []
    included_labels = []
    pointer_labels = []
    for section in segmented.sections:
        if section.key not in kept:
            continue
        parts.append(_section_header(section.label) + kept[section.key])
        included_labels.append(section.label)
        if section.is_pointer:
            pointer_labels.append(section.label)

    return FilingDocument(
        text=_SECTION_SEPARATOR.join(parts),
        included_labels=tuple(included_labels),
        omitted_labels=tuple(dropped) + segmented.missing_labels + segmented.policy_excluded_labels,
        pointer_labels=tuple(pointer_labels),
        was_truncated=was_truncated,
    )


_SECTION_SEPARATOR = "\n\n"


def _section_header(label: str) -> str:
    return f"===== {label} =====\n"
