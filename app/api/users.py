"""User management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from app.api import state
from app.domain.users.models import User

class UserCreate(BaseModel):
    username: str
    email: str | None = None

router = APIRouter()

@router.post("/", response_model=User, status_code=201)
async def create_user(user_in: UserCreate):
    """Create a new user account."""
    return await state.user_service.create_user(user_in.username, user_in.email)

@router.get("/{user_id}", response_model=User)
async def get_user(user_id: str):
    """Retrieve user details."""
    user = await state.user_repo.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
