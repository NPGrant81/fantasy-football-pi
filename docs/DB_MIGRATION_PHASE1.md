# DB Organization — Phase 1 (Issue #60)

## Goal

Establish a predictable PostgreSQL folder layout and complete a safe Alembic cutover to the `/db` structure.

## Completed Cutover

- `/db` hierarchy is established and documented.
- Domain purpose is defined for each folder.
- Migration ownership conventions are documented.
- Runtime path switch is complete.

## Current State

- Alembic runtime config points to `/db` with revisions in `db/migrations`.
- Retired `backend/alembic/` artifacts have been removed.
- Earlier branches were unified by merge revision `5517dcbf0494`; the current
  canonical graph has the single head `0028_reconcile_runtime_schema`.
- CI rejects any future `backend/**/alembic/versions/*.py` revision file.

See `docs/MIGRATION_LEGACY_INVENTORY.md` for the disposition of the retired lineage.
Disposable PostgreSQL execution and deployed revision-history verification
remain release gates for retiring that lineage.

## Naming and Placement Standard

- Revisions: sequence or timestamp prefix + descriptive slug (snake_case).
- Schema SQL: `db/schema/<domain>/<entity>.create.sql` (or equivalent domain grouping).
- Seed SQL: `db/seeds/<domain>.<purpose>.sql`.
- Functions/views/triggers/extensions/utils: keep one object per file where practical.

## Definition of Done

- [x] `/db` scaffold is present and documented.
- [x] Folder purpose and naming conventions are written.
- [x] Safe cutover checklist is documented for Phase 2.
- [x] Alembic runtime cutover executed and validated (Phase 2).

## Phase 2 Execution Notes (Workspace)

- `backend/alembic.ini` now uses:
   - `script_location = %(here)s/../db`
   - `version_locations = %(here)s/../db/migrations`
- Added `db/env.py` and `db/script.py.mako` for full Alembic compatibility.
- Performed migration resilience sweep across `0003` through `0012` to guard against pre-existing schema drift.
- Verified with `alembic stamp 0001_create_draft_value_tables` followed by `alembic upgrade head`; migration chain now completes and `current` matches `heads`.
