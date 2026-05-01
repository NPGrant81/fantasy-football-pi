# Existing Architecture Decisions — Fantasy Football PI

This document records the key architectural decisions made for this project. For the ADR format and authoring guide, see [adrs/SKILL.md](../SKILL.md).

---

## ADR-001: React 18 + Vite over Next.js

**Status**: Accepted  
**Date**: 2024 (initial project setup)

**Context**: Fantasy Football PI is a private-league dashboard requiring authentication for all views. Multiple frameworks were considered: Next.js (SSR/SSG), plain Create React App, Vite+React.

**Decision**: Use React 18 with Vite as the build tool.

**Rationale**:
- No SEO or SSR requirements — all views are behind auth
- Vite HMR is substantially faster than webpack-based CRA
- Smaller config surface than Next.js for this use case
- No server functions needed — FastAPI handles all server-side logic

**Consequences**:
- All routing is client-side (React Router); 404s must be handled by Nginx try_files directive
- No ISR, no image optimization from Next.js
- Faster dev iteration; ~33s production build

---

## ADR-002: SQLAlchemy ORM Only (No Raw SQL in Application Code)

**Status**: Accepted  
**Date**: 2024 (initial project setup)

**Context**: Application needs to query PostgreSQL across ~15 tables with complex joins for analytics.

**Decision**: All data access in `backend/` uses SQLAlchemy ORM models. Raw SQL is only permitted in Alembic migration scripts and in `db/` SQL files (schema, seeds).

**Rationale**:
- ORM prevents SQL injection at the parameterization layer
- Alembic migrations generated from ORM models are the canonical schema source
- SQLite can substitute for PostgreSQL in tests (with ORM, type differences are abstracted)
- Team skills are centered on ORM patterns

**Consequences**:
- Complex analytics aggregations are more verbose than raw SQL
- `select()` with `.label()` and `.func` used for computed columns
- Occasional `text()` used in Alembic-only migration scripts is acceptable

---

## ADR-003: React Context Only (No Redux/Zustand)

**Status**: Accepted  
**Date**: 2024

**Context**: Frontend needs to share: current league selection, authenticated user, and theme preference across many components.

**Decision**: React Context API is the only global state mechanism. No Redux, Zustand, Jotai, or similar.

**Rationale**:
- App has limited cross-component state (auth, league ID, theme)
- React Query manages all server state (caching, loading, invalidation)
- Redux adds significant complexity for modest benefit at this scale
- Fewer dependencies = less maintenance surface

**Consequences**:
- Complex derived state (e.g., aggregated cross-season stats) must be computed in hooks or services
- If app grows to many async state slices, may warrant revisiting Zustand
- Context re-renders are acceptable given component tree size

---

## ADR-004: Pydantic Schemas as DTOs (No Separate Mapper Layer)

**Status**: Accepted  
**Date**: 2024

**Context**: FastAPI requires Pydantic models for request/response validation. Some architectures add a separate DTO/mapper class between ORM models and Pydantic.

**Decision**: `backend/schemas/` Pydantic models ARE the DTOs. No separate mapper layer.

**Rationale**:
- FastAPI + Pydantic's `from_orm()` / `model_validate()` handles mapping
- A separate mapper layer adds files and maintenance without benefit at current scale
- Pydantic v2 `model_config = ConfigDict(from_attributes=True)` makes ORM→DTO trivial

**Consequences**:
- Schema names must match the intended API contract (not ORM internals)
- `backend/schemas/` is the source of truth for what the frontend may rely on
- ORM model field names must NOT be exposed directly if Pydantic schema names differ

---

## ADR-005: Tailwind CSS, Light-First Convention

**Status**: Accepted  
**Date**: 2024 (refined post early dark-mode regressions)

**Context**: Early frontend development used dark-first Tailwind, causing accessibility issues in light environments and inconsistent contrast.

**Decision**: All components default to light theme. Dark mode is applied via `dark:` modifier as progressive enhancement.

**Rationale**:
- Light theme is accessible by default; dark mode is an enhancement
- Dark-only classes regressed to light-mode failures in early versions
- `check-ui.js` audit tool was created to catch dark-only regressions

**Consequences**:
- Every background, text, border class must have both light and dark versions
- Developers must always add `dark:` counterpart alongside any light class
- `node check-ui.js` should be run before PR

---

## ADR-006: Historical MFL Users with `hist_%` Pattern

**Status**: Accepted  
**Date**: 2024

**Context**: Pre-2024 MFL leagues have historical participant data that must be preserved for analytics, but these users should not appear in current-season member lists.

**Decision**: Historical users are stored as real `User` rows with usernames matching `hist_%`. All current-member queries MUST exclude this pattern.

**Rationale**:
- Preserves full historical transaction and matchup data integrity
- Enables cross-season analytics (e.g., "all-time head-to-head record")
- Simple exclusion pattern requires only one WHERE clause

**Consequences**:
- EVERY query returning current members MUST include: `.filter(~User.username.like("hist_%"))`
- Failure to exclude causes ghost users to appear in standings/rosters
- This is both a data integrity AND security rule (access isolation)

---

## ADR-007: Raspberry Pi 4 + Cloudflare Tunnel Deployment

**Status**: Accepted  
**Date**: 2024

**Context**: Needed a way to host the app on personal hardware, accessible from anywhere, with HTTPS, at zero recurring cost.

**Decision**: Deploy on Raspberry Pi 4 (4GB RAM). Use Cloudflare Tunnel (free tier) for HTTPS and DNS routing. No cloud hosting.

**Rationale**:
- Zero monthly hosting cost
- Private league traffic is well within Pi capacity (< 20 concurrent users)
- Cloudflare Tunnel provides TLS without port forwarding or exposed IP
- Full control over data (no third-party hosting for fantasy data)

**Consequences**:
- Pi hardware constraints: must monitor disk, temp, RAM
- Frontend must be built on dev machine and pushed (building on Pi is slow)
- Cloudflare tunnel token must be rotated if compromised
- SD card failures are a risk — backup strategy required

---

## ADR-008: Alembic for Database Migrations

**Status**: Accepted  
**Date**: 2024

**Context**: Need a way to evolve database schema over time without data loss.

**Decision**: Alembic (SQLAlchemy's migration tool) is the sole migration mechanism.

**Rationale**:
- Standard SQLAlchemy tooling; no additional dependencies
- `autogenerate` creates migrations from model diffs
- Revision history provides audit trail
- Downgrade functions enable rollback

**Consequences**:
- Every schema change MUST go through `alembic revision --autogenerate`
- Never modify production schema directly (psql ALTER TABLE)
- `alembic heads` must show exactly 1 head before deploying

---

## ADR-009: Standard Analytics Response Envelope

**Status**: Accepted  
**Date**: 2025

**Context**: Multiple analytics endpoints needed a consistent response format for frontend caching and test assertions.

**Decision**: All analytics endpoints return `{"rows": [...], "meta": {...}}` using `_analytics_meta()` helper.

**Rationale**:
- Frontend can treat all analytics endpoints identically
- `meta.computed_at` enables cache validation
- Consistent structure simplifies test assertions
- `heatmap_max` and `all_weeks` are optional extra fields for specific chart types

**Consequences**:
- Single-value analytics results still use the envelope (minor verbosity acceptable)
- `_analytics_meta()` helper must be called in every analytics endpoint
- Frontend destructures `data.rows` / `data.meta` consistently
