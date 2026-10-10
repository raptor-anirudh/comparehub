"""User preferences endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from app.api import state
from app.domain.users.models import UserPreferences

class PreferencesUpdate(BaseModel):
    preferred_provider_ids: list[str]

router = APIRouter()

@router.get("/", response_model=UserPreferences)
async def get_preferences(x_user_id: str = Header(...)):
    """Get preferences for the authenticated user."""
    # The UserPreferences model is returned. If not found in DB,
    # the repo returns a default instance.
    return await state.user_repo.get_preferences(x_user_id)

@router.put("/", status_code=204)
async def update_preferences(
    prefs_in: PreferencesUpdate,
    x_user_id: str = Header(...)
):
    """Update preferences for the authenticated user."""
    # First verify user exists
    user = await state.user_repo.get_user(x_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await state.user_service.set_preferences(x_user_id, prefs_in.preferred_provider_ids)
    return None
