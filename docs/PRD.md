# CompareHub — Product Requirements (MVP)

## Problem
Shoppers compare the same item across several stores by hand. Existing
comparison sites choose the stores for you. CompareHub lets the user choose
which providers are searched and shows a transparent, consistent comparison.

## MVP scope
**In:** one category (e-commerce: electronics, proven with USB pen drives);
user-selected providers; mock providers; concurrent search with partial-failure
handling; normalization; variant-safe matching; deterministic explainable
ranking; REST API; persistence of provider groups and preferences; Next.js UI;
optional AI query parsing with deterministic fallback.

**Out (explicitly):** transportation, food, travel, insurance; user-added
arbitrary websites; scraping; checkout or purchasing; price alerts; microservices;
Redis; vector DB; LangChain/LangGraph; any claim of live data without a real
verified integration.

## Users and stories
1. As a shopper I pick providers and search so only those are queried.
2. As a shopper I see price, known charges, and total, with unknowns marked.
3. As a shopper I never see 32 GB and 64 GB listings merged as one product.
4. As a shopper I see which providers failed or timed out, and why.
5. As a shopper I sort by total cost, delivery, returns, or a balanced score and
   understand why an item ranked where it did.
6. As a shopper I save provider groups and preferences for later.
7. As a shopper I can tell demo data from live data at a glance.
8. As a developer I add a provider without touching search orchestration.

## Acceptance criteria (testable)
- AC1: Search over 3 providers where 1 times out returns the other 2 results and
  an explicit timeout status for the third.
- AC2: Adding a provider requires only a new adapter plus registration.
- AC3: Different capacities/variants are never grouped as equivalent.
- AC4: Missing values serialize as unknown, never 0.
- AC5: Same input and preferences give identical ranking.
- AC6: A hard budget filter excludes over-budget items regardless of score.
- AC7: Malformed LLM output cannot reach business logic.
- AC8: Core tests pass with no network and no paid services.

## Success metrics
Matching precision/recall on a labeled fixture set (targets set after first
measurement); p95 search latency on mock providers (baseline first); zero
unmarked mock results in the UI; zero secrets in the repo.

## Failure conditions
Any fabricated price/policy/availability; a provider failure failing the whole
search; mock data labeled live; unvalidated LLM output used in logic.

## Assumptions (to confirm)
- Default currency INR; default market India.
- Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL in deployment.
- Dev environment here has no Docker or Postgres; those parts are written but
  cannot be verified in this sandbox (see TASKS.md).
- Authentication method is undecided; Phase 3 will use an isolated dev stub.
