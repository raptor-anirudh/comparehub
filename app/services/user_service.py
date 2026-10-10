"""Service for managing user identity and search preferences."""

from __future__ import annotations

from app.domain.users.models import UserPreferences, UserId
from app.domain.providers.models import ProviderSelection
from app.repositories.base import UserRepository

class UserService:
    """Orchestrates user-related domain logic."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def get_effective_providers(
        self,
        user_id: UserId | None,
        explicit_selection: list[str] | None
    ) -> ProviderSelection | None:
        """
        Determines which providers to use for a search based on priority:
        1. Explicitly provided IDs in the request.
        2. User's saved preferences (if logged in).
        3. Global defaults (return None to signal 'all enabled').
        """
        # 1. Explicit selection takes absolute priority
        if explicit_selection:
            return ProviderSelection(provider_ids=tuple(explicit_selection))

        # 2. Fallback to user preferences if identity is known
        if user_id:
            prefs = await self._user_repo.get_preferences(user_id)
            if prefs.preferred_provider_ids:
                return ProviderSelection(provider_ids=tuple(prefs.preferred_provider_ids))

        # 3. Return None to indicate "use all enabled providers"
        return None

    async def set_preferences(self, user_id: UserId, provider_ids: list[str]) -> None:
        """Save a user's preferred provider list."""
        prefs = UserPreferences(preferred_provider_ids=frozenset(provider_ids))
        await self._user_repo.update_preferences(user_id, prefs)

    async def create_user(self, username: str, email: str | None = None):
        """Create a new user account."""
        return await self._user_repo.create_user(username, email)
