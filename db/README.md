# Database Directory Structure

This directory is the canonical home for SQL and PostgreSQL artifacts.

## Folder Layout

- `migrations/` — Alembic revision scripts (ordered, timestamp/sequence named)
- `schema/` — base DDL grouped by domain (`users`, `league`, `draft`, etc.)
- `seeds/` — seed SQL for dev/UAT bootstrapping
- `functions/` — SQL functions and stored procedures
- `views/` — regular and materialized views
- `triggers/` — trigger definitions and trigger helper functions
- `extensions/` — Postgres extension install SQL (`pgcrypto`, `uuid-ossp`, etc.)
- `utils/` — shared SQL snippets, enums, and helpers

## Naming Standard

- Use `snake_case` for all SQL and migration files.
- Prefix files by domain and intent when possible (e.g., `users.create.sql`, `teams.seed.sql`).
- Keep migration numbering/order deterministic.

## Current Phase (Issue #60)

This repository is currently in **Phase 2 complete (Alembic cutover + legacy cleanup)**.

- Alembic now resolves script/env from `/db` and revisions from `db/migrations`.
- Legacy revision files under `backend/alembic/versions` have been retired.
- A merge revision unifies migration heads for deterministic lineage.

For implementation history and safety notes, see `docs/DB_MIGRATION_PHASE1.md`.
