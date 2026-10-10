"""Provider adapter interface and the errors adapters may raise.

Vendor-specific schemas and quirks live ONLY inside adapter implementations.
The orchestrator maps these exceptions to `SearchState` values.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.comparisons.models import ProductQuery
from app.domain.enums import ProviderStatus, SearchState
from app.domain.products.models import ProductResult
from app.domain.providers.models import Provider, ProviderHealth


class ProviderError(Exception):
    """Base class for adapter failures. `message` must be safe to show to users."""

    state: SearchState = SearchState.ERROR

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ProviderUnavailableError(ProviderError):
    state = SearchState.UNAVAILABLE


class ProviderRateLimitedError(ProviderError):
    state = SearchState.RATE_LIMITED

    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ProviderInvalidResponseError(ProviderError):
    state = SearchState.INVALID_RESPONSE


class UnsupportedQueryError(ProviderError):
    """The provider cannot serve this query (e.g. unsupported market)."""

    state = SearchState.UNSUPPORTED


class ProviderAdapter(ABC):
    """Contract every provider integration implements."""

    @property
    @abstractmethod
    def provider(self) -> Provider:
        """Static identity, categories and capabilities."""

    @abstractmethod
    async def search(self, query: ProductQuery) -> list[ProductResult]:
        """Return normalized results, or raise a ProviderError subclass.

        Must be safe to cancel (the orchestrator enforces timeouts) and must not
        retry non-idempotent operations internally.
        """

    def validate_query(self, query: ProductQuery) -> None:
        """Raise UnsupportedQueryError if this provider cannot serve `query`."""
        markets = {m for cap in self.provider.capabilities for m in cap.markets}
        if query.market not in markets:
            raise UnsupportedQueryError(
                f"{self.provider.display_name} does not support market {query.market}"
            )

    async def health(self) -> ProviderHealth:
        """Cheap self-report. Real adapters may override with a probe."""
        status = self.provider.status
        return ProviderHealth(
            provider_id=self.provider.id,
            healthy=status is ProviderStatus.ENABLED,
            detail=None if status is ProviderStatus.ENABLED else status.value,
        )
