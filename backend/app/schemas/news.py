"""Response schema for `GET /news`."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NewsItem(BaseModel):
    """One news item for a holding, as reported by Finnhub's `company-news` endpoint.

    `publisher` (not `source`) deliberately avoids colliding in meaning
    with `SourcedValue.source` (which names the *data provider*, "Finnhub",
    on the wrapping envelope) -- this field names the individual article's
    outlet (e.g. "Reuters"), a different concept at a different level.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    symbol: str
    headline: str
    summary: str
    url: str
    publisher: str = Field(alias="source")
    published_at: datetime = Field(alias="datetime")

    @field_validator("published_at", mode="before")
    @classmethod
    def _parse_unix_timestamp(cls, value: object) -> object:
        """Finnhub reports `datetime` as a Unix timestamp (seconds), not ISO-8601."""
        if isinstance(value, int | float):
            return datetime.fromtimestamp(value, tz=UTC)
        return value
