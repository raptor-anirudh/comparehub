# ADR 0003: Decimal money and explicit unknowns
Status: accepted. Decision: Money uses Decimal + ISO currency. Optional charges
carry a status (known/unknown/not_applicable) instead of defaulting to zero.
Consequences: totals can legitimately be "unknown"; ranking needs an explicit
missing-data rule (Phase 8).
