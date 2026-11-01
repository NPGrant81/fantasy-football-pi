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

## Slice 2 progress and remaining gate

`player_conflict_audit` now traces all 50 conflicting player IDs, all 101
distinct source variants and all 135 affected draft rows through selected
2018-2025 catalogs and auction events. Variant/catalog/draft evidence includes
input SHA-256 and CSV row references. Every original variant is retained.

Observed variant relationships:

- 23 suffix/punctuation alias review groups, using the existing player-service
  suffix normalizer. Native name collisions remain ambiguous.
- 22 defense-label alias review groups.
- Five nontrivial alias/identity review groups (including nickname/spelling
  differences); no fuzzy match or hardcoded nickname mapping is applied.

All 135 affected draft rows nominate one valid native auction event by
name-variant/exact-bid evidence. The 39 drafted IDs therefore have **event
resolution proposals ready for review**, not approved identities. The 11
undrafted IDs remain blocked on catalog-only identity review. None of the
single-event candidates spans multiple native player IDs within the selected
season evidence; this does not prove every variant is the same identity.

`player_conflict_dispositions` records uncovered-season, ambiguous/missing-event
and catalog-only blockers. A proposal does not certify all source variants or
approve nickname, defense or target-player mappings. Every entry remains
`approved=false`, `resolution=null`, `reconstruction_blocked=true`.

### Slice 2 resolution

The owner explicitly approved all 50 reviewed native identities and aliases:
suffix/punctuation variants, NFL team-name/D/ST labels, Chig/Chigoziem Okonkwo,
Gabe/Gabriel Davis, Hollywood/Marquise Brown, Cam/Cameron Skattebo, and the
Los/Las Vegas Raiders spelling difference. Catalog evidence distinguishes
native defense IDs from the 12 similarly named team aggregate positions.

All 11 undrafted identities have explicit catalog-backed resolutions; their
lack of draft events does not discard them or manufacture historical events.
The reviewed manifest accounts for all 50 IDs, 101 variants and 135 affected
drafts. The `approved_player_resolutions` section records identity-only approval,
catalog/event hashes and evidence references. Candidate sections remain
unchanged to preserve the original evidence trail.

Slice 2 is **complete for legacy player identity resolution**. Slice 3 may
proceed. Target-app player mapping, legacy position/team repairs, event
reconciliation and schema/import gates remain unresolved. No original source,
position field or database row was changed. Validation: 100 focused tests and
real approval-manifest replay passed. This slice made zero API requests.

## Slice 3 source-ownership resolution

The owner explicitly approved all 96 season-specific legacy owner to native
franchise mappings, covering all 12 conflicting owner IDs and 25 distinct
owner variants. The source audit uses validated player identities where
available and exact-bid native event evidence; it never approves an owner from
their name or falls back across seasons.

All 1,197 legacy draft rows now have reviewed source-ownership evidence. One
explicit exception is preserved: 2024 legacy CSV row 959 (Ezekiel Elliott,
$5) resolves from source owner 6 to source owner 3/native franchise `0002`.
The other twelve source-owner-6 events resolve to `0007`. No majority rewrite
is used; the exception retains its original owner and both source references.

Three additional event-specific identity labels were approved: 2021 Washington
Commanders/Washington Football Team defense (`0520`), 2023 legacy "Mecole Def"
to Mecole Hardman (`14113`), and 2025 Cameron/Cam Ward (`17030`). These do not
authorize global catalog changes or position/team attribute repair.

`--owner-resolutions` validates reviewed source hashes, every owner variant,
complete season-key coverage, same-season franchise evidence, row-specific
exceptions, supplemental native identities and uniqueness of native event
claims. Distinct source owners cannot collapse into one season franchise.
The approved resolution section is separate from preserved candidate evidence.

Slice 3 is complete **for legacy source ownership**, and slice 4 may proceed.
Target app user/account mappings remain a prerequisite to eventual imports;
no account identity, access, membership or database row has been changed.
No API requests were sent. Restricted approval manifests and replay reports
remain outside Git.

## Slice 4 reviewed attribute resolutions

The owner explicitly approved the row-specific repairs and snapshot-attribution
policy. The offline reconciler now replays `--attribute-resolutions` only after
the player and owner approval gates pass. All 1,197 draft rows have unique,
hash-bound attribute resolutions:

- 974 draft positions retained, 144 missing 2025 positions filled and 79
  mismatched positions corrected using the reviewed native identity/event.
- All 113 disputed-position drafts are accounted for: `8006` resolves per row
  to 12 DST, two WR, one QB and one RB; `8099` resolves to 73 DST and 24 K.
  The earlier unmatched candidate now has the approved supplemental identity
  evidence from slice 3.
- 1,044 team attributes retained; 153 repaired from the corresponding seasonal
  player catalog: three invalid 2023 values, six discrepant 2024 values and
  144 missing 2025 values.
- The six 2024 team repairs are A.J. Brown GBP to PHI, Justin Herbert SFO to LAC,
  Seattle defense NOS to SEA, Trevor Lawrence SEA to JAC, Marvin Harrison Jr.
  NEP to ARI and Jonathon Brooks TBB to CAR.
- All nine position-taxonomy rows are reviewed. Def/TD means DST and
  Kicker/PK means K **as labels only**; these approvals never authorize global
  replacement of draft position IDs.

Team repairs explicitly use `season_catalog_snapshot_not_auction_time`.
The retained catalogs do not prove NFL affiliation at auction time. Original
IDs/labels, native catalog row references and extraction timestamps remain in
the audit; the approved attribution must not be presented as auction-time
evidence. The team taxonomy is separately hash-bound, including shared
FA/FA* and OAK/LVR identifiers.

Of 1,850 player catalog rows, 540 are linked to reviewed draft identities or
approved player conflicts: 469 retain their positions, 70 have missing or
mismatched position repairs and one preserves Taysom Hill's seasonal QB (2021)
and TE (2024) positions. Resolutions are season-specific, not a global current
position update. The other 1,310 rows have no reviewed identity link and remain
preserved outside this repair scope; they are not certified or discarded.

The approval validator checks exact source/export/team hashes and complete
row-specific taxonomy, draft and linked-catalog proposals, including native
event/catalog references. Unsupported or conflicting attributes block approval.
Fresh PR feedback also exposed a catalog-only player-approval gap: contradictory
rows sharing a native ID are now preserved with hash-bound references and block
approval even when only one name matches. Selected actual catalogs contain no
such conflicts; all prior approvals replay successfully.

Slice 4 is **complete for reviewed historical source attributes**.
`approved_attribute_resolutions.ready_for_slice_5=true`;
`ready_to_import=false`. Validation: 147 focused tests, Black, flake8 and
whitespace checks passed. Both full database-copy manifests still match the
verified baselines; original sources and selected export hashes are unchanged.
No API requests, source rewrites, database repairs or imports were performed.
Slice 5 may reconcile missing/disputed events and define their ingestion grain;
target mappings and schema/runtime adoption remain separate blockers.

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
