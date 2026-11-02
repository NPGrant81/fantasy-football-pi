# ADR-001: Historical ingestion schema and guarded adoption

## Status and approval

Accepted 2026-11-01 for slice 6, after explicit operator approval of guarded
adoption, source-event uniqueness and validation on a new disposable clone.
This does not authorize historical imports or production changes.

## Date

2026-11-01

## Context

The preserved application database reports
`0029_harden_historical_ingestion_models`, but no corresponding migration exists
in the available graph or Git history. Its source-event, provider and stub fields
must survive adoption. The database also has runtime-created defaults/indexes
that differ from the migration-owned bootstrap contract.

The approved slice 5 event plan preserves distinct auction observations.
The originally suggested owner/player/season uniqueness in issue #524 would
collapse repeated acquisitions and therefore cannot be used as event identity.

## Decision

- Add a new forward revision after the published `0028` head. Do not invent,
  reuse or rewrite the missing `0029` revision.
- Adopt only the pinned complete observed schema with an explicit copy-only
  migration command. Verify the unknown revision and full schema fingerprint
  under locks, reconcile without dropping tables/columns, verify bootstrap
  equivalence and preserved data, then record the new revision atomically.
  Normal startup still rejects unknown revisions.
- Maintain both fresh-bootstrap and incremental paths at the same contract.
- Preserve the observed legacy keeper, mapping, season-provider and scoring
  columns in place as nullable evidence. They are not active configuration.
  Do not remove legacy `player_seasons.mfl_id` evidence or infer canonical
  player bindings from it.
- Use league/source/event uniqueness, not owner/player uniqueness. Legacy rows
  without source event identities remain preserved. A source event ID requires
  a nonempty source and league. Identical reviewed observation keys reject
  duplicates; distinct acquisitions and seasons remain representable.
- Make waiver budget uniqueness season-aware, provider IDs native strings and
  historical account exclusion explicit while retaining legacy-name safeguards.
- Keep target mappings and all historical imports behind the slice 7 gate.

## Consequences

Adoption is intentionally narrow and refuses other schema fingerprints.
Runtime-created differences are reviewed as part of the complete pinned input,
not silently accepted by migration startup. Fresh and adopted schemas must
converge before adoption is recorded. Any incompatible rows or unexpected
structure abort the transaction; no silent deduplication or account merging is
permitted. Source observation fingerprints still do not establish chronology.

## Alternatives

Blindly stamping the missing revision would conceal unreviewed drift.
Recreating that revision would falsely claim knowledge of its original script.
Dropping legacy fields to force parity would lose historical evidence.
Owner/player/season uniqueness would collapse legitimate repeated observations.
All four alternatives were rejected.

## Related decisions

This extends the historical-user naming safeguard with an explicit flag; it
does not replace legacy-name exclusion or the SQLAlchemy-only runtime boundary.
