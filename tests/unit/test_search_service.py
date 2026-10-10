"""Search orchestration tests. Deterministic: no network, no real sleeping."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.comparisons.models import ProductQuery, SearchQuery
from app.domain.enums import Category, ChargeStatus, SearchState, SourceKind
from app.domain.money import Money
from app.domain.products.models import Charge, DataProvenance, PriceBreakdown, ProductResult
from app.domain.providers.models import Provider, ProviderCapability, ProviderSelection
from app.providers.base import (
    ProviderAdapter,
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)
from app.providers.mock.ecommerce import MockAlphaAdapter, MockBetaAdapter, MockFailureMode
from app.providers.registry import ProviderRegistry, ProviderSelectionError
from app.services.search import SearchConfig, SearchService

NOW = datetime(2026, 10, 10, tzinfo=UTC)


def inr(value: str) -> Money:
    return Money(amount=Decimal(value), currency="INR")


def make_result(
    pid: str,
    listing_id: str,
    advertised: str = "500",
    *,
    attributes: dict[str, str] | None = None,
    currency: str = "INR",
) -> ProductResult:
    return ProductResult(
        provider_id=pid,
        listing_id=listing_id,
        title=f"Test item {listing_id}",
        attributes=attributes or {},
        price=PriceBreakdown(
            advertised=Money(amount=Decimal(advertised), currency=currency),
            charges=(Charge(name="delivery", status=ChargeStatus.UNKNOWN),),
        ),
        provenance=DataProvenance(provider_id=pid, source_kind=SourceKind.MOCK, retrieved_at=NOW),
    )


class FakeAdapter(ProviderAdapter):
    """Scriptable adapter. `script` items are returned/raised in order, last one repeats."""

    def __init__(
        self,
        pid: str,
        script: list[object] | None = None,
        *,
        markets: frozenset[str] = frozenset({"IN"}),
        delay: float = 0.0,
        validate_raises: Exception | None = None,
    ) -> None:
        self._provider = Provider(
            id=pid,
            display_name=pid,
            capabilities=(ProviderCapability(category=Category.ECOMMERCE, markets=markets),),
        )
        self._script = script if script is not None else [[make_result(pid, f"{pid}-1")]]
        self._delay = delay
        self._validate_raises = validate_raises
        self.calls = 0
        self.cancelled = False

    @property
    def provider(self) -> Provider:
        return self._provider

    def validate_query(self, query: ProductQuery) -> None:
        if self._validate_raises is not None:
            raise self._validate_raises
        super().validate_query(query)

    async def search(self, query: ProductQuery) -> list[ProductResult]:
        item = self._script[min(self.calls, len(self._script) - 1)]
        self.calls += 1
        try:
            if self._delay:
                await asyncio.sleep(self._delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        if isinstance(item, Exception):
            raise item
        assert isinstance(item, list)
        return item


class SleepRecorder:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def build(
    *adapters: ProviderAdapter,
    config: SearchConfig | None = None,
    sleeper: SleepRecorder | None = None,
) -> SearchService:
    registry = ProviderRegistry()
    for adapter in adapters:
        registry.register(adapter)
    return SearchService(
        registry,
        config or SearchConfig(per_provider_timeout_seconds=0.05, retry_backoff_seconds=0.01),
        sleep=sleeper or SleepRecorder(),
    )


def query(
    *ids: str, text: str = "pen drive", max_price: str | None = None, **product_kwargs: object
) -> SearchQuery:
    return SearchQuery(
        category=Category.ECOMMERCE,
        product=ProductQuery(
            text=text,
            max_price=inr(max_price) if max_price else None,
            **product_kwargs,  # type: ignore[arg-type]
        ),
        selection=ProviderSelection(provider_ids=ids),
    )


def states(response: object) -> dict[str, SearchState]:
    return {s.provider_id: s.state for s in response.provider_statuses}  # type: ignore[attr-defined]


# --- acceptance criterion ---


async def test_three_providers_one_times_out_returns_valid_results_from_the_rest() -> None:
    service = build(
        MockAlphaAdapter(),
        MockBetaAdapter(),
        MockAlphaAdapter(
            provider_id="mock-flaky", failure_mode=MockFailureMode.TIMEOUT, hang_seconds=5
        ),
        config=SearchConfig(per_provider_timeout_seconds=0.05, max_retries=0),
    )
    response = await service.search(query("mock-alpha", "mock-beta", "mock-flaky"))

    assert states(response) == {
        "mock-alpha": SearchState.SUCCESS,
        "mock-beta": SearchState.SUCCESS,
        "mock-flaky": SearchState.TIMEOUT,
    }
    assert {r.provider_id for r in response.results} == {"mock-alpha", "mock-beta"}
    assert len(response.results) == 8
    assert response.is_partial is True
    assert response.all_failed is False
    timeout_status = response.provider_statuses[2]
    assert timeout_status.message is not None and "no response" in timeout_status.message


# --- failure handling ---


async def test_all_providers_failing_is_reported_not_raised() -> None:
    service = build(
        FakeAdapter("down-a", [ProviderUnavailableError("a is down")]),
        FakeAdapter("down-b", [ProviderInvalidResponseError("b sent junk")]),
        config=SearchConfig(per_provider_timeout_seconds=0.05, max_retries=0),
    )
    response = await service.search(query("down-a", "down-b"))
    assert response.results == ()
    assert response.all_failed is True
    assert states(response) == {
        "down-a": SearchState.UNAVAILABLE,
        "down-b": SearchState.INVALID_RESPONSE,
    }


async def test_unexpected_exception_is_isolated_and_not_leaked() -> None:
    service = build(
        FakeAdapter("good"),
        FakeAdapter("buggy", [RuntimeError("secret db password=hunter2")]),
    )
    response = await service.search(query("good", "buggy"))
    assert states(response) == {"good": SearchState.SUCCESS, "buggy": SearchState.ERROR}
    assert len(response.results) == 1
    message = response.provider_statuses[1].message or ""
    assert "hunter2" not in message and "RuntimeError" not in message


async def test_validator_crash_does_not_cancel_other_providers() -> None:
    service = build(
        FakeAdapter("good"),
        FakeAdapter("bad-validator", validate_raises=RuntimeError("boom")),
    )
    response = await service.search(query("good", "bad-validator"))
    assert states(response) == {"good": SearchState.SUCCESS, "bad-validator": SearchState.ERROR}
    assert len(response.results) == 1


async def test_results_attributed_to_another_provider_are_rejected() -> None:
    liar = FakeAdapter("liar", [[make_result("someone-else", "X-1")]])
    response = await build(liar).search(query("liar"))
    assert states(response) == {"liar": SearchState.INVALID_RESPONSE}
    assert response.results == ()


async def test_unsupported_market_is_reported_without_calling_the_provider() -> None:
    us_only = FakeAdapter("us-only", markets=frozenset({"US"}))
    response = await build(us_only, FakeAdapter("in-ok")).search(query("us-only", "in-ok"))
    assert states(response) == {"us-only": SearchState.UNSUPPORTED, "in-ok": SearchState.SUCCESS}
    assert us_only.calls == 0


# --- retries ---


async def test_transient_failure_is_retried_then_succeeds() -> None:
    sleeper = SleepRecorder()
    flaky = FakeAdapter("flaky", [ProviderUnavailableError("blip"), [make_result("flaky", "F-1")]])
    response = await build(flaky, sleeper=sleeper).search(query("flaky"))
    assert states(response) == {"flaky": SearchState.SUCCESS}
    assert flaky.calls == 2
    assert sleeper.delays == [0.01]


async def test_retries_are_bounded_with_exponential_backoff() -> None:
    sleeper = SleepRecorder()
    down = FakeAdapter("down", [ProviderUnavailableError("still down")])
    service = build(
        down,
        config=SearchConfig(
            per_provider_timeout_seconds=0.05, max_retries=3, retry_backoff_seconds=0.1
        ),
        sleeper=sleeper,
    )
    response = await service.search(query("down"))
    assert states(response) == {"down": SearchState.UNAVAILABLE}
    assert down.calls == 4  # 1 + 3 retries, never more
    assert sleeper.delays == [0.1, 0.2, 0.4]


async def test_timeouts_are_retried() -> None:
    slow = FakeAdapter("slow", delay=5)
    response = await build(slow, config=SearchConfig(per_provider_timeout_seconds=0.02)).search(
        query("slow")
    )
    assert states(response) == {"slow": SearchState.TIMEOUT}
    assert slow.calls == 2  # default max_retries=1


@pytest.mark.parametrize(
    "error",
    [ProviderRateLimitedError("slow down", 30), ProviderInvalidResponseError("junk")],
)
async def test_rate_limits_and_invalid_responses_are_never_retried(error: Exception) -> None:
    adapter = FakeAdapter("prov", [error])
    response = await build(adapter).search(query("prov"))
    assert adapter.calls == 1
    assert response.provider_statuses[0].state in {
        SearchState.RATE_LIMITED,
        SearchState.INVALID_RESPONSE,
    }


async def test_rate_limit_retry_after_is_surfaced() -> None:
    adapter = FakeAdapter("prov", [ProviderRateLimitedError("slow down", 30)])
    status = (await build(adapter).search(query("prov"))).provider_statuses[0]
    assert status.state is SearchState.RATE_LIMITED
    assert status.retry_after_seconds == 30


# --- collection behaviour ---


async def test_empty_result_is_empty_state_not_error() -> None:
    response = await build(FakeAdapter("prov", [[]])).search(query("prov"))
    assert states(response) == {"prov": SearchState.EMPTY}
    assert response.is_partial is False


async def test_duplicate_listings_from_one_provider_are_removed_and_reported() -> None:
    dup = [make_result("prov", "1"), make_result("prov", "1"), make_result("prov", "2")]
    response = await build(FakeAdapter("prov", [dup])).search(query("prov"))
    assert [r.listing_id for r in response.results] == ["1", "2"]
    status = response.provider_statuses[0]
    assert status.result_count == 2
    assert status.message is not None and "1 duplicate" in status.message


async def test_per_provider_result_cap_is_applied_and_reported() -> None:
    many = [make_result("prov", str(i)) for i in range(10)]
    service = build(
        FakeAdapter("prov", [many]),
        config=SearchConfig(per_provider_timeout_seconds=0.05, max_results_per_provider=3),
    )
    response = await service.search(query("prov"))
    assert len(response.results) == 3
    assert "truncated" in (response.provider_statuses[0].message or "")


async def test_statuses_and_results_follow_selection_order_deterministically() -> None:
    fast, slow = FakeAdapter("fast"), FakeAdapter("slow", delay=0.02)
    service = build(slow, fast, config=SearchConfig(per_provider_timeout_seconds=1))
    first = await service.search(query("slow", "fast"))
    second = await service.search(query("slow", "fast"))
    assert [s.provider_id for s in first.provider_statuses] == ["slow", "fast"]
    assert [r.listing_id for r in first.results] == [r.listing_id for r in second.results]


async def test_latency_is_recorded() -> None:
    status = (await build(FakeAdapter("prov")).search(query("prov"))).provider_statuses[0]
    assert status.latency_ms is not None and status.latency_ms >= 0


# --- selection ---


async def test_unknown_provider_raises_selection_error_listing_all_issues() -> None:
    service = build(FakeAdapter("real"))
    with pytest.raises(ProviderSelectionError) as info:
        await service.search(query("real", "ghost", "phantom"))
    assert {i.provider_id for i in info.value.issues} == {"ghost", "phantom"}


# --- concurrency, cancellation ---


async def test_providers_run_concurrently_but_within_the_concurrency_limit() -> None:
    active = peak = 0

    class Tracking(FakeAdapter):
        async def search(self, query: ProductQuery) -> list[ProductResult]:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0.02)
            finally:
                active -= 1
            return [make_result(self.provider.id, "1")]

    adapters = [Tracking(f"p{i}") for i in range(6)]
    service = build(
        *adapters, config=SearchConfig(per_provider_timeout_seconds=1, max_concurrency=2)
    )
    response = await service.search(query(*(a.provider.id for a in adapters)))
    assert len(response.results) == 6
    assert peak == 2  # concurrent (>1) yet bounded (<=2)


async def test_cancelling_a_search_cancels_in_flight_provider_calls() -> None:
    slow = FakeAdapter("slow", delay=30)
    service = build(slow, config=SearchConfig(per_provider_timeout_seconds=60))
    task = asyncio.create_task(service.search(query("slow")))
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert slow.cancelled is True


# --- hard filters through the service ---


async def test_budget_excludes_provably_over_budget_listings_but_keeps_unknown_totals() -> None:
    service = build(MockAlphaAdapter(), MockBetaAdapter())
    response = await service.search(query("mock-alpha", "mock-beta", max_price="800"))
    ids = {r.listing_id for r in response.results}
    # A-104: 799 advertised but 848 total; B-9003: 749 advertised but 809 total; A-103: 1199.
    assert "A-104" not in ids and "B-9003" not in ids and "A-103" not in ids
    # B-9002: advertised 729 with an UNKNOWN total cannot be proven over budget, so it stays.
    assert "B-9002" in ids
    assert ids == {"A-100", "A-101", "A-102", "B-9001", "B-9002"}
    # mock-alpha pre-filters A-103 server-side, so the service itself receives 7 listings and
    # excludes exactly two (A-104, B-9003). The service re-checks every hard filter itself
    # rather than trusting adapters' server-side filtering.
    assert response.filtered_out_count == 2


async def test_required_attribute_that_cannot_be_verified_excludes_the_listing() -> None:
    verified = make_result("prov", "ok", attributes={"Capacity_GB": " 64 "})
    wrong = make_result("prov", "wrong", attributes={"capacity_gb": "32"})
    missing = make_result("prov", "missing")
    service = build(FakeAdapter("prov", [[verified, wrong, missing]]))
    response = await service.search(query("prov", required_attributes={"capacity_gb": "64"}))
    assert [r.listing_id for r in response.results] == ["ok"]
    assert response.filtered_out_count == 2


async def test_different_currency_than_budget_is_excluded_not_guessed() -> None:
    usd = make_result("prov", "usd", "5", currency="USD")
    inr_ok = make_result("prov", "inr", "500")
    response = await build(FakeAdapter("prov", [[usd, inr_ok]])).search(
        query("prov", max_price="800")
    )
    assert [r.listing_id for r in response.results] == ["inr"]
    assert response.filtered_out_count == 1


# --- privacy / config ---


async def test_logs_never_contain_the_query_text(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    await build(FakeAdapter("prov")).search(query("prov", text="my secret medical query"))
    assert "secret medical" not in caplog.text
    assert "provider search finished" in caplog.text


@pytest.mark.parametrize(
    "kwargs",
    [
        {"per_provider_timeout_seconds": 0},
        {"max_concurrency": 0},
        {"max_retries": -1},
        {"max_retries": 4},
        {"retry_backoff_seconds": -1},
        {"max_results_per_provider": 0},
    ],
)
def test_invalid_search_config_is_rejected(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        SearchConfig(**kwargs)  # type: ignore[arg-type]
