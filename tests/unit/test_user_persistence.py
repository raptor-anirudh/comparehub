"""Tests for user persistence and preference resolution."""

from __future__ import annotations

import pytest
import os
import asyncio
from app.domain.users.models import User, UserPreferences
from app.repositories.sqlite_user_repo import SQLiteUserRepository
from app.services.user_service import UserService
from app.domain.providers.models import ProviderSelection

@pytest.fixture
async def user_repo(tmp_path):
    # Use a temporary file for the DB to avoid pollution
    db_file = tmp_path / "test_users.db"
    repo = SQLiteUserRepository(str(db_file))
    await repo.init_db()
    return repo

@pytest.fixture
async def user_service(user_repo):
    return UserService(user_repo)

@pytest.mark.asyncio
async def test_create_and_get_user(user_repo):
    username = "test_user"
    email = "test@example.com"

    user = await user_repo.create_user(username, email)

    assert user.id is not None
    fetched = await user_repo.get_user(user.id)
    assert fetched is not None
    assert fetched.username == username
    assert fetched.email == email

@pytest.mark.asyncio
async def test_preferences_crud(user_repo):
    user = await user_repo.create_user("pref_user")

    # Initially should be empty
    prefs_init = await user_repo.get_preferences(user.id)
    assert prefs_init.preferred_provider_ids == frozenset()

    # Update preferences
    preferred = {"alpha", "beta"}
    prefs_update = UserPreferences(preferred_provider_ids=frozenset(preferred))
    await user_repo.update_preferences(user.id, prefs_update)

    # Verify retrieval
    prefs_fetched = await user_repo.get_preferences(user.id)
    assert prefs_fetched.preferred_provider_ids == frozenset(preferred)

@pytest.mark.asyncio
async def test_effective_provider_resolution(user_service, user_repo):
    # Setup user with preferences
    user = await user_repo.create_user("resolution_user")
    preferred = {"alpha", "beta"}
    await user_service.set_preferences(user.id, list(preferred))

    # Case 1: Explicit selection takes priority
    explicit = ["beta", "gamma"]
    res1 = await user_service.get_effective_providers(user.id, explicit)
    assert res1.provider_ids == tuple(explicit)

    # Case 2: No explicit selection -> use user preferences
    res2 = await user_service.get_effective_providers(user.id, None)
    # Use set comparison because order in frozenset isn't guaranteed
    assert set(res2.provider_ids) == preferred

    # Case 3: No user ID, no explicit selection -> use all (empty selection)
    res3 = await user_service.get_effective_providers(None, None)
    assert res3.provider_ids == ()

@pytest.mark.asyncio
async def test_no_user_no_prefs_resolution(user_service):
    # Guest user, no selection
    res = await user_service.get_effective_providers(None, None)
    assert res.provider_ids == ()
