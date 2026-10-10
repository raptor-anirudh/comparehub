"""Flipkart Affiliate API adapter."""

from __future__ import annotations

import os
import httpx
from decimal import Decimal, InvalidOperation
from app.domain.comparisons.models import ProductQuery
from app.domain.enums import Category, ChargeStatus, ProviderStatus, SourceKind, StockStatus, TaxTreatment
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
    ProviderUnavailableError,
)

class FlipkartAdapter(ProviderAdapter):
    """Integration with the official Flipkart Affiliate API."""

    def __init__(self) -> None:
        # Credentials read from environment variables
        self._affiliate_id = os.environ.get("FLIPKART_AFFILIATE_ID")
        self._affiliate_token = os.environ.get("FLIPKART_AFFILIATE_TOKEN")

        self._provider = Provider(
            id="flipkart",
            display_name="Flipkart",
            capabilities=(
                ProviderCapability(
                    category=Category.ECOMMERCE,
                    markets=frozenset({"IN"}),
                ),
            ),
            status=ProviderStatus.ENABLED,
        )

    @property
    def provider(self) -> Provider:
        return self._provider

    async def search(self, query: ProductQuery) -> list[ProductResult]:
        # 1. Credential Check
        if not self._affiliate_id or not self._affiliate_token:
            raise ProviderUnavailableError(
                "Flipkart API credentials (FLIPKART_AFFILIATE_ID, FLIPKART_AFFILIATE_TOKEN) are missing"
            )

        # 2. Request setup
        # Based on docs: /affiliate/search/json
        url = "https://affiliate.flipkart.com/affiliate/search/json"
        params = {"q": query.text}
        headers = {
            "Fk-Affiliate-Id": self._affiliate_id,
            "Fk-Affiliate-Token": self._affiliate_token,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as exc:
                # Handle specific status codes if needed
                if exc.response.status_code == 401:
                    raise ProviderUnavailableError("Flipkart API token is invalid or expired")
                raise ProviderInvalidResponseError(f"Flipkart API error: {exc.response.status_code}")
            except Exception as exc:
                raise ProviderInvalidResponseError(f"Unexpected error calling Flipkart: {str(exc)}")

        # 3. Map results
        # Note: The exact JSON schema is pending live capture.
        # We use a safe mapper that returns empty if the structure is unexpected.
        return self._map_response(data)

    def _map_response(self, data: dict) -> list[ProductResult]:
        """Maps the Flipkart JSON response to our domain model."""
        results: list[ProductResult] = []

        # This is a skeletal mapper. It will be refined once real JSON fixtures are captured.
        products = data.get("products", [])
        for p in products:
            try:
                # Placeholder mapping based on expected Affiliate API fields
                listing_id = str(p.get("id", ""))
                if not listing_id: continue

                results.append(ProductResult(
                    provider_id=self.provider.id,
                    listing_id=listing_id,
                    title=p.get("title", "Unknown Product"),
                    brand=p.get("brand", "Unknown Brand"),
                    attributes={},
                    price=PriceBreakdown(
                        advertised=Money(amount=Decimal(str(p.get("price", 0))), currency="INR"),
                        charges=(),
                        charges_complete=False,
                        tax_treatment=TaxTreatment.INCLUSIVE,
                    ),
                    availability=Availability(status=StockStatus.IN_STOCK),
                    return_policy=ReturnPolicy(returnable=True, window_days=0),
                    warranty=Warranty(months=0),
                    seller=p.get("seller", "Flipkart"),
                    url=p.get("url", ""),
                    provenance=self._provenance(listing_id),
                ))
            except (ValueError, InvalidOperation, TypeError):
                continue # Skip malformed records

        return results

    def _provenance(self, listing_id: str) -> DataProvenance:
        from app.domain.enums import SourceKind
        from datetime import datetime, UTC
        return DataProvenance(
            provider_id=self.provider.id,
            source_kind=SourceKind.LIVE,
            source_url=f"https://flipkart.com/p/{listing_id}",
            retrieved_at=datetime.now(UTC),
            ttl_seconds=3600,
        )
