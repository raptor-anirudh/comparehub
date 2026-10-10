"""Search orchestration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, Query
from pydantic import BaseModel
from typing import Optional

from app.api import state
from app.domain.comparisons.models import SearchQuery, SearchResponse, ProductQuery, ComparisonPreference
from app.domain.providers.models import ProviderSelection

# Request models for the API to decouple internal domain models from the wire format
class SearchRequest(BaseModel):
    text: str
    category: str # Simplified for API; maps to Category enum
    market: str = "IN"
    max_price: float | None = None
    required_attributes: dict[str, str] = {}
    # Optional: explicit provider selection. If omitted, preferences are used.
    providers: list[str] | None = None
    # Sorting/Ranking preferences
    ranking_mode: str = "lowest_total_cost"

router = APIRouter()

@router.post("/", response_model=SearchResponse)
async def search(
    req: SearchRequest,
    x_user_id: Optional[str] = Header(None)
):
    """
    Perform a product comparison search.

    Priority for provider selection:
    1. `req.providers` (Explicit)
    2. User preferences (if `x_user_id` is provided)
    3. All enabled providers (Default)
    """
    # 1. Map API request to Domain models
    try:
        from app.domain.enums import Category, RankingMode
        category = Category[req.category.upper()]
    except KeyError:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"Invalid category. Valid: {[c.name for c in Category]}")

    product_query = ProductQuery(
        text=req.text,
        market=req.market,
        # In a real app, we'd convert float to Money domain model here
        max_price=None, # Simplified for this stub
        required_attributes=req.required_attributes
    )

    # Handle Provider Selection
    selection = None
    if req.providers:
        selection = ProviderSelection(provider_ids=tuple(req.providers))

    # 2. Build the SearchQuery
    # We provide a default empty selection if none is resolved yet;
    # SearchService will handle the resolution via UserService.
    query = SearchQuery(
        category=category,
        product=product_query,
        selection=selection or ProviderSelection(provider_ids=()),
    )

    # 3. Execute search via service
    return await state.search_service.search(
        query=query,
        user_id=x_user_id,
        user_service=state.user_service
    )
