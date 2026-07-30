"""Concentration risk: which holdings are outsized, and the largest few."""

from collections.abc import Sequence
from decimal import Decimal

from app.domain.allocation import Allocation


def flag_concentrated(
    allocations: Sequence[Allocation], threshold_pct: Decimal
) -> list[Allocation]:
    """Return allocations whose percent exceeds `threshold_pct`.

    Args:
        allocations: Output of `compute_allocation`.
        threshold_pct: Percent (0-100) above which a holding is flagged,
            e.g. `Decimal("20")` for a 20% concentration threshold.

    Returns:
        The subset of `allocations` strictly above the threshold, in input
        order. Empty if none exceed it (including when `allocations` is
        empty).
    """
    return [allocation for allocation in allocations if allocation.percent > threshold_pct]


def top_n_by_weight(allocations: Sequence[Allocation], n: int) -> list[Allocation]:
    """Return the `n` largest allocations, descending by weight.

    Args:
        allocations: Output of `compute_allocation`.
        n: Maximum number of allocations to return. If `n` exceeds
            `len(allocations)`, every allocation is returned.

    Returns:
        Up to `n` allocations sorted by `percent` descending.

    Raises:
        ValueError: if `n` is negative.
    """
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}.")

    return sorted(allocations, key=lambda allocation: allocation.percent, reverse=True)[:n]
