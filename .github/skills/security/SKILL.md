---
name: security
description: 'Authentication, authorization, RBAC (commissioner/owner/superuser roles), JWT, OWASP Top 10 compliance, input validation, and security patterns for Fantasy Football PI. Use when: implementing auth, adding protected routes, handling commissioner-only features, validating inputs, reviewing security, or asking about RBAC.'
argument-hint: 'Optional: focus area (auth | rbac | owasp | input-validation | historical-user)'
---

# Security

## Why This Exists
Fantasy Football PI handles real league data including waiver claims, trade proposals, and commissioner actions. Unauthorized access to commissioner routes or cross-league data leakage would compromise league integrity. Security must be explicit, not assumed.

## Role Hierarchy

```
Superuser (admin)
  └── Commissioner (per-league)
        └── Owner (per-league member)
              └── Public (read-only, unauthenticated)
```

| Role | Can Do |
|------|--------|
| Public | View public league standings, player stats |
| Owner | View own team, submit lineups, place waiver claims, propose trades |
| Commissioner | All owner actions + manage settings, approve/reject trades, manage roster locks |
| Superuser | System admin, multi-league management, platform tools |

## Auth Pattern (JWT)
- JWT tokens issued at login via `POST /auth/token`
- Token injected via `Authorization: Bearer <token>` header
- Backend extracts current user via `Depends(get_current_user)`
- Session expiry enforced; idle timeout on frontend via `useIdleTimer`

### Route protection examples
```python
# Owner-required route
@router.get('/my-team')
def get_my_team(current_user: models.User = Depends(get_current_user), ...):
    ...

# Commissioner-required route
@router.patch('/settings')
def update_settings(
    current_user: models.User = Depends(get_current_user),
    ...
):
    if not current_user.is_commissioner:
        raise HTTPException(status_code=403, detail="Commissioner access required")
    ...

# Superuser-required route
@router.post('/platform/clear-data')
def clear_data(current_user: models.User = Depends(get_current_user), ...):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    ...
```

## Historical User Exclusion (Security + Data Integrity)
Historical MFL import users match `hist_YYYY_XXXX`. They must never:
- Appear in current-season member lists
- Be able to authenticate or act
- Receive waiver budgets or trade eligibility

**Enforce on every member-list query:**
```python
~models.User.username.like("hist_%")
```

This is both a data integrity and security rule.

## OWASP Top 10 Compliance

| Risk | Mitigation in this project |
|------|---------------------------|
| A01 Broken Access Control | `Depends(get_current_user)` + explicit `is_commissioner` / `is_superuser` checks |
| A02 Cryptographic Failures | JWT with strong secret (`SECRET_KEY` env var), HTTPS via Cloudflare |
| A03 Injection | SQLAlchemy ORM — no raw SQL ever; Pydantic validates all inputs |
| A04 Insecure Design | Service layer isolates business logic; schema-validated DTOs |
| A05 Security Misconfiguration | `.env` not committed; secrets via environment variables |
| A06 Vulnerable Components | `requirements-lock.txt` pins versions; regular dependency audits |
| A07 Auth Failures | JWT expiry enforced; idle timer on frontend; no password in URL |
| A08 Software & Data Integrity | `requirements-lock.txt`; `.pre-commit-config.yaml` hooks |
| A09 Logging Failures | `logging.getLogger('fantasy')` for audit trail; avoid logging PII |
| A10 SSRF | No user-controlled URL fetching; API keys are server-side only |

## Input Validation Rules
- **All** path/query parameters must use FastAPI's `Query()` or `Path()` with constraints
- **All** request bodies must use Pydantic with `ConfigDict(extra="ignore")`
- Integer IDs must have `ge=1`; amounts must have `ge=0`
- String fields must have `max_length` constraints
- Never interpolate user input into file paths or command strings

```python
# Correct
player_id: int = Field(ge=1)
bid_amount: int = Field(ge=0, le=10000)
team_name: str = Field(min_length=1, max_length=64)

# Wrong — no constraints
player_id: int
bid_amount: int
```

## Cross-League Data Isolation
Every query involving user data MUST filter by `league_id`:
```python
db.query(models.Matchup).filter(
    models.Matchup.league_id == league_id,   # ← ALWAYS
    models.Matchup.week == week,
).all()
```

Failing to include `league_id` in queries can expose other leagues' data.

## Secret Management
| Secret | Location |
|--------|----------|
| `DATABASE_URL` | `.env` (never committed) |
| `SECRET_KEY` | `.env` — use 32+ char random string |
| `MFL_API_KEY` | `.env` |
| `ESPN_S2`, `ESPN_SWID` | `.env` — ESPN session cookies |
| Cloudflare Tunnel token | Systemd service unit or `.env` |

**Never:**
- Log secrets or tokens
- Commit `.env`
- Return full JWT in response body (return in `access_token` field only)
- Store passwords in plaintext

## Always Do
- Always check role before any mutation operation (POST/PATCH/DELETE)
- Always include `league_id` filter on data queries
- Always use `Depends(get_current_user)` — never trust client-supplied `user_id`
- Always validate numeric bounds on all user inputs
- Always use `logging.getLogger('fantasy')` for security-relevant events (login, role escalation)

## Never Do
- Never trust `is_commissioner` from the request body — always read from DB
- Never expose stack traces in API error responses (use generic messages in prod)
- Never allow commissioner actions without a fresh DB lookup of the user's role
- Never store sensitive data in browser localStorage (use httpOnly cookies or memory)
- Never bypass `Depends(get_current_user)` in route handlers

## Related Skills
- [API Patterns](../api-patterns/SKILL.md) — where auth guards are placed
- [Architecture](../architecture/SKILL.md) — service layer as security boundary
- [Database](../database/SKILL.md) — historical user exclusion
- [Git Workflow](../git-workflow/SKILL.md) — secret scanning in pre-commit hooks
