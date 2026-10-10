"""Shared enumerations for the domain layer."""

from __future__ import annotations

from enum import StrEnum


class Category(StrEnum):
    """Comparison categories. Add members here to support new categories."""

    ECOMMERCE = "ecommerce"


class SourceKind(StrEnum):
    """Where a datum came from. See docs/data-quality-policy.md."""

    LIVE = "live"
    CACHED = "cached"
    STALE = "stale"
    ESTIMATED = "estimated"
    MOCK = "mock"
    UNAVAILABLE = "unavailable"


class ChargeStatus(StrEnum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class TotalKind(StrEnum):
    KNOWN = "known"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class TaxTreatment(StrEnum):
    INCLUSIVE = "inclusive"
    EXCLUSIVE = "exclusive"
    UNKNOWN = "unknown"


class StockStatus(StrEnum):
    IN_STOCK = "in_stock"
    LIMITED = "limited"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"


class ProviderStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"


class SearchState(StrEnum):
    """Per-provider outcome of one search."""

    SUCCESS = "success"
    EMPTY = "empty"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    INVALID_RESPONSE = "invalid_response"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


class RankingMode(StrEnum):
    LOWEST_TOTAL_COST = "lowest_total_cost"
    BEST_MATCH = "best_match"
    PREFERRED_BRAND = "preferred_brand"
    BEST_RETURNS = "best_returns"
    FASTEST_DELIVERY = "fastest_delivery"
    BALANCED = "balanced"
