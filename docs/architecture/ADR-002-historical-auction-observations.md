# ADR-002: Separate historical auction observations from live ownership

## Status

Accepted 2026-11-02 for slice 7 following explicit operator approval of
evidence-backed target representatives, archival accounts and a separate
historical-observation model with history-reader integration and isolation tests.
Production promotion remains separately gated.

## Context

The approved 1,198 MFL records are auction observations, not a transaction
ledger or proof of current ownership. Several live consumers query all
`draft_picks` in a league, including waivers and player availability. Loading
observations into that table would falsely reserve players and could create
mutable historical roster entries.

The adopted copy contains duplicate player snapshots, no canonical MFL bindings
for the required players and no 2018-2025 archival accounts. Some retained
season rows incorrectly mix different MFL identities on one target player.

## Decision

- Store reviewed observations in a migration-owned, separately constrained
  `historical_auction_observations` table, not `draft_picks`, roster, transaction
  or financial tables. Integrate the authenticated, league-scoped historical
  draft-history and season readers; do not infer chronology.
- Retain exact bids with a bounded `NUMERIC(18,6)` contract. Refuse out-of-range
  or over-scale values before writing; never round.
- Store complete source-event evidence, reviewed snapshot attributes and
  hash-bound source/target approvals durably with every observation.
- Prefer a corroborated existing provider binding; otherwise explicitly approve
  the lowest-ID representative among same-season native-corroborated candidates.
  This selects a representative, not a name-based identity inference.
  Exclude mixed-native-ID records from selection while preserving every
  original row and relationship. Do not merge or redirect duplicates.
- Create nonprivileged, non-login season/franchise archival accounts. Refuse
  username, league, privilege or identity conflicts rather than repurpose users.
- Apply only to an explicitly named new local working clone whose original
  contents match the reviewed snapshot. Verify the complete schema and original
  row preservation, exact approved observations and totals. A second application
  must make zero data or sequence changes; conflicting reruns roll back.

## Consequences

Historical observations cannot enter live roster mutations merely by existing
in the database. Existing live draft/keeper behavior stays unchanged.
Authenticated historical readers can display reviewed observations with explicit
observation grain and snapshot attribution.

Roster-based analytics do not automatically gain reconstructed auction data.
Consumers needing auction observations must explicitly use the new model;
this is not a reconstruction of end-of-season rosters or transaction chronology.
Legacy duplicate and mixed-identity rows remain evidence requiring separately
approved remediation, not silent cleanup.

## Alternatives

Adding all observations to `draft_picks` and filtering live readers would retain
the semantic mismatch and make every future roster query a historical-mutation
risk. Creating new players for every MFL identity would avoid representative
review but duplicate all 472 already corroborated identities. Neither was chosen.

## Related decisions

- [ADR-001](ADR-001-historical-ingestion-adoption.md): guarded adoption and
  source-observation uniqueness. This extends its slice-7 gate; existing
  draft/transaction provenance fields remain intact.
