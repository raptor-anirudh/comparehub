# Data Quality, Provenance and Freshness Policy

## Rules
1. **Unknown is not zero.** Missing fields are `None`/`UNKNOWN`, never `0`.
2. **Provenance on every result:** provider id, source kind, source URL when
   known, retrieval timestamp, and per-field confidence where relevant.
3. **LLMs never supply facts.** Prices, availability, specs, and policies come
   only from provider data.
4. **Money is `Decimal`** with an explicit currency. No floats.

## Source kinds
| Kind | Meaning | UI label |
|---|---|---|
| `live` | Fetched from the provider during this request | Live |
| `cached` | Served from our cache within TTL | Cached (age) |
| `stale` | Cached but past TTL | Stale (age) |
| `estimated` | Provider-supplied estimate, not a firm price | Estimate |
| `mock` | Deterministic demonstration data | DEMO DATA |
| `unavailable` | Provider could not supply data | Unavailable |

`mock` results must be impossible to confuse with `live` in API and UI.

## Price semantics
- **Advertised price:** the listed item price.
- **Known mandatory charges:** fees the provider explicitly reports.
- **Known total:** advertised + all mandatory charges, only when every charge is
  known to be reported.
- **Estimated total:** includes at least one estimated charge.
- **Unknown total:** any mandatory charge status is unknown.
Totals are never computed by assuming a missing charge is zero.

## Freshness
Each provider declares a TTL. A result older than its TTL is `stale` and must
say so. Ranking may not silently treat stale prices as live.
