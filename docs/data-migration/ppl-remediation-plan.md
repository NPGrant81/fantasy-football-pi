# PPL historical remediation plan (Refs #524-#528)

## Objective and invariants

Resolve every legacy ID conflict before reconstructing history, as selected by
the owner. Native MFL records are supporting evidence, not permission to replace
legacy history. Keep the original databases, retained CSVs and verified backups
unchanged. Work on copies only after reviewed mappings and schema adoption.

Evidence: PR #557, the restricted copied-database reconciliation and native
source worksheets. Current coverage: 1,197 legacy CSV drafts, 1,050 staging
drafts and 1,198 selected native MFL auction records for 2018-2025. The differences
are not interchangeable: 147 CSV rows are absent from staging, while 2024 has
140 native records versus 139 legacy CSV records.

No name, numeric-ID overlap, majority vote or absence of a candidate is an
identity approval. Source hashes and row references must accompany resolutions.
Native event evidence locators are not final ingestion idempotency keys.

## Slices and acceptance gates

| Slice | Scope | Prerequisite | Acceptance |
| --- | --- | --- | --- |
| 1 | Position conflict forensic audit | Preserved CSVs and selected native catalogs/events | Account for every draft row referencing conflicting position IDs; preserve all candidate events and expose mixed native-position evidence without replacing IDs. |
| 2 | Resolve 50 player-ID conflicts | Slice 1 | Resolve every source variant and affected season/event using evidence; explicitly separate reused IDs and unresolvable cases. No unresolved player conflict passes the gate. |
| 3 | Resolve 12 owner-ID conflicts | Slice 2 | Approve season-specific owner/franchise identities; resolve the 2024 split/shared evidence without cross-season or majority fallback. |
| 4 | Finalize position and missing-attribute repairs | Slices 1-3 | Approve per-row position/team resolutions, distinguishing taxonomy aliases from reused draft IDs; account for 2025 blanks and the three 2023 invalid team attributes. |
| 5 | Reconcile all missing/disputed events | Slice 4 | Account for 147 CSV/staging gaps, the 2024 native/CSV discrepancy and repeated acquisitions; retain every original event and define reviewed source-event grain. |
| 6 | Migration-owned schema and runtime parity | Slice 5 | Recognize the observed unknown 0029 contract without blind stamping; preserve fields, add reviewed forward migrations and bootstrap parity, implement season-aware budgets/native identities/stub exclusions; pass migration/runtime tests. |
| 7 | Apply approved repairs on working copies | Slice 6 | Import only approved mappings/events; verify exact counts/bids, provenance, preservation and idempotent reruns. Backed-up production promotion requires separate approval and validation. |

Player and owner resolutions must include an explicit unresolved disposition
when available evidence is insufficient. Such a disposition documents the
blocker; it does not permit reconstruction to continue.

## Slice 1 implementation and finding

The offline [source reconciler](../../backend/scripts/reconcile_ppl_mfl_sources.py)
now emits `position_conflict_audit` for each selected season. It compares all
retained player-name variants and exact bids against native auction events
**without using the disputed legacy position as a matching filter**.

The conflicting taxonomy rows are:

- `8006`: `Def` / `TD`.
- `8099`: `Kicker` / `PK`.

Verified evidence for all 113 affected 2018-2024 draft rows:

| Legacy position ID | Affected rows | Candidate native-position sets |
| --- | --- | --- |
| 8006 | 16 | 12 defense, two WR, one QB, one RB |
| 8099 | 97 | 72 defense, 24 kicker, one without a candidate |

These are candidate observations, not approved identities. A global
`8099 -> kicker` or `8006 -> defense` rewrite is unsafe. Resolving the label
aliases alone would not repair the draft data. Slice 1 is an evidence audit,
not an import or a claim that the two position conflicts are resolved.

Validation: 79 focused tests passed. The actual source audit produced exactly
113 distinct legacy draft-row references: 112 single-event review candidates
and one without a candidate. All remain unapproved. Input hashes matched the
previous retained worksheet; both working-copy table schemas, counts and
complete row hashes still matched their verified backup manifests. This slice
made zero API requests.

The output retains all native event candidates with hash-bound CSV-row
references, keeps rows unapproved and records the methodology/limitations.
It contains IDs and aggregates rather than owner/player names. Reports stay
in restricted storage outside Git. Inputs and databases are unchanged.

## API policy

Reuse retained exports first. Any new request is one season/report in a short,
bounded burst, using public access where possible. Stop on authentication,
throttling or unexpected redirects; do not launch an all-season retry sweep.
Do not place credentials in chat, Git, reports or shell history.

## Tracking

PR #557 contains the read-only evidence tooling; merging it does not close
#524-#528. Record slice completion, residual blockers, commit/PR references and
validation on #528. Production deployment and promotion are not included in
this plan's first slice.
