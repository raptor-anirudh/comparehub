"""User-side domain models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# We use a simple string ID for the user in the domain layer.
# This decouples the domain from specific DB primary key types (like UUID or Integer).
UserId = str

class User(BaseModel):
    """Basic user identity."""
    model_config = ConfigDict(frozen=True)

    id: UserId
    username: str = Field(min_length=1, max_length=50)
    email: str | None = None

class UserPreferences(BaseModel):
    """User-configurable search defaults."""
    model_config = ConfigDict(frozen=True)

    # The set of providers the user prefers to search by default.
    # If empty, the system should fall back to global defaults.
    preferred_provider_ids: frozenset[str] = Field(default_factory=frozenset)

    # Future preferences (e.g., default currency, category) can be added here.
