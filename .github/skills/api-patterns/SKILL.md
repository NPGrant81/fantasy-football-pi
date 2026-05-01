---
name: api-patterns
description: 'FastAPI router/service/schema patterns, DTO design, endpoint conventions, Pydantic validation, response shapes, and HTTP error handling for Fantasy Football PI. Use when: creating new endpoints, writing service functions, defining request/response schemas, handling HTTP errors, or reviewing API design.'
argument-hint: 'Optional: focus area (router | service | schema | error | response-shape)'
---

# API Patterns

## Why This Exists
Consistent API structure prevents logic from leaking into routes, ensures all inputs are validated, and makes endpoints testable in isolation. Every new feature must follow this pattern — no exceptions.

## The Three-Layer Pattern

```
Router (thin)          →   Service (logic)        →   Model/DB (data)
backend/routers/       →   backend/services/      →   backend/models.py
Validates input           Domain calculations        SQLAlchemy queries
Returns Pydantic schema   Returns dicts/objects      Returns ORM rows
```

### Router responsibility (only these things):
1. Declare the route + HTTP method
2. Validate path/query params via FastAPI `Query()` / `Path()`
3. Get DB session via `Depends(get_db)`
4. Call service function
5. Return Pydantic-typed response

### Service responsibility:
- All business logic, calculations, aggregations
- Database queries via SQLAlchemy
- Raising `HTTPException` for domain-level errors

## DTO / Schema Design
Pydantic schemas in `backend/schemas/` are the DTOs. Two types:

**Request DTO** (validates incoming body):
```python
class CreateWaiverClaimIn(BaseModel):
    model_config = ConfigDict(extra="ignore")   # ignore unknown fields
    player_id: int = Field(ge=1)
    bid_amount: int = Field(ge=0, le=1000)
    drop_player_id: int | None = None
```

**Response DTO** (defines output shape):
```python
class WaiverClaimOut(BaseModel):
    id: int
    player_id: int
    bid_amount: int
    status: str
    created_at: str
```

## Standard Analytics Response Shape
All analytics endpoints return this structure (enforced by `_analytics_meta()`):
```json
{
  "rows": [...],
  "meta": {
    "metric": "luck_index",
    "league_id": 1,
    "season": 2025,
    "computed_at": "2025-05-01T12:00:00Z"
  }
}
```
Use the `_analytics_meta(db, metric, league_id, season)` helper — do not build meta manually.

## Endpoint Naming Conventions
| Action | Method | Pattern |
|--------|--------|---------|
| Get list | GET | `/league/{id}/resource` |
| Get single | GET | `/league/{id}/resource/{res_id}` |
| Create | POST | `/league/{id}/resource` |
| Update | PATCH | `/league/{id}/resource/{res_id}` |
| Delete | DELETE | `/league/{id}/resource/{res_id}` |
| Analytics | GET | `/analytics/league/{id}/{metric}` |

## HTTP Error Handling
```python
# Correct — raise HTTPException from the service or router
from fastapi import HTTPException

if not league:
    raise HTTPException(status_code=404, detail="League not found")

if not user.is_commissioner:
    raise HTTPException(status_code=403, detail="Commissioner access required")
```

Never return `{"error": "..."}` — always raise `HTTPException` with appropriate status codes.

## Always Do
- Validate ALL inputs with Pydantic or FastAPI `Query()`/`Path()` — no bare `request.json()`
- Use `Depends(get_db)` for every route that needs a database session
- Put `model_config = ConfigDict(extra="ignore")` on request DTOs to safely ignore unknown fields
- Add `ge=1` constraints on ID fields, `ge=0` on numeric amounts
- Use `_resolved_season(season)` helper for season default logic (analytics routes)
- Include `description=` in `Query()` for self-documenting OpenAPI

## Never Do
- Never put loops, calculations, or aggregations inside a route handler
- Never call `db.query()` inside a route — put it in a service
- Never return SQLAlchemy model objects directly — serialize via Pydantic or dict
- Never swallow exceptions silently — always let `HTTPException` propagate
- Never create new endpoints without explicit request (API surface is tightly controlled)
- Never bypass `Depends(get_db)` for database access in routes

## Common Patterns

### Season default helper
```python
def _resolved_season(season: int | None) -> int:
    return season if season else datetime.now().year
```

### Commissioner guard
```python
def require_commissioner(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_commissioner:
        raise HTTPException(status_code=403, detail="Commissioner access required")
    return current_user
```

### Pagination
```python
@router.get('/league/{league_id}/resource')
def list_resource(
    league_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    ...
```

## Common Problems & Remediation

| Problem | Fix |
|---------|-----|
| `422 Unprocessable Entity` | Missing required field or wrong type in request body |
| `500 Internal Server Error` in analytics | Check `_resolved_season()` and `hist_%` exclusion |
| Slow endpoint | Move DB query to service; check for N+1 (use `.joinedload()`) |
| Test fails with `None` response | Mock is not returning `.data` correctly — check `vi.mock` setup |

## Related Skills
- [Architecture](../architecture/SKILL.md) — where each layer lives
- [Database](../database/SKILL.md) — ORM query patterns
- [Security](../security/SKILL.md) — auth/RBAC middleware
- [Testing](../testing/SKILL.md) — how to test routes and services
- [ML Ops](../ml-ops/SKILL.md) — analytics endpoint conventions
