"""Search orchestration: resolve providers, fan out concurrently, collect, filter.

Knows nothing about any specific provider. Failure isolation is the core contract:
every selected provider gets exactly one `ProviderSearchStatus`, and one provider's
failure never discards another's results.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.domain.comparisons.models import ProductQuery, SearchQuery, SearchResponse
from app.domain.enums import SearchState
from app.domain.products.models import ProductResult
from app.domain.providers.models import ProviderSearchStatus, ProviderSelection
from app.providers.base import (
    ProviderAdapter,
    ProviderError,
    ProviderInvalidResponseError,
    UnsupportedQueryError,
)
from app.providers.registry import ProviderRegistry
from app.services.filters import apply_hard_filters

logger = logging.getLogger(__name__)

Sleep = Callable[[float], Awaitable[None]]

# Only these states are worth retrying: the search call is a read-only, idempotent lookup,
# and the failure may be transient. Rate limiting is deliberately NOT retried in-call:
# hammering a provider that asked us to back off is exactly what we must not do.
_RETRYABLE = frozenset({SearchState.TIMEOUT, SearchState.UNAVAILABLE})


@dataclass(frozen=True)
class SearchConfig:
    per_provider_timeout_seconds: float = 40.0
    max_concurrency: int = 5
    max_retries: int = 1  # extra attempts after the first
    retry_backoff_seconds: float = 0.25
    max_results_per_provider: int = 50

    def __post_init__(self) -> None:
        if self.per_provider_timeout_seconds <= 0:
            raise ValueError("per_provider_timeout_seconds must be positive")
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        if not 0 <= self.max_retries <= 3:
            raise ValueError("max_retries must be within [0, 3]")
        if self.retry_backoff_seconds < 0 or self.max_results_per_provider < 1:
            raise ValueError("invalid backoff or result cap")


@dataclass(frozen=True)
class _Outcome:
    status: ProviderSearchStatus
    results: tuple[ProductResult, ...] = ()


class SearchService:
    def __init__(
        self,
        registry: ProviderRegistry,
        config: SearchConfig | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._registry = registry
        self._config = config or SearchConfig()
        self._sleep = sleep

    async def search(
        self,
        query: SearchQuery,
        user_id: str | None = None,
        user_service: 'UserService' | None = None
    ) -> SearchResponse:
        """Run one search.

        If query.selection is omitted, providers are resolved via user_service
        using the provided user_id. If both are missing, all enabled providers are used.

        Raises ProviderSelectionError (a ValueError) if the selection is invalid; the
        API layer maps that to a 422. Provider-level failures never raise.
        Cancelling the caller cancels all in-flight provider calls.
        """
        # Resolve effective provider selection
        selection = query.selection
        if selection is None or not selection.provider_ids:
            if user_service:
                # Resolve via preferences if no explicit selection was provided
                resolved = await user_service.get_effective_providers(
                    user_id=user_id,
                    explicit_selection=None
                )
                if resolved:
                    selection = resolved
                else:
                    # Use all enabled providers: pass empty tuple to registry
                    selection = ProviderSelection(provider_ids=())
            else:
                # Default to empty selection
                selection = ProviderSelection(provider_ids=())

        try:
            # If provider_ids is empty, resolve() should be updated to return all enabled
            adapters = self._registry.resolve(selection.provider_ids, query.category)
        except Exception as exc:
            # Re-raise as ValueError so the API layer returns 422 instead of 500
            raise ValueError(str(exc)) from exc

        semaphore = asyncio.Semaphore(self._config.max_concurrency)
        async with asyncio.TaskGroup() as group:
            tasks = [
                group.create_task(self._search_one(a, query.product, semaphore)) for a in adapters
            ]
        outcomes = [t.result() for t in tasks]  # selection order, hence deterministic


        collected = [r for o in outcomes for r in o.results]
        eligible, excluded = apply_hard_filters(collected, query.product)
        return SearchResponse(
            results=tuple(eligible),
            provider_statuses=tuple(o.status for o in outcomes),
            filtered_out_count=excluded,
        )

    async def _search_one(
        self, adapter: ProviderAdapter, product: ProductQuery, semaphore: asyncio.Semaphore
    ) -> _Outcome:
        """Never raises (except cancellation): every failure becomes a status."""
        pid = adapter.provider.id
        try:
            adapter.validate_query(product)
        except UnsupportedQueryError as exc:
            return _Outcome(
                ProviderSearchStatus(provider_id=pid, state=exc.state, message=exc.message)
            )
        except Exception:
            # A buggy validator must not take down the other providers' searches.
            logger.exception("adapter validation failed", extra={"provider_id": pid})
            return _Outcome(
                ProviderSearchStatus(
                    provider_id=pid,
                    state=SearchState.ERROR,
                    message="unexpected error while validating the query for this provider",
                )
            )

        async with semaphore:
            started = time.monotonic()
            attempt = 0
            while True:
                outcome = await self._attempt(adapter, product)
                state = outcome.status.state
                if state not in _RETRYABLE or attempt >= self._config.max_retries:
                    break
                attempt += 1
                await self._sleep(self._config.retry_backoff_seconds * 2 ** (attempt - 1))
            latency_ms = int((time.monotonic() - started) * 1000)

        status = outcome.status.model_copy(update={"latency_ms": latency_ms})
        # Deliberately no query text in logs (privacy); ids, state and timing only.
        logger.info(
            "provider search finished",
            extra={
                "provider_id": pid,
                "state": status.state.value,
                "latency_ms": latency_ms,
                "attempts": attempt + 1,
                "result_count": status.result_count,
            },
        )
        return _Outcome(status, outcome.results)

    async def _attempt(self, adapter: ProviderAdapter, product: ProductQuery) -> _Outcome:
        pid = adapter.provider.id
        try:
            async with asyncio.timeout(self._config.per_provider_timeout_seconds):
                results = await adapter.search(product)
            return self._accept(pid, results)
        except TimeoutError:
            return _Outcome(
                ProviderSearchStatus(
                    provider_id=pid,
                    state=SearchState.TIMEOUT,
                    message=f"no response within {self._config.per_provider_timeout_seconds:g}s",
                )
            )
        except ProviderError as exc:
            retry_after = getattr(exc, "retry_after_seconds", None)
            return _Outcome(
                ProviderSearchStatus(
                    provider_id=pid,
                    state=exc.state,
                    message=exc.message,
                    retry_after_seconds=retry_after,
                )
            )
        except Exception:
            # A bug or unexpected upstream failure: record it, but show users no internals.
            logger.exception("unexpected adapter failure", extra={"provider_id": pid})
            return _Outcome(
                ProviderSearchStatus(
                    provider_id=pid,
                    state=SearchState.ERROR,
                    message="unexpected error while searching this provider",
                )
            )

    def _accept(self, pid: str, results: list[ProductResult]) -> _Outcome:
        """Defend against adapters returning results attributed to another provider."""
        if any(r.provider_id != pid for r in results):
            raise ProviderInvalidResponseError("adapter returned results for a different provider")
        note: str | None = None
        cap = self._config.max_results_per_provider
        if len(results) > cap:
            note = f"results truncated to {cap}"
            results = results[:cap]
        seen: set[str] = set()
        unique: list[ProductResult] = []
        for result in results:
            if result.listing_id not in seen:
                seen.add(result.listing_id)
                unique.append(result)
        dupes = len(results) - len(unique)
        if dupes:
            note = (note + "; " if note else "") + f"{dupes} duplicate listing(s) removed"
        state = SearchState.SUCCESS if unique else SearchState.EMPTY
        return _Outcome(
            ProviderSearchStatus(
                provider_id=pid, state=state, result_count=len(unique), message=note
            ),
            tuple(unique),
        )
