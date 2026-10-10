"""Deterministic mock e-commerce adapters (DEMO DATA ONLY).

Two adapters with intentionally different raw vendor schemas show that vendor
quirks stay inside adapters. Brands are fictional so mock listings cannot be
mistaken for real prices. Search is a naive token matcher; real normalization
and variant matching belong to Phase 6.
"""

from __future__ import annotations

import asyncio
from abc import abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from app.domain.comparisons.models import ProductQuery
from app.domain.enums import (
    Category,
    ChargeStatus,
    ProviderStatus,
    SourceKind,
    StockStatus,
    TaxTreatment,
)
from app.domain.money import Money
from app.domain.products.models import (
    Availability,
    Charge,
    DataProvenance,
    PriceBreakdown,
    ProductResult,
    ReturnPolicy,
    Warranty,
)
from app.domain.providers.models import Provider, ProviderCapability
from app.providers.base import (
    ProviderAdapter,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)

MOCK_TTL_SECONDS = 900


class MockFailureMode(StrEnum):
    NONE = "none"
    TIMEOUT = "timeout"  # hangs until cancelled by the caller's timeout
    RATE_LIMITED = "rate_limited"
    INVALID_RESPONSE = "invalid_response"  # returns a malformed raw record
    UNAVAILABLE = "unavailable"


Clock = Callable[[], datetime]


def _inr(value: str) -> Money:
    return Money(amount=Decimal(value), currency="INR")


class _MockEcommerceAdapter(ProviderAdapter):
    _default_id: str
    _default_name: str
    _supported_filters: frozenset[str] = frozenset()

    def __init__(
        self,
        *,
        provider_id: str | None = None,
        display_name: str | None = None,
        failure_mode: MockFailureMode = MockFailureMode.NONE,
        hang_seconds: float = 3600.0,
        clock: Clock | None = None,
    ) -> None:
        self._failure_mode = failure_mode
        self._hang_seconds = hang_seconds
        self._clock: Clock = clock or (lambda: datetime.now(UTC))
        self._provider = Provider(
            id=provider_id or self._default_id,
            display_name=display_name or self._default_name,
            capabilities=(
                ProviderCapability(
                    category=Category.ECOMMERCE,
                    markets=frozenset({"IN"}),
                    supported_filters=self._supported_filters,
                ),
            ),
            is_demo=True,
        )

    @property
    def provider(self) -> Provider:
        return self._provider

    @abstractmethod
    def _raw_catalog(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def _map_record(self, record: dict[str, Any]) -> ProductResult: ...

    async def search(self, query: ProductQuery) -> list[ProductResult]:
        self.validate_query(query)
        await self._maybe_fail()
        records = self._raw_catalog()
        if self._failure_mode is MockFailureMode.INVALID_RESPONSE:
            records = [{"corrupt": True}]
        try:
            results = [self._map_record(r) for r in records]
        except (KeyError, ValueError, InvalidOperation, ValidationError) as exc:
            # ValidationError subclasses ValueError. Never leak raw payloads.
            raise ProviderInvalidResponseError(
                f"{self.provider.display_name} returned a malformed response"
            ) from exc
        results = [r for r in results if _matches_text(r.title, query.text)]
        if query.max_price is not None and "max_price" in self._supported_filters:
            limit = query.max_price
            results = [
                r
                for r in results
                if r.price.advertised.currency != limit.currency
                or r.price.advertised.amount <= limit.amount
            ]
        return results

    async def _maybe_fail(self) -> None:
        mode = self._failure_mode
        name = self.provider.display_name
        if mode is MockFailureMode.TIMEOUT:
            await asyncio.sleep(self._hang_seconds)
        elif mode is MockFailureMode.RATE_LIMITED:
            raise ProviderRateLimitedError(f"{name} is rate limiting requests", 30)
        elif mode is MockFailureMode.UNAVAILABLE:
            raise ProviderUnavailableError(f"{name} is temporarily unavailable")

    def _provenance(self, listing_id: str) -> DataProvenance:
        return DataProvenance(
            provider_id=self.provider.id,
            source_kind=SourceKind.MOCK,
            source_url=f"https://{self.provider.id}.invalid/p/{listing_id}",
            retrieved_at=self._clock(),
            ttl_seconds=MOCK_TTL_SECONDS,
        )


def _matches_text(title: str, text: str) -> bool:
    """Naive deterministic matcher: every query token appears in the title."""
    haystack = title.lower()
    compact = haystack.replace(" ", "")
    return all(tok in haystack or tok in compact for tok in text.lower().split())


_STOCK = {"yes": StockStatus.IN_STOCK, "few": StockStatus.LIMITED, "no": StockStatus.OUT_OF_STOCK}


class MockAlphaAdapter(_MockEcommerceAdapter):
    """Raw schema A: `mrp_inr` and `ship_fee_inr` as strings; full policy data."""

    _default_id = "mock-alpha"
    _default_name = "Mock Store Alpha (demo)"
    _supported_filters = frozenset({"max_price"})

    def _raw_catalog(self) -> list[dict[str, Any]]:
        base = {"ship_fee_inr": "49.00", "return_days": 7, "warranty_months": 60}
        return [
            {
                **base,
                "sku": "A-100",
                "name": "Nimbus Swift 64GB USB 3.2 Pen Drive",
                "brand": "Nimbus",
                "mrp_inr": "649.00",
                "stock": "yes",
                "eta": (3, 5),
            },
            {
                **base,
                "sku": "A-101",
                "name": "Nimbus Swift 32GB USB 3.2 Pen Drive",
                "brand": "Nimbus",
                "mrp_inr": "449.00",
                "stock": "yes",
                "eta": (3, 5),
            },
            {
                **base,
                "sku": "A-102",
                "name": "Kestrel Edge 64GB USB 2.0 Pen Drive",
                "brand": "Kestrel",
                "mrp_inr": "399.00",
                "stock": "few",
                "eta": (4, 6),
            },
            {
                **base,
                "sku": "A-103",
                "name": "Vortex Pro 128GB USB 3.2 Pen Drive",
                "brand": "Vortex",
                "mrp_inr": "1199.00",
                "stock": "no",
                "eta": None,
            },
            {
                **base,
                "sku": "A-104",
                "name": "Kestrel Edge 64GB USB 3.2 Pen Drive",
                "brand": "Kestrel",
                "mrp_inr": "799.00",
                "stock": "yes",
                "eta": (3, 5),
            },
        ]

    def _map_record(self, record: dict[str, Any]) -> ProductResult:
        eta = record["eta"]
        return ProductResult(
            provider_id=self.provider.id,
            listing_id=record["sku"],
            title=record["name"],
            brand=record["brand"],
            attributes={},
            price=PriceBreakdown(
                advertised=_inr(record["mrp_inr"]),
                charges=(
                    Charge(
                        name="delivery",
                        status=ChargeStatus.KNOWN,
                        amount=_inr(record["ship_fee_inr"]),
                    ),
                ),
                charges_complete=True,
                tax_treatment=TaxTreatment.INCLUSIVE,
            ),
            availability=Availability(
                status=_STOCK[record["stock"]],
                delivery_days_min=eta[0] if eta else None,
                delivery_days_max=eta[1] if eta else None,
            ),
            return_policy=ReturnPolicy(returnable=True, window_days=record["return_days"]),
            warranty=Warranty(months=record["warranty_months"]),
            seller="Mock Alpha Retail",
            url=f"https://{self.provider.id}.invalid/p/{record['sku']}",
            provenance=self._provenance(record["sku"]),
        )


class MockBetaAdapter(_MockEcommerceAdapter):
    """Raw schema B: `price`, `shipping` ('free' | 'unknown' | amount), sparse policy data."""

    _default_id = "mock-beta"
    _default_name = "Mock Store Beta (demo)"

    def _raw_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "B-9001",
                "title": "Nimbus Swift 64GB USB 3.2 Pen Drive",
                "brand": "Nimbus",
                "price": "689",
                "shipping": "free",
                "in_stock": "yes",
                "warranty": 12,
            },
            {
                "id": "B-9002",
                "title": "Vortex Pro 64GB USB 3.2 Pen Drive",
                "brand": "Vortex",
                "price": "729",
                "shipping": "unknown",
                "in_stock": "yes",
                "warranty": None,
            },
            {
                "id": "B-9003",
                "title": "Kestrel Edge 64GB USB 3.2 Pen Drive",
                "brand": "Kestrel",
                "price": "749",
                "shipping": "60",
                "in_stock": "yes",
                "warranty": 24,
            },
        ]

    def _map_record(self, record: dict[str, Any]) -> ProductResult:
        shipping = record["shipping"]
        if shipping == "unknown":
            delivery = Charge(name="delivery", status=ChargeStatus.UNKNOWN)
        else:
            amount = Decimal("0") if shipping == "free" else Decimal(shipping)
            delivery = Charge(
                name="delivery",
                status=ChargeStatus.KNOWN,
                amount=Money(amount=amount, currency="INR"),
            )
        warranty = record["warranty"]
        return ProductResult(
            provider_id=self.provider.id,
            listing_id=record["id"],
            title=record["title"],
            brand=record["brand"],
            price=PriceBreakdown(
                advertised=_inr(record["price"]),
                charges=(delivery,),
                charges_complete=True,
            ),
            availability=Availability(status=_STOCK[record["in_stock"]]),
            # Beta publishes no return policy: left unknown, NOT "no returns".
            warranty=Warranty(months=warranty),
            url=f"https://{self.provider.id}.invalid/p/{record['id']}",
            provenance=self._provenance(record["id"]),
        )


class UnavailableProviderAdapter(ProviderAdapter):
    """Placeholder for a real provider that is blocked (see provider-feasibility.md).

    Registered so users can see it exists and why it cannot be used. It never
    returns data, synthetic or otherwise.
    """

    def __init__(self, provider_id: str, display_name: str, reason: str) -> None:
        self._provider = Provider(
            id=provider_id,
            display_name=display_name,
            capabilities=(ProviderCapability(category=Category.ECOMMERCE),),
            status=ProviderStatus.UNAVAILABLE,
            unavailable_reason=reason,
        )

    @property
    def provider(self) -> Provider:
        return self._provider

    async def search(self, query: ProductQuery) -> list[ProductResult]:
        raise ProviderUnavailableError(
            f"{self.provider.display_name} is unavailable: {self.provider.unavailable_reason}"
        )
