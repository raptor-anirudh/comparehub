"""Flipkart scraper adapter using Playwright."""

from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation
from playwright.async_api import async_playwright, Page
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
    """Integration with Flipkart via Playwright scraping."""

    def __init__(self) -> None:
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
        """Scrape search results from Flipkart."""
        url = f"https://www.flipkart.com/search?q={query.text}"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                # 1. Navigate with a generous timeout
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # 2. Immediate capture of HTML for debugging
                content = await page.content()
                with open("flipkart_debug.html", "w", encoding="utf-8") as f:
                    f.write(content)

                # 3. Basic check for blocking/captcha
                if "captcha" in content.lower():
                    raise ProviderUnavailableError("Flipkart blocked the request with a CAPTCHA")

                # 4. Wait for potential results to render
                try:
                    await page.wait_for_selector('div[class*="_cgRdT"], div[class*="_1AtV5S"], div[class*="_4sS_S_"], a[class*="_1AtV5S"]', timeout=10000)
                except Exception:
                    pass

                # 5. Extract data using a broad heuristic
                products_data = await page.evaluate("""
                    () => {
                        const results = [];
                        const candidates = document.querySelectorAll('div, a');

                        candidates.forEach(el => {
                            if (el.children.length > 2) {
                                const text = el.innerText || "";
                                if (text.includes('₹') && el.querySelector('a')) {
                                    if (el.innerText.length < 1000) {
                                        const link = el.querySelector('a');
                                        const title = el.querySelector('div[class*="title"], a, span') ?
                                                    (el.querySelector('div[class*="title"], a, span').innerText) : "Unknown";

                                        let price = "";
                                        const children = el.innerText.split('\\n');
                                        for (const line of children) {
                                            if (line.includes('₹')) {
                                                price = line.replace(/[^0-9.]/g, '');
                                                break;
                                            }
                                        }

                                        if (title && price) {
                                            results.push({
                                                title: title.trim(),
                                                price: price,
                                                url: link ? link.href : ''
                                            });
                                        }
                                    }
                                }
                            }
                        });

                        const unique = [];
                        const seen = new Set();
                        results.forEach(r => {
                            if (!seen.has(r.url)) {
                                unique.push(r);
                                seen.add(r.url);
                            }
                        });
                        return unique;
                    }
                """)

                await browser.close()
                return self._map_results(products_data)

            except Exception as exc:
                await browser.close()
                if isinstance(exc, ProviderUnavailableError):
                    raise exc
                raise ProviderInvalidResponseError(f"Flipkart scraping failed: {str(exc)}")
                # Note: Flipkart selectors change frequently. These are best-effort.
                # Using a broad selector for product cards.
                products_data = await page.evaluate("""
                    () => {
                        const results = [];
                        // Try multiple common selectors for product cards
                        const cards = document.querySelectorAll('div[class*="_cgRdT"], div[class*="_1AtV5S"]');

                        cards.forEach(card => {
                            const titleEl = card.querySelector('div[class*="_4rR0S"], a[class*="_4rR0S"], div[class*="_KzT0S"]');
                            const priceEl = card.querySelector('div[class*="_30jeq3"], span[class*="_30jeq3"]');
                            const linkEl = card.querySelector('a');

                            if (titleEl && priceEl) {
                                results.push({
                                    title: titleEl.innerText,
                                    price: priceEl.innerText.replace(/[^0-9.]/g, ''),
                                    url: linkEl ? linkEl.href : ''
                                });
                            }
                        });
                        return results;
                    }
                """)

                await browser.close()
                return self._map_results(products_data)

            except Exception as exc:
                await browser.close()
                if isinstance(exc, ProviderUnavailableError):
                    raise exc
                raise ProviderInvalidResponseError(f"Flipkart scraping failed: {str(exc)}")

    def _map_results(self, data: list[dict]) -> list[ProductResult]:
        results: list[ProductResult] = []
        for i, item in enumerate(data):
            try:
                listing_id = f"fk-scraped-{i}"
                price_val = item.get("price", "0")

                results.append(ProductResult(
                    provider_id=self.provider.id,
                    listing_id=listing_id,
                    title=item.get("title", "Unknown Product"),
                    brand="Unknown", # Brand often requires deeper parsing
                    attributes={},
                    price=PriceBreakdown(
                        advertised=Money(amount=Decimal(price_val), currency="INR"),
                        charges=(),
                        charges_complete=False,
                        tax_treatment=TaxTreatment.INCLUSIVE,
                    ),
                    availability=Availability(status=StockStatus.IN_STOCK),
                    return_policy=ReturnPolicy(returnable=True, window_days=0),
                    warranty=Warranty(months=0),
                    seller="Flipkart",
                    url=item.get("url", ""),
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
            source_kind=SourceKind.MOCK, # Mark as mock/scraped until we have a formal source
            source_url=f"https://flipkart.com/p/{listing_id}",
            retrieved_at=datetime.now(UTC),
            ttl_seconds=3600,
        )
