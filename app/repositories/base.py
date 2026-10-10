"""Abstract repository interface for user data."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from app.domain.users.models import User, UserPreferences, UserId

class UserRepository(ABC):
    """Interface for persisting user identities and preferences."""

    @abstractmethod
    async def get_user(self, user_id: UserId) -> User | None:
        """Retrieve a user by their ID."""
        ...

    @abstractmethod
    async def get_preferences(self, user_id: UserId) -> UserPreferences:
        """Retrieve preferences for a user. Returns defaults if none found."""
        ...

    @abstractmethod
    async def update_preferences(self, user_id: UserId, preferences: UserPreferences) -> None:
        """Save updated preferences for a user."""
        ...

    @abstractmethod
    async def create_user(self, username: str, email: str | None = None) -> User:
        """Create a new user record."""
        ...
