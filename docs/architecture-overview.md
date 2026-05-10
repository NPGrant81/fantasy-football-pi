# Architecture Overview (Issue #113)

## Purpose

This page is the quick-start architecture map for contributors and reviewers.
It points to canonical architecture references and defines where major concerns
belong in this repository.

For detailed architecture, use:

- `docs/ARCHITECTURE.md`
- `docs/architecture/overview.md`
- `docs/API_PAGE_MATRIX.md`

## System Layers

1. Frontend (`frontend/`)
- React + Vite single-page app.
- Page-level orchestration in `src/pages/`.
- Shared API client and request wrappers in `src/api/`.

2. Backend API (`backend/`)
- FastAPI routers in `backend/routers/`.
- Business logic in `backend/services/`.
- Shared auth/config/dependencies in `backend/core/`.

3. Data and ETL (`etl/`, `db/`)
- Data extraction/transform/load in `etl/`.
- Schema, migrations, database objects in `db/` and `backend/alembic/`.

4. Ops and Deployment (`deploy/`, workflows)
- Systemd/nginx/cloudflared runtime artifacts in `deploy/`.
- CI/CD and validation gates in `.github/workflows/`.

## Contract Boundaries

- Frontend should consume backend APIs through shared client wrappers, not
  hardcoded host/path strings.
- Routers should delegate business rules to service functions.
- ETL feature contracts must be versioned and documented before model promotion.
- Commissioner settings are authoritative for league-specific simulation limits.

## Quality Gate Alignment

All cross-layer changes should include:

- tests in affected layers (backend pytest, frontend vitest, Cypress when UX flow changes)
- API/documentation updates in `docs/API_PAGE_MATRIX.md` when request/response
  behavior changes
- issue and status updates in `docs/ISSUE_STATUS.md` for traceability

## Decision Records and Standards

When a change affects architecture-level behavior, update at least one:

- `docs/PATTERN_LIBRARY.md` for reusable implementation patterns
- `docs/PATTERN_DECISION_LOG.md` for important design decisions
- `docs/DOC_ISSUE_CORRELATION_MAP.md` to keep doc-to-issue traceability intact
