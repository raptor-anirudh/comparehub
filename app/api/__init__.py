"""FastAPI application entry point and dependency injection."""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.providers.registry import ProviderRegistry
from app.providers.defaults import build_default_registry
from app.services.search import SearchService, SearchConfig
from app.repositories.sqlite_user_repo import SQLiteUserRepository
from app.services.user_service import UserService

# Global state for dependencies
# In a production app, we'd use FastAPI's dependency injection more formally
# or a container, but for this phase, a simple singleton approach works.
class AppState:
    def __init__(self):
        self.registry = build_default_registry()
        self.search_service = SearchService(self.registry)
        self.user_repo = SQLiteUserRepository("comparehub.db")
        self.user_service = UserService(self.user_repo)

state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema on startup
    await state.user_repo.init_db()
    yield
    # Cleanup could go here

app = FastAPI(
    title="CompareHub API",
    description="Transparent comparison platform for e-commerce",
    lifespan=lifespan
)

# Import routers after app creation to avoid circular imports
from app.api import users, preferences, search
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(preferences.router, prefix="/preferences", tags=["Preferences"])
app.include_router(search.router, prefix="/search", tags=["Search"])
