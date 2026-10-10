import pytest
from pydantic import ValidationError

from app.domain.comparisons.models import ProductQuery, SearchResponse
from app.domain.enums import Category, ProviderStatus, SearchState
from app.domain.products.models import ProductResult
from app.domain.providers.models import (
    Provider,
    ProviderCapability,
    ProviderSearchStatus,
    ProviderSelection,
)
from app.providers.base import ProviderAdapter
from app.providers.defaults import build_default_registry
from app.providers.mock.ecommerce import MockAlphaAdapter
from app.providers.registry import (
    DuplicateProviderError,
    ProviderRegistry,
    ProviderSelectionError,
)

EC = Category.ECOMMERCE


def test_provider_id_pattern() -> None:
    cap = (ProviderCapability(category=EC),)
    with pytest.raises(ValidationError):
        Provider(id="Bad Id!", display_name="x", capabilities=cap)


def test_unavailable_provider_requires_reason() -> None:
    cap = (ProviderCapability(category=EC),)
    with pytest.raises(ValidationError):
        Provider(id="abc", display_name="x", capabilities=cap, status=ProviderStatus.UNAVAILABLE)


def test_selection_rejects_duplicates_and_bad_ids() -> None:
    with pytest.raises(ValidationError):
        ProviderSelection(provider_ids=("mock-alpha", "mock-alpha"))
    with pytest.raises(ValidationError):
        ProviderSelection(provider_ids=("NOPE!",))
    with pytest.raises(ValidationError):
        ProviderSelection(provider_ids=())


def test_register_duplicate_rejected() -> None:
    reg = ProviderRegistry()
    reg.register(MockAlphaAdapter())
    with pytest.raises(DuplicateProviderError):
        reg.register(MockAlphaAdapter())


def test_resolve_preserves_user_order() -> None:
    reg = build_default_registry()
    adapters = reg.resolve(("mock-beta", "mock-alpha"), EC)
    assert [a.provider.id for a in adapters] == ["mock-beta", "mock-alpha"]


def test_resolve_reports_all_issues_at_once() -> None:
    reg = build_default_registry()
    with pytest.raises(ProviderSelectionError) as exc:
        reg.resolve(("nope", "flipkart", "mock-alpha"), EC)
    codes = {i.provider_id: i.code for i in exc.value.issues}
    assert codes == {"nope": "unknown", "flipkart": "unavailable"}
    assert "awaiting" in str(exc.value)  # reason is surfaced to the caller


def test_disabled_and_unsupported_category_rejected() -> None:
    class Disabled(ProviderAdapter):
        @property
        def provider(self) -> Provider:
            return Provider(
                id="off-store",
                display_name="Off",
                capabilities=(ProviderCapability(category=EC),),
                status=ProviderStatus.DISABLED,
            )

        async def search(self, query: ProductQuery) -> list[ProductResult]:
            return []

    reg = ProviderRegistry()
    reg.register(Disabled())
    with pytest.raises(ProviderSelectionError) as exc:
        reg.resolve(("off-store",), EC)
    assert exc.value.issues[0].code == "disabled"


async def test_new_provider_needs_no_orchestration_changes() -> None:
    """Phase 1 form of AC2: a brand-new adapter plugs in via register() only."""

    class Custom(ProviderAdapter):
        @property
        def provider(self) -> Provider:
            return Provider(
                id="custom-shop",
                display_name="Custom",
                capabilities=(ProviderCapability(category=EC),),
            )

        async def search(self, query: ProductQuery) -> list[ProductResult]:
            return []

    reg = build_default_registry()
    reg.register(Custom())
    adapters = reg.resolve(("custom-shop", "mock-alpha"), EC)
    assert len(adapters) == 2
    assert await adapters[0].search(ProductQuery(text="x")) == []


async def test_default_health_reports_status() -> None:
    reg = build_default_registry()
    healthy = await reg.resolve(("mock-alpha",), EC)[0].health()
    assert healthy.healthy is True


def test_search_response_partial_flags() -> None:
    ok = ProviderSearchStatus(provider_id="a", state=SearchState.SUCCESS, result_count=1)
    empty = ProviderSearchStatus(provider_id="b", state=SearchState.EMPTY)
    bad = ProviderSearchStatus(provider_id="c", state=SearchState.TIMEOUT)
    assert SearchResponse(provider_statuses=(ok, empty)).is_partial is False
    partial = SearchResponse(provider_statuses=(ok, bad))
    assert partial.is_partial is True and partial.all_failed is False
    assert SearchResponse(provider_statuses=(bad,)).all_failed is True
    assert SearchResponse().all_failed is False
