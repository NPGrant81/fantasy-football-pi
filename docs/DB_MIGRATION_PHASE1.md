# DB Organization — Phase 1 (Issue #60)

## Goal

Establish a predictable PostgreSQL folder layout and complete a safe Alembic cutover to the `/db` structure.

## Scope Completed

- `/db` hierarchy is established and documented.
- Domain purpose is defined for each folder.
- Migration ownership conventions are documented.
- Alembic runtime configuration now uses the canonical `/db` migration tree.
- Runtime path switch is complete.

## Current State

- Alembic runtime config points to `/db` with revisions in `db/migrations`.
- Retired `backend/alembic/` artifacts have been removed.
- Earlier branches were unified by merge revision `5517dcbf0494`; the current
  canonical graph has the single head `0028_reconcile_runtime_schema`.
- CI scans repository-wide for Alembic revision files and permits only
  `db/migrations/` plus the governed bootstrap revision.

See `docs/MIGRATION_LEGACY_INVENTORY.md` for the disposition of the retired lineage.
Disposable PostgreSQL execution and deployed revision-history verification
remain release gates for retiring that lineage.

## Cutover Status

The Phase 2 runtime cutover is complete:

- `backend/alembic.ini` points Alembic to `db/` and `db/migrations/`.
- `db/env.py` and `db/script.py.mako` provide the Alembic environment and revision template.
- Canonical revisions are maintained in `db/migrations/`; the former
  `backend/alembic/versions/` tree is no longer the migration source.
- New migrations must be applied through the guarded project runner,
  `python -m backend.apply_migrations`, from the repository root. Do not use
  direct `alembic upgrade` commands for application or production databases.

The configured database's current revision must be verified separately against
the canonical graph before any deployment. This document does not establish
that a production database is current.

## Naming and Placement Standard

- Revisions: sequence or timestamp prefix + descriptive slug (snake_case).
- Schema SQL: `db/schema/<domain>/<entity>.create.sql` (or equivalent domain grouping).
- Seed SQL: `db/seeds/<domain>.<purpose>.sql`.
- Functions/views/triggers/extensions/utils: keep one object per file where practical.

## Definition of Done

- [x] `/db` scaffold is present and documented.
- [x] Folder purpose and naming conventions are written.
- [x] Alembic runtime cutover completed and the canonical migration location documented.

## Cutover Implementation Notes

- `backend/alembic.ini` uses `script_location = %(here)s/../db` and
  `version_locations = %(here)s/../db/migrations`.
- The canonical graph includes merge revision `5517dcbf0494` and head
  `0028_reconcile_runtime_schema`.
- Historical cutover validation included Alembic command and migration checks.
  Re-run database-specific checks against the intended target before deployment;
  never stamp a database simply to bypass a missing-revision error.
