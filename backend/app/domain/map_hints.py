"""What the portfolio map should show for one released sentence of an answer.

Derived deterministically from the sentence's words, rather than asking the model
to direct the screen: the model's output format doesn't change, there's nothing
structured to validate, and the result can only ever be a held symbol or one of a
closed set of sizing modes. A wrong guess affects highlighting, never a figure.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.domain.symbol_matching import HeldSymbol, match_held_symbols

_GAIN_TERMS = re.compile(
    r"\b(gains?|gained|loss|losses|profits?|unrealized|p&l)\b|\b(since|from) cost\b",
    re.IGNORECASE,
)
_COST_TERMS = re.compile(r"\b(cost|costs|paid)\b", re.IGNORECASE)


class MapSizing(StrEnum):
    VALUE = "value"
    COST = "cost"
    GAIN = "gain"


@dataclass(frozen=True, slots=True)
class MapHint:
    focus: tuple[str, ...]
    sizing: MapSizing


def derive_map_hint(
    sentence: str, held: Sequence[HeldSymbol], previous_focus: tuple[str, ...]
) -> MapHint:
    """Return the focus and sizing for `sentence`.

    Args:
        sentence: One released sentence of an answer.
        held: The positions the user actually holds.
        previous_focus: The prior sentence's focus, kept when this one names no
            held position: "The position cost $4,400" should stay on NVDA.
    """
    named = match_held_symbols(sentence, held)
    return MapHint(focus=tuple(named) or previous_focus, sizing=_sizing_for(sentence))


def _sizing_for(sentence: str) -> MapSizing:
    if _GAIN_TERMS.search(sentence):
        return MapSizing.GAIN
    if _COST_TERMS.search(sentence):
        return MapSizing.COST
    return MapSizing.VALUE
