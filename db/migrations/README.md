# Migrations Directory

This folder stores Alembic migration revisions only.

## Rules

- Keep only revision scripts in this folder.
- Do not place base schema SQL, seeds, or utility SQL here.
- Preserve file ordering and dependencies (`revision`, `down_revision`).

## Operational Note

During Issue #60 Phase 1, this folder is treated as the target migration home for organization.
Runtime path cutover for Alembic (`script_location`) is handled separately via a documented checklist to avoid production/developer breakage.

See `docs/DB_MIGRATION_PHASE1.md` for the safe cutover steps.
