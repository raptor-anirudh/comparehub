# ADR 0001: Modular monolith
Status: accepted. Context: small team, learning project, need fast iteration.
Decision: single deployable FastAPI service with strict module boundaries.
Consequences: simple ops; boundaries enforced by convention and review, so
import direction (see architecture.md) must be checked.
