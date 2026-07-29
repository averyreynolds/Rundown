"""Provider-independent value types shared across the domain layer.

`Holding` is the one shape every downstream consumer -- the portfolio
endpoint (U4) and the advisor's context assembly (U8) -- agrees on.
`services/snaptrade_service.py` (U4) maps SnapTrade's response shape into
`Holding`, never the other way around, so this module stays testable with
synthetic fixtures and ignorant of any specific broker's API.

Every monetary/quantity field is a `Decimal`, not `float`: this layer
computes the numbers shown to a user as their real money, and binary
floating point silently accumulates rounding error that has no place in
financial arithmetic.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Holding:
    """A single position in a portfolio, as of some point in time.

    `market_value` is carried as reported by the broker rather than
    re-derived as `quantity * current_price` here -- the broker's own
    figure is authoritative and may reflect intraday timing or rounding
    this layer has no visibility into.
    """

    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    current_price: Decimal
    market_value: Decimal
