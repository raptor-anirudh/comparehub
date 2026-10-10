"""Default registry used for local development and demos."""

from __future__ import annotations

from app.providers.mock.ecommerce import (
    MockAlphaAdapter,
    MockBetaAdapter,
    MockFailureMode,
    UnavailableProviderAdapter,
)
from app.providers.registry import ProviderRegistry


def build_default_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(MockAlphaAdapter())
    registry.register(MockBetaAdapter())
    # Always-failing demo provider so partial-failure handling is visible in the UI.
    registry.register(
        MockAlphaAdapter(
            provider_id="mock-flaky",
            display_name="Mock Flaky Store (demo, always times out)",
            failure_mode=MockFailureMode.TIMEOUT,
        )
    )
    # Real providers that are blocked; see docs/provider-feasibility.md.
    registry.register(
        UnavailableProviderAdapter(
            "flipkart", "Flipkart", "awaiting affiliate registration and API token"
        )
    )
    registry.register(
        UnavailableProviderAdapter(
            "amazon-in", "Amazon India", "awaiting Creators API eligibility confirmation"
        )
    )
    return registry
