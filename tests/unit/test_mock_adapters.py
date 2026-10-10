import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.comparisons.models import ProductQuery
from app.domain.enums import SearchState, SourceKind, TotalKind
from app.domain.money import Money
from app.providers.base import (
    ProviderInvalidResponseError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
    UnsupportedQueryError,
)
from app.providers.mock.ecommerce import (
    MockAlphaAdapter,
    MockBetaAdapter,
    MockFailureMode,
    UnavailableProviderAdapter,
)

FIXED = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)
Q = ProductQuery(text="pen drive 64 gb")


def fixed_clock() -> datetime:
    return FIXED


async def test_results_are_deterministic() -> None:
    a = MockAlphaAdapter(clock=fixed_clock)
    first = await a.search(Q)
    second = await a.search(Q)
    assert first == second


async def test_all_results_are_tagged_mock_with_provenance() -> None:
    for adapter in (MockAlphaAdapter(clock=fixed_clock), MockBetaAdapter(clock=fixed_clock)):
        results = await adapter.search(Q)
        assert results
        for r in results:
            assert r.provenance.source_kind is SourceKind.MOCK
            assert r.provenance.retrieved_at == FIXED
            assert r.provenance.provider_id == adapter.provider.id
            assert r.url is not None and str(r.url).startswith("https://")
        assert adapter.provider.is_demo is True


async def test_providers_return_different_result_sets() -> None:
    alpha = {r.listing_id for r in await MockAlphaAdapter().search(Q)}
    beta = {r.listing_id for r in await MockBetaAdapter().search(Q)}
    assert alpha and beta and alpha.isdisjoint(beta)


async def test_capacity_text_excludes_other_capacities() -> None:
    titles = [r.title for r in await MockAlphaAdapter().search(Q)]
    assert not any("32GB" in t or "128GB" in t for t in titles)


async def test_variant_trap_is_still_returned_for_later_matching() -> None:
    # USB 2.0 vs 3.2 of the same 64GB drive must reach Phase 6 un-merged.
    titles = [r.title for r in await MockAlphaAdapter().search(Q)]
    assert any("USB 2.0" in t for t in titles) and any("USB 3.2" in t for t in titles)


async def test_unknown_values_stay_unknown() -> None:
    beta = {r.listing_id: r for r in await MockBetaAdapter().search(Q)}
    unknown_ship = beta["B-9002"]
    assert unknown_ship.price.total_kind is TotalKind.UNKNOWN
    assert unknown_ship.price.total is None
    assert unknown_ship.return_policy.returnable is None  # not "no returns"
    assert unknown_ship.warranty.months is None  # not 0
    free_ship = beta["B-9001"]
    assert free_ship.price.total == Money(amount=Decimal("689"), currency="INR")


async def test_alpha_applies_max_price_prefilter_beta_does_not() -> None:
    capped = ProductQuery(
        text="pen drive 64gb", max_price=Money(amount=Decimal("500"), currency="INR")
    )
    alpha_ids = {r.listing_id for r in await MockAlphaAdapter().search(capped)}
    beta_ids = {r.listing_id for r in await MockBetaAdapter().search(capped)}
    assert alpha_ids == {"A-102"}
    assert len(beta_ids) == 3  # beta cannot pre-filter; the search service must


async def test_unsupported_market_rejected() -> None:
    with pytest.raises(UnsupportedQueryError):
        await MockAlphaAdapter().search(ProductQuery(text="pen drive", market="US"))


@pytest.mark.parametrize(
    ("mode", "exc"),
    [
        (MockFailureMode.RATE_LIMITED, ProviderRateLimitedError),
        (MockFailureMode.UNAVAILABLE, ProviderUnavailableError),
        (MockFailureMode.INVALID_RESPONSE, ProviderInvalidResponseError),
    ],
)
async def test_failure_modes_raise_typed_errors(
    mode: MockFailureMode, exc: type[Exception]
) -> None:
    with pytest.raises(exc):
        await MockAlphaAdapter(failure_mode=mode).search(Q)


async def test_rate_limit_carries_retry_after_and_state() -> None:
    with pytest.raises(ProviderRateLimitedError) as e:
        await MockBetaAdapter(failure_mode=MockFailureMode.RATE_LIMITED).search(Q)
    assert e.value.retry_after_seconds == 30
    assert e.value.state is SearchState.RATE_LIMITED


async def test_invalid_response_does_not_leak_raw_payload() -> None:
    with pytest.raises(ProviderInvalidResponseError) as e:
        await MockAlphaAdapter(failure_mode=MockFailureMode.INVALID_RESPONSE).search(Q)
    assert "corrupt" not in e.value.message


async def test_timeout_mode_hangs_until_cancelled() -> None:
    adapter = MockAlphaAdapter(failure_mode=MockFailureMode.TIMEOUT)
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
            await adapter.search(Q)


async def test_unavailable_placeholder_never_returns_data() -> None:
    adapter = UnavailableProviderAdapter("flipkart", "Flipkart", "no credentials")
    with pytest.raises(ProviderUnavailableError) as e:
        await adapter.search(Q)
    assert "no credentials" in e.value.message
    health = await adapter.health()
    assert health.healthy is False


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_blank_query_text_is_rejected_not_match_all(blank: str) -> None:
    # Regression: whitespace-only text used to split to zero tokens and match every listing.
    with pytest.raises(ValidationError):
        ProductQuery(text=blank)


def test_query_text_is_stripped() -> None:
    assert ProductQuery(text="  pen drive  ").text == "pen drive"
