# ADR 0002: Mock-first providers
Status: accepted. Context: see provider-feasibility.md; no verified credentials,
and Uber/Rapido have no verified public API.
Decision: build and test everything against deterministic mock adapters; real
adapters are added only with verified docs and owner-supplied credentials.
Consequences: MVP is an architecture proof, not a live product. All mock output
is tagged `mock` and labeled DEMO DATA.
