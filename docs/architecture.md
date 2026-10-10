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

## Search orchestration (Phase 2)

`app/services/search.py` (`SearchService`) and `app/services/filters.py`. It depends only on
`ProviderRegistry` and the `ProviderAdapter` interface, never on a concrete provider.

Flow: resolve selection (raises `ProviderSelectionError` listing *all* bad ids) -> per provider:
`validate_query` -> bounded-concurrency call under a per-attempt timeout -> bounded retry ->
accept/validate results -> merge in selection order -> hard filters -> `SearchResponse`.

Decisions:
- **Failure isolation.** Every selected provider gets exactly one `ProviderSearchStatus`. Adapter
  errors, timeouts, buggy validators and unexpected exceptions all become statuses; users see a
  generic message for unexpected errors (details go to logs only).
- **Retries.** Only `TIMEOUT` and `UNAVAILABLE` are retried (search is a read-only lookup), with
  exponential backoff, at most `max_retries` (default 1, hard cap 3). `RATE_LIMITED` and
  `INVALID_RESPONSE` are never retried in-call; `retry_after_seconds` is surfaced instead.
- **Cancellation.** Cancelling the caller cancels all in-flight provider calls (`TaskGroup`).
- **Defensive checks.** Results attributed to a different provider mark the provider
  `INVALID_RESPONSE`; per-provider results are capped; duplicate `(provider, listing_id)` removed.
  Cross-provider matching/dedup is deliberately Phase 6.
- **Hard filters are re-enforced by the service**, not delegated to adapters (adapters may filter
  server-side as an optimization only).
- **Budget semantics (resolves the Phase 1 open question).** `max_price` excludes a listing only
  when it is *provably* over budget: advertised > max, or a known/estimated total > max. A listing
  with an unknown total but advertised price within budget is kept, because an unknown is not
  evidence of exceeding the budget; ranking/UI must show that its total is unknown.
  A different currency than the budget is excluded (no FX guessing).
- **Required attributes.** Unverifiable hard requirements exclude the listing; exact
  case-insensitive equality only until Phase 6 normalization.
- **Transparency.** `SearchResponse.filtered_out_count` reports how many listings hard filters removed.
- **Privacy.** Logs contain provider id, state, latency, attempts, count; never query text (tested).

Known limitations: no global search deadline (worst case ~ timeout x (1+retries) per provider,
run concurrently); no per-provider rate limiter or circuit breaker yet; no caching.
