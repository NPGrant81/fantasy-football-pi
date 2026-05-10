# Season Reset and New-League Year Runbook (Issue #113)

## Purpose

This runbook defines the minimum safe process for starting a new fantasy season
while preserving historical integrity and model reproducibility.

Related references:

- `docs/restore.md`
- `docs/MFL_HISTORICAL_DATA_OPERATIONS.md`
- `docs/model-versioning.md`
- `docs/DATA_QUALITY_RUNBOOK.md`

## Preconditions

Before reset:

- Production backup completed and restorable.
- Current season data refresh and reconciliation complete.
- Champion model version and dataset hash recorded.
- Open issues related to in-season data integrity triaged.

## Reset Workflow

1. Freeze window
- Announce maintenance window and freeze write-heavy commissioner operations.

2. Snapshot and archive
- Capture DB backup and ETL artifact snapshot.
- Archive prior season derived outputs with season label.

3. New season configuration
- Set/verify new season year in environment/config.
- Confirm league settings import includes roster/slot limits.
- Validate owner/team mapping consistency.

4. Re-seed and baseline refresh
- Run required seed/refresh scripts for season bootstrapping.
- Rebuild draft-value and related baseline datasets as needed.

5. Validation gates
- Execute data quality runbook checks.
- Execute backend and frontend regression suites for critical flows.
- Validate draft simulation returns league-configured caps and roster size.

6. Model and simulation readiness
- Confirm active champion model version remains valid for new season context.
- Trigger challenger training cycle if drift or schema shifts are detected.

7. Post-reset verification
- Smoke test commissioner pages, draft analyzer, and advisor/chatbot endpoints.
- Record reset completion notes and any follow-up actions.

## Required Evidence for Completion

A reset is complete only when all evidence is captured:

- backup artifact id or path
- executed command log summary
- validation gate results
- model version + feature schema hash
- known-risk list with owners and due dates

## Rollback Criteria

Trigger rollback to pre-reset snapshot if any of the following occurs:

- critical data-contract validation failures
- unrecoverable owner/team mapping mismatches
- draft simulation or recommendation flows fail smoke tests
- authentication/authorization regressions block commissioner operations

## Ownership

- Primary owner: platform/commissioner operations maintainer
- Secondary owners: backend and ML maintainers for validation and model readiness
