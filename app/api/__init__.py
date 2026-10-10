"""FastAPI application entry point and dependency injection."""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.providers.registry import ProviderRegistry
from app.providers.defaults import build_default_registry
from app.services.search import SearchService, SearchConfig
from app.repositories.sqlite_user_repo import SQLiteUserRepository
from app.services.user_service import UserService

# Global state for dependencies
class AppState:
    def __init__(self):
        self.registry = build_default_registry()
        # Debug: Log registered providers
        providers = [p.id for p in self.registry.list_providers()]
        print(f"DEBUG: Registered providers: {providers}")

        self.search_service = SearchService(self.registry)
        self.user_repo = SQLiteUserRepository("comparehub.db")
        self.user_service = UserService(self.user_repo)

state = AppState()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema on startup
    await state.user_repo.init_db()
    yield

app = FastAPI(
    title="CompareHub API",
    description="Transparent comparison platform for e-commerce",
    lifespan=lifespan
)

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Map domain validation errors (like ProviderSelectionError) to 422."""
    return JSONResponse(
        status_code=422,
        content={"detail": str(exc)},
    )

# Import routers after app creation to avoid circular imports
from app.api import users, preferences, search
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(preferences.router, prefix="/preferences", tags=["Preferences"])
app.include_router(search.router, prefix="/search", tags=["Search"])
