# DB Organization — Phase 1 (Issue #60)

## Goal

Establish a predictable PostgreSQL folder layout and complete a safe Alembic cutover to the `/db` structure.

## Scope Completed in Phase 1

- `/db` hierarchy is established and documented.
- Domain purpose is defined for each folder.
- Migration ownership conventions are documented.
- Runtime path switch intentionally deferred to Phase 2.

## Current State

- Alembic runtime config points to `/db` with revisions in `db/migrations`.
- Legacy files in `backend/alembic/versions` have been removed.
- Head lineage is unified via merge revision `5517dcbf0494`.

## Phase 2 Safe Cutover Checklist

Use this exact order:

1. **Freeze migration generation**
   - Pause creation of new revisions during cutover PR.

2. **Validate revision parity**
   - Ensure both trees contain the same revision files and `down_revision` chain.
   - Confirm no duplicate `revision` IDs.

3. **Switch Alembic script path**
   - Update `backend/alembic.ini`:
     - `script_location = db`
     - `directory = db`
   - Keep `sqlalchemy.url` unchanged.

4. **Add/adjust environment loader**
   - Ensure `db/env.py` imports app metadata correctly (equivalent to current `backend/alembic/env.py`).

5. **Smoke test Alembic commands**
   - `alembic -c backend/alembic.ini current`
   - `alembic -c backend/alembic.ini heads`
   - `alembic -c backend/alembic.ini history`
   - `alembic -c backend/alembic.ini upgrade head` (against dev DB)

6. **Remove legacy migration tree**
   - Only after successful smoke tests and CI, remove stale files from `backend/alembic/versions`.

7. **CI guardrail**
   - Add a CI check that fails if revision files exist outside `db/migrations` after cutover.

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
