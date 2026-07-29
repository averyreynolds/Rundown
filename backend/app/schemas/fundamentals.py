"""Response schema for `GET /fundamentals/{symbol}`."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class FundamentalsSnapshot(BaseModel):
    """A symbol's key ratios and TTM metrics, merged from FMP's `/stable/ratios`
    and `/stable/key-metrics-ttm` responses.

    Field selection favors the ratios most relevant to a holdings dashboard
    over exhaustively mirroring FMP's full response shape -- this is the
    frontend-facing contract, not a raw passthrough. Every field is
    optional: FMP omits some ratios for certain symbols (e.g. financials
    or REITs), and this plan has no live API key to verify the exact
    "stable" field-naming against a real response, so the service (and
    this schema, via `extra="ignore"`) is deliberately tolerant of a
    missing or differently-named field rather than failing hard on it --
    verify field names against a live response once real credentials are
    available.
    """

    # FMP's JSON fields are camelCase (e.g. `priceToEarningsRatio`); this
    # model's field names are snake_case per project convention.
    # `alias_generator=to_camel` maps between the two so `model_validate`
    # on a raw FMP response actually populates every field instead of
    # silently leaving them at their `None` defaults, while
    # `populate_by_name=True` still allows constructing the model directly
    # with snake_case kwargs (e.g. in tests).
    #
    # `to_camel` titlecases each underscore-separated word naively, so it
    # gets acronym-suffixed fields wrong: `to_camel("revenue_per_share_ttm")`
    # produces "revenuePerShareTtm", not FMP's actual "revenuePerShareTTM"
    # (caught by this module's own test suite). Every `*_ttm` field below
    # needs an explicit `Field(alias=...)`, which always overrides the
    # generator, to match FMP's real casing.
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )

    symbol: str
    price_to_earnings_ratio: Decimal | None = None
    price_to_book_ratio: Decimal | None = None
    debt_to_equity_ratio: Decimal | None = None
    current_ratio: Decimal | None = None
    net_profit_margin: Decimal | None = None
    return_on_equity_ttm: Decimal | None = Field(default=None, alias="returnOnEquityTTM")
    revenue_per_share_ttm: Decimal | None = Field(default=None, alias="revenuePerShareTTM")
    net_income_per_share_ttm: Decimal | None = Field(
        default=None, alias="netIncomePerShareTTM"
    )
