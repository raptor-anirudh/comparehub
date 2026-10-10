# CompareHub

User-configurable comparison platform: search only the providers you choose and
compare results with transparent, provenance-tracked data.

> **Status: Phase 1 of 14 — architecture proof, mock data only.**
> This is NOT a working multi-vendor live comparison product. All providers are
> deterministic demos (fictional brands) or explicit `unavailable` placeholders.
> See [docs/provider-feasibility.md](docs/provider-feasibility.md) for why.

## What exists today
- Typed domain models (Decimal money, honest "unknown" totals, provenance)
- `ProviderAdapter` interface + `ProviderRegistry`
- Two mock e-commerce adapters with different vendor schemas, simulated failures
  (timeout, rate limit, invalid response, unavailable), and placeholders for
  blocked real providers (Flipkart, Amazon India)

Not yet built: search orchestration, matching, ranking, database, API, AI,
frontend, Docker, CI. See [TASKS.md](TASKS.md).

## Quick start (verified in a clean venv)
Requires Python 3.12+.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q          # 54 passed
ruff check . && ruff format --check .
mypy
```

## Layout
```
app/domain/      pure models (money, products, providers, comparisons)
app/providers/   adapter interface, registry, mock adapters, default registry
tests/unit/      deterministic unit tests (no network)
docs/            PRD, architecture, ADRs, feasibility, data-quality policy
```

## Adding a provider
Implement `ProviderAdapter` (identity, `search`) and call `registry.register()`.
No orchestration code changes are needed.
