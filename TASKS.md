# TASKS

**Current phase:** 1 complete -> next: Phase 2 (search orchestration)

## Environment facts (verified 2026-10-10)
- Python 3.12.3, Node 22, Git 2.43 available.
- Docker: NOT installed -> Docker/Compose files cannot be verified here.
- PostgreSQL: NOT installed -> DB tests will need SQLite or an external Postgres.
- Network: only package registries and GitHub reachable from the shell.

## Phase 0 — Requirements and feasibility
- [x] docs/PRD.md
- [x] docs/architecture.md + ADRs 0001-0003
- [x] docs/provider-feasibility.md (researched via official docs; see caveats)
- [x] docs/data-quality-policy.md
- [x] TASKS.md

## Phase 1 — Domain + provider abstraction  [DONE, verified 2026-10-10]
- [x] Domain models (Money, PriceBreakdown, Charge, DataProvenance, ProductResult,
      Provider, ProviderCapability, ProviderSelection, ProviderSearchStatus,
      SearchQuery/ProductQuery/ComparisonPreference, SearchResponse)
- [x] ProviderAdapter interface + ProviderRegistry (collects all selection issues)
- [x] Mock providers: alpha, beta (distinct raw schemas), failure modes, and
      UnavailableProviderAdapter placeholders for flipkart / amazon-in
- [x] Verified: pytest 54 passed; ruff check + format clean; mypy --strict clean;
      reproduced in a fresh venv via `pip install -e ".[dev]"`
- Bug found in review and fixed: whitespace-only query matched all listings
  (regression tests added).

### Phase 1 known limitations
- Mock search is a naive token matcher; no normalization or variant matching yet.
- Budget semantics undecided: A-104 is 799 advertised but 848 total. Decide in
  Phase 8 whether max_price applies to advertised or known total.
- `mock-flaky` is in the default registry and always times out (by design).
- Provider-supplied URLs are validated as http(s) only; output sanitization and
  SSRF controls are Phase 10 work.
- Docker, Postgres, and Next.js are untested (not installed / not started here).

## Later phases
2 Search orchestration · 3 DB/preferences · 4 API · 5 Real provider ·
6 Matching · 7 AI query parsing · 8 Ranking · 9 Frontend · 10 Security ·
11 Test/eval · 12 Observability · 13 Docker/CI · 14 Docs

## Blockers / owner actions
- Flipkart affiliate credentials (needed for first real adapter).
- Amazon Creators API eligibility confirmation.
- Auth approach decision (Phase 3; dev stub planned).
