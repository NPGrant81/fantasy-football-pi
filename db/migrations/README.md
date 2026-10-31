# Migrations Directory

This folder stores Alembic migration revisions only.

## Rules

- Keep only revision scripts in this folder.
- Do not place base schema SQL, seeds, or utility SQL here.
- Preserve file ordering and dependencies (`revision`, `down_revision`).

## Canonical Authority

This is the only directory for active incremental Alembic revisions. The Alembic
configuration remains at `backend/alembic.ini`, with its environment in `db/env.py`.
Run migrations from the repository root with `python -m backend.apply_migrations`.

The immutable empty-database bootstrap lineage lives separately in `db/bootstrap/`.
See `docs/MIGRATION_LEGACY_INVENTORY.md` for the retired legacy lineage and recovery
guidance for databases that still report a legacy revision.
