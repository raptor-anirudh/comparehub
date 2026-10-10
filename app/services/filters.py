"""Hard eligibility filters. These decide WHETHER a listing is eligible, never its rank.

Rules (documented in docs/architecture.md, "Search orchestration"):
- Budget: the advertised price is a lower bound of the total (charges are never negative),
  so a listing is excluded when it is *provably* over budget: advertised > max, or a
  known/estimated total > max. A listing whose total is unknown but whose advertised price
  is within budget is kept; ranking/UI must show that its total is unknown.
- Currency: a price in a different currency than the budget cannot be compared, so it is
  excluded rather than guessed at (no FX conversion).
- Required attributes: a hard requirement that cannot be verified excludes the listing.
  Exact (case-insensitive) value equality only; unit/variant normalization is Phase 6.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.comparisons.models import ProductQuery
from app.domain.money import Money
from app.domain.products.models import ProductResult


def _within_budget(result: ProductResult, limit: Money) -> bool:
    price = result.price
    if price.advertised.currency != limit.currency:
        return False
    if price.advertised.amount > limit.amount:
        return False
    total = price.total
    return total is None or total.amount <= limit.amount


def _has_required_attributes(result: ProductResult, required: dict[str, str]) -> bool:
    have = {k.lower(): v.strip().lower() for k, v in result.attributes.items()}
    return all(have.get(k.lower()) == v.strip().lower() for k, v in required.items())


def is_eligible(result: ProductResult, query: ProductQuery) -> bool:
    if query.max_price is not None and not _within_budget(result, query.max_price):
        return False
    return _has_required_attributes(result, query.required_attributes)


def apply_hard_filters(
    results: Iterable[ProductResult], query: ProductQuery
) -> tuple[list[ProductResult], int]:
    """Return (eligible results, number excluded)."""
    kept: list[ProductResult] = []
    excluded = 0
    for result in results:
        if is_eligible(result, query):
            kept.append(result)
        else:
            excluded += 1
    return kept, excluded
