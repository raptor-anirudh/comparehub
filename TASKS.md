# TASKS

**Current phase:** 1 — Domain models and provider abstraction (in progress)

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

## Phase 1 — Domain + provider abstraction
- [ ] Domain models
- [ ] ProviderAdapter interface + registry
- [ ] Mock providers (incl. failure modes)
- [ ] Unit tests passing, ruff + mypy clean

## Later phases
2 Search orchestration · 3 DB/preferences · 4 API · 5 Real provider ·
6 Matching · 7 AI query parsing · 8 Ranking · 9 Frontend · 10 Security ·
11 Test/eval · 12 Observability · 13 Docker/CI · 14 Docs

## Blockers / owner actions
- Flipkart affiliate credentials (needed for first real adapter).
- Amazon Creators API eligibility confirmation.
- Auth approach decision (Phase 3; dev stub planned).
