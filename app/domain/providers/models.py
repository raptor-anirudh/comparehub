"""Provider-side domain models."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import Category, ProviderStatus, SearchState

PROVIDER_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]{1,39}$"


class ProviderCapability(BaseModel):
    """What a provider can do for one category."""

    model_config = ConfigDict(frozen=True)

    category: Category
    markets: frozenset[str] = frozenset({"IN"})
    # Filters the provider can apply server-side. The search service still
    # enforces hard filters itself, so this is an optimization hint only.
    supported_filters: frozenset[str] = frozenset()


class Provider(BaseModel):
    """Static description of a registered provider."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(pattern=PROVIDER_ID_PATTERN)
    display_name: str = Field(min_length=1, max_length=80)
    capabilities: tuple[ProviderCapability, ...] = Field(min_length=1)
    status: ProviderStatus = ProviderStatus.ENABLED
    unavailable_reason: str | None = None
    # True for demonstration providers whose data is synthetic.
    is_demo: bool = False

    @model_validator(mode="after")
    def _reason_when_unavailable(self) -> Provider:
        if self.status is ProviderStatus.UNAVAILABLE and not self.unavailable_reason:
            raise ValueError("UNAVAILABLE providers must state unavailable_reason")
        return self

    def capability_for(self, category: Category) -> ProviderCapability | None:
        return next((c for c in self.capabilities if c.category is category), None)


class ProviderSelection(BaseModel):
    """The providers a user chose to search."""

    model_config = ConfigDict(frozen=True)

    provider_ids: tuple[str, ...] = Field(min_length=0, max_length=20)

    @field_validator("provider_ids")
    @classmethod
    def _valid_and_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for pid in value:
            if not re.fullmatch(PROVIDER_ID_PATTERN, pid):
                raise ValueError(f"invalid provider id: {pid!r}")
        if len(set(value)) != len(value):
            raise ValueError("provider_ids must be unique")
        return value


class ProviderHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_id: str
    healthy: bool
    detail: str | None = None


class ProviderSearchStatus(BaseModel):
    """Outcome of searching one provider. Safe to show to users."""

    model_config = ConfigDict(frozen=True)

    provider_id: str
    state: SearchState
    result_count: int = Field(default=0, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    message: str | None = Field(default=None, max_length=300)
    retry_after_seconds: int | None = Field(default=None, ge=0)
