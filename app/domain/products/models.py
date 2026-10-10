"""Product-side domain models: results, pricing, provenance."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    computed_field,
    field_validator,
    model_validator,
)

from app.domain.enums import (
    ChargeStatus,
    SourceKind,
    StockStatus,
    TaxTreatment,
    TotalKind,
)
from app.domain.money import Money


class DataProvenance(BaseModel):
    """Where and when a result was obtained."""

    model_config = ConfigDict(frozen=True)

    provider_id: str
    source_kind: SourceKind
    source_url: HttpUrl | None = None
    retrieved_at: datetime
    ttl_seconds: int | None = Field(default=None, gt=0)
    # Optional per-field confidence in [0, 1], e.g. for extracted (non-API) data.
    field_confidence: dict[str, float] = Field(default_factory=dict)

    @field_validator("retrieved_at")
    @classmethod
    def _require_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("field_confidence")
    @classmethod
    def _confidence_range(cls, value: dict[str, float]) -> dict[str, float]:
        for name, score in value.items():
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"confidence for {name!r} must be within [0, 1]")
        return value

    def effective_kind(self, now: datetime) -> SourceKind:
        """Source kind after applying the TTL: expired live/cached data is STALE.

        MOCK, ESTIMATED and UNAVAILABLE are never upgraded or downgraded by age.
        """
        if self.source_kind in (SourceKind.LIVE, SourceKind.CACHED) and self.ttl_seconds:
            age = (now - self.retrieved_at).total_seconds()
            if age > self.ttl_seconds:
                return SourceKind.STALE
        return self.source_kind


class Charge(BaseModel):
    """A mandatory extra charge (delivery, platform fee, ...).

    UNKNOWN means the provider did not tell us; it is never treated as zero.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=64)
    status: ChargeStatus
    amount: Money | None = None
    is_estimate: bool = False

    @model_validator(mode="after")
    def _amount_matches_status(self) -> Self:
        if self.status is ChargeStatus.KNOWN and self.amount is None:
            raise ValueError("a KNOWN charge requires an amount")
        if self.status is not ChargeStatus.KNOWN and self.amount is not None:
            raise ValueError("amount is only allowed when status is KNOWN")
        if self.is_estimate and self.status is not ChargeStatus.KNOWN:
            raise ValueError("is_estimate only applies to KNOWN charges")
        return self


class PriceBreakdown(BaseModel):
    """Advertised price plus mandatory charges, with an honest total.

    The total is only KNOWN when the provider asserts the charge list is
    complete (`charges_complete`) and every charge is known and firm.
    """

    model_config = ConfigDict(frozen=True)

    advertised: Money
    charges: tuple[Charge, ...] = ()
    charges_complete: bool = False
    tax_treatment: TaxTreatment = TaxTreatment.UNKNOWN

    @model_validator(mode="after")
    def _single_currency(self) -> Self:
        for charge in self.charges:
            if charge.amount and charge.amount.currency != self.advertised.currency:
                raise ValueError("all charges must use the advertised price's currency")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_kind(self) -> TotalKind:
        if not self.charges_complete:
            return TotalKind.UNKNOWN
        if any(c.status is ChargeStatus.UNKNOWN for c in self.charges):
            return TotalKind.UNKNOWN
        if any(c.is_estimate for c in self.charges):
            return TotalKind.ESTIMATED
        return TotalKind.KNOWN

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total(self) -> Money | None:
        """Sum of advertised price and known charges; None when the total is unknown."""
        if self.total_kind is TotalKind.UNKNOWN:
            return None
        result = self.advertised
        for charge in self.charges:
            if charge.amount is not None:
                result = result + charge.amount
        return result


class Availability(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: StockStatus = StockStatus.UNKNOWN
    delivery_days_min: int | None = Field(default=None, ge=0)
    delivery_days_max: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        lo, hi = self.delivery_days_min, self.delivery_days_max
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("delivery_days_min must not exceed delivery_days_max")
        return self


class ReturnPolicy(BaseModel):
    """None means unknown, not 'no returns'."""

    model_config = ConfigDict(frozen=True)

    returnable: bool | None = None
    window_days: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=500)


class Warranty(BaseModel):
    """None means unknown, not 'no warranty'."""

    model_config = ConfigDict(frozen=True)

    months: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=500)


class ProductResult(BaseModel):
    """A normalized listing from one provider."""

    model_config = ConfigDict(frozen=True)

    provider_id: str
    listing_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=300)
    brand: str | None = None
    model: str | None = None
    identifiers: dict[str, str] = Field(default_factory=dict)
    # Raw provider-supplied attributes. Normalization/matching happens later.
    attributes: dict[str, str] = Field(default_factory=dict)
    price: PriceBreakdown
    availability: Availability = Field(default_factory=Availability)
    return_policy: ReturnPolicy = Field(default_factory=ReturnPolicy)
    warranty: Warranty = Field(default_factory=Warranty)
    seller: str | None = None
    url: HttpUrl | None = None
    provenance: DataProvenance

    @model_validator(mode="after")
    def _provider_ids_agree(self) -> Self:
        if self.provenance.provider_id != self.provider_id:
            raise ValueError("provenance.provider_id must match provider_id")
        return self
