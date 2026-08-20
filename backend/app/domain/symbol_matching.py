"""Which of the user's held symbols a question mentions, by ticker or company name."""

import re
from collections.abc import Sequence
from dataclasses import dataclass

# Stripped from the end of a company name (repeatedly) before phrase-matching,
# so "Compass, Inc." and "Alphabet Inc. Class A" normalize to "Compass" and
# "Alphabet" -- the parts of a registered name that are actually likely to
# appear in a casually-phrased question.
_SUFFIX_PATTERN = re.compile(
    r"[,.]?\s*\b(incorporated|inc|corporation|corp|co|company|"
    r"ltd|limited|llc|plc|holdings?|class\s+[abc])\b\.?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class HeldSymbol:
    """One held position's symbol and its registered company name, if known."""

    symbol: str
    company_name: str | None = None


def match_held_symbols(question: str, held: Sequence[HeldSymbol]) -> list[str]:
    """Return which of `held`'s symbols are mentioned in `question`.

    Matching is deliberately literal: a ticker matches as a whole word, and a
    company name matches only as its full normalized phrase (corporate
    suffixes like "Inc." stripped first) -- never on a single word out of a
    multi-word name. This keeps false positives to the same class as an
    ordinary ticker collision (a short/common word), not a broader fuzzy
    match.

    Args:
        question: The user's question text.
        held: The symbols currently held, each with an optional resolved
            company name (`None` when no name is on record for it).

    Returns:
        Matched symbols, deduplicated, in `held`'s order -- not the order
        they appear in the question.
    """
    if not question or not held:
        return []

    matched: list[str] = []
    seen: set[str] = set()
    for entry in held:
        if entry.symbol in seen:
            continue
        if _word_pattern(entry.symbol).search(question):
            matched.append(entry.symbol)
            seen.add(entry.symbol)
            continue
        normalized = _normalize_company_name(entry.company_name) if entry.company_name else ""
        if normalized and _word_pattern(normalized).search(question):
            matched.append(entry.symbol)
            seen.add(entry.symbol)

    return matched


def _normalize_company_name(name: str) -> str:
    """Strip trailing corporate suffixes/punctuation, for phrase matching."""
    stripped = name.strip()
    while True:
        without_suffix = _SUFFIX_PATTERN.sub("", stripped).strip().rstrip(",.")
        if without_suffix == stripped:
            return stripped
        stripped = without_suffix


def _word_pattern(phrase: str) -> re.Pattern[str]:
    r"""A case-insensitive, word-boundary pattern matching `phrase` verbatim.

    Each word is escaped individually and joined with `\s+` so minor
    spacing differences in the question (extra spaces, a newline) don't
    break a multi-word match -- `re.escape` on the whole phrase at once
    would escape the spaces themselves (`"a b"` -> `r"a\ b"`), which a
    literal-whitespace pattern would then fail to match against normal
    question text.
    """
    escaped = r"\s+".join(re.escape(word) for word in phrase.split())
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)
