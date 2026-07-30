"""Synthetic Finnhub `company-news` fixture data.

Fabricated content shaped like a real Finnhub response, not real news
data or a real company's coverage.
"""

from typing import Any


def synthetic_news_items(count: int = 2) -> list[dict[str, Any]]:
    """`count` synthetic articles, in Finnhub's raw (pre-`symbol`-injection) shape."""
    return [
        {
            "category": "company",
            "datetime": 1_700_000_000 + i,
            "headline": f"Synthetic headline {i}",
            "id": i,
            "image": "https://example.com/image.png",
            "related": "",
            "source": f"Synthetic Wire {i}",
            "summary": f"Synthetic summary {i}.",
            "url": f"https://example.com/article-{i}",
        }
        for i in range(count)
    ]
