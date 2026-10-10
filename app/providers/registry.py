"""Registry resolving user-selected provider ids to enabled adapters."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import Category, ProviderStatus
from app.domain.providers.models import Provider
from app.providers.base import ProviderAdapter


class DuplicateProviderError(ValueError):
    """A provider id was registered twice."""


@dataclass(frozen=True)
class SelectionIssue:
    provider_id: str
    code: str  # unknown | disabled | unavailable | unsupported_category
    message: str


class ProviderSelectionError(ValueError):
    """One or more selected providers cannot be used. Lists ALL issues."""

    def __init__(self, issues: list[SelectionIssue]) -> None:
        self.issues = issues
        super().__init__("; ".join(f"{i.provider_id}: {i.message}" for i in issues))


class ProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ProviderAdapter] = {}

    def register(self, adapter: ProviderAdapter) -> None:
        pid = adapter.provider.id
        if pid in self._adapters:
            raise DuplicateProviderError(f"provider already registered: {pid}")
        self._adapters[pid] = adapter

    def list_providers(self) -> list[Provider]:
        return sorted((a.provider for a in self._adapters.values()), key=lambda p: p.id)

    def resolve(self, provider_ids: tuple[str, ...], category: Category) -> list[ProviderAdapter]:
        """Return adapters for the selection, preserving the user's order.

        If provider_ids is empty, returns all enabled providers that support the category.

        Raises ProviderSelectionError listing every unusable provider at once.
        """
        if not provider_ids:
            return [
                adapter for adapter in self._adapters.values()
                if adapter.provider.status == ProviderStatus.ENABLED
                and adapter.provider.capability_for(category) is not None
            ]

        adapters: list[ProviderAdapter] = []
        issues: list[SelectionIssue] = []
        for pid in provider_ids:
            adapter = self._adapters.get(pid)
            if adapter is None:
                issues.append(SelectionIssue(pid, "unknown", "provider is not registered"))
                continue
            provider = adapter.provider
            if provider.status is ProviderStatus.DISABLED:
                issues.append(SelectionIssue(pid, "disabled", "provider is disabled"))
            elif provider.status is ProviderStatus.UNAVAILABLE:
                reason = provider.unavailable_reason or "no reason given"
                issues.append(SelectionIssue(pid, "unavailable", f"provider unavailable: {reason}"))
            elif provider.capability_for(category) is None:
                issues.append(
                    SelectionIssue(
                        pid, "unsupported_category", f"does not support {category.value}"
                    )
                )
            else:
                adapters.append(adapter)
        if issues:
            raise ProviderSelectionError(issues)
        return adapters
