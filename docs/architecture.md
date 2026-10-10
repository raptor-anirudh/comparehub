# Architecture

Modular monolith. Domain logic has no dependency on FastAPI, the database, or
any LLM vendor.

```
domain/      pure models + rules (Pydantic, Decimal)   <- depends on nothing
providers/   adapter interface, registry, mocks         <- depends on domain
services/    search, normalization, matching, ranking   <- domain + providers
ai/          optional query parser behind an interface  <- domain
repositories/ db/                                       <- domain
api/         FastAPI routes + schemas                   <- services
```

## Search flow (Phase 2)
validate -> resolve selected providers (registry) -> capability check ->
concurrent fan-out (per-provider timeout, semaphore) -> collect results and
per-provider status -> normalize -> match -> filter -> rank -> respond.

## Key boundaries
- **ProviderAdapter**: one class per vendor; the only place vendor schemas exist.
- **ProviderRegistry**: resolves only registered and enabled adapters.
- **Hard filters vs ranking**: filters decide eligibility; ranking only orders
  eligible items.

## Rationale for deviations from the suggested layout
Phase 1 follows the suggested layout under `app/`; domain models live in `app/domain/{products,providers,comparisons}/models.py`.
