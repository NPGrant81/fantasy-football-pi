---
name: architecture
description: 'Fantasy Football PI system architecture, layer separation, service pattern, DTO design (Pydantic schemas as DTOs), data flow, cross-layer naming conventions, and design principles. Use when: designing new features, deciding where code goes, understanding layer boundaries, asking about DTOs, or reviewing system design.'
argument-hint: 'Optional: focus area (layers | dto | data-flow | naming | patterns)'
---

# Architecture

## Why This Exists
Fantasy Football PI is a full-stack app where **backend business logic must never leak into route handlers or the frontend**. This skill documents the exact layer boundaries, naming contracts, and design patterns that keep the system maintainable as it grows.

## Are We Using DTOs?
**Yes — informally via Pydantic.** `backend/schemas/` models serve as DTOs (Data Transfer Objects):
- **Request DTOs**: Pydantic `BaseModel` classes validate and deserialize incoming request bodies
- **Response DTOs**: Pydantic models define the exact shape of every endpoint's response
- There is no separate DTO layer by name — `schemas/` IS the DTO layer

The pattern intentionally avoids a separate mapping step. SQLAlchemy models are internal; Pydantic schemas are the public contract.

## Layer Map

```
┌──────────────────────────────────────┐
│  Browser (React 18 / Vite)           │  ← UI only, no business logic
│  frontend/src/pages/ + components/   │
│  State: React Context only           │
└─────────────┬────────────────────────┘
              │ HTTP (JSON)
              ▼
┌──────────────────────────────────────┐
│  API Layer (FastAPI)                 │  ← Thin: validate input, call service, return schema
│  backend/routers/*.py                │
│  DTOs: backend/schemas/*.py (Pydantic│
└─────────────┬────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│  Service Layer                       │  ← All domain/business logic lives here
│  backend/services/*.py               │
│  backend/utils/*.py  (helpers)       │
└─────────────┬────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│  ORM Layer (SQLAlchemy)              │  ← Data access only, no logic
│  backend/models.py                   │
│  backend/database.py                 │
└─────────────┬────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│  PostgreSQL                          │
└──────────────────────────────────────┘
```

## Data Flow (Read example)

1. Browser calls `GET /analytics/league/1/luck-index`
2. Router `analytics.py` validates query params via FastAPI's `Query()`
3. Router calls service function (or computes inline for analytics — acceptable for read-only analytics)
4. Service queries `models.Matchup` via SQLAlchemy session
5. Router returns Pydantic-typed response `{"rows": [...], "meta": {...}}`
6. Frontend `analyticsApi.js` → `getJson()` → component state → render

## File Placement Rules

| What | Where |
|------|-------|
| Route handler | `backend/routers/<domain>.py` |
| Business logic | `backend/services/<domain>_service.py` |
| Shared helpers | `backend/utils/<topic>.py` |
| Request/Response shapes | `backend/schemas/<domain>.py` |
| DB models | `backend/models.py` (or `backend/models/<domain>.py`) |
| Pages/views | `frontend/src/pages/<domain>/` |
| Reusable components | `frontend/src/components/` |
| API calls | `frontend/src/api/<domain>Api.js` |
| Shared types | `frontend/src/types/` |
| Context/state | `frontend/src/context/` |

## Naming Contracts (cross-layer consistency)
These terms must be spelled identically in both backend and frontend:

| Entity | Backend key | Frontend key |
|--------|-------------|--------------|
| League | `league_id` | `leagueId` |
| Owner | `owner_id` | `ownerId` |
| Season | `season` | `season` |
| Week | `week` | `week` |
| Fantasy points | `fantasy_points` | `fantasyPoints` |
| Player | `player_id` | `playerId` |

## Always Do
- Route handlers are thin: parse request → call service → return schema
- All domain logic goes in `services/`; shared utilities go in `utils/`
- Use Pydantic schemas for ALL endpoint request/response typing
- Prefix analytics response objects with `rows` + `meta` (see `_analytics_meta()` helper)
- Keep frontend API calls inside `frontend/src/api/` files; never `fetch()` in components directly
- Use React Context for shared state; no Redux, Zustand, or other stores

## Never Do
- Never put domain logic in a route handler
- Never write raw SQL — SQLAlchemy ORM only
- Never bypass `frontend/src/api/client.js` for HTTP calls
- Never introduce new state management libraries (Redux, Zustand, Jotai, etc.)
- Never create new database relationships without a corresponding Alembic migration
- Never expose SQLAlchemy model objects directly from endpoints — always serialize via Pydantic

## Common Anti-Patterns to Reject

| Anti-pattern | Correct approach |
|--------------|-----------------|
| 50-line route handler with loops and calculations | Move logic to `services/` |
| `db.execute(text("SELECT ..."))` | Use ORM query: `db.query(Model).filter(...)` |
| `axios.get('/api/...')` in a React component | `import { fetchX } from '@api/xApi'` |
| Redux store for async data | React Query / React Context |
| `models.User` dict in API response | Pydantic schema with only exposed fields |

## Related Skills
- [API Patterns](../api-patterns/SKILL.md) — router/service/schema implementation detail
- [Database](../database/SKILL.md) — ORM, migrations, schema design
- [UI/UX](../ui-ux/SKILL.md) — frontend layer conventions
- [Security](../security/SKILL.md) — auth layer placement
- [Layer Map Reference](./references/layer-map.md)
