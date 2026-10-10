"""Query, preference and response models for a comparison search."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.domain.enums import Category, RankingMode, SearchState
from app.domain.money import Money
from app.domain.products.models import ProductResult
from app.domain.providers.models import ProviderSearchStatus, ProviderSelection


class ProductQuery(BaseModel):
    """What the user wants. Everything here is a HARD constraint."""

    # Stripping makes a whitespace-only query fail min_length instead of matching everything.
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=200)
    market: str = Field(default="IN", pattern=r"^[A-Z]{2}$")
    max_price: Money | None = None
    # Hard attribute requirements, e.g. {"capacity_gb": "64"}.
    required_attributes: dict[str, str] = Field(default_factory=dict, max_length=20)


class ComparisonPreference(BaseModel):
    """How to order eligible results. Never affects eligibility."""

    model_config = ConfigDict(frozen=True)

    mode: RankingMode = RankingMode.LOWEST_TOTAL_COST
    preferred_brands: tuple[str, ...] = ()


class SearchQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: Category
    product: ProductQuery
    selection: ProviderSelection
    preference: ComparisonPreference = Field(default_factory=ComparisonPreference)


class SearchResponse(BaseModel):
    """Results plus a status for EVERY selected provider."""

    model_config = ConfigDict(frozen=True)

    search_id: UUID = Field(default_factory=uuid4)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    results: tuple[ProductResult, ...] = ()
    provider_statuses: tuple[ProviderSearchStatus, ...] = ()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_partial(self) -> bool:
        """True when at least one provider did not return usable data."""
        ok = {SearchState.SUCCESS, SearchState.EMPTY}
        return any(s.state not in ok for s in self.provider_statuses)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_failed(self) -> bool:
        ok = {SearchState.SUCCESS, SearchState.EMPTY}
        return bool(self.provider_statuses) and all(
            s.state not in ok for s in self.provider_statuses
        )
