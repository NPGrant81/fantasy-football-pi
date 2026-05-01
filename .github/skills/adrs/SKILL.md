---
name: adrs
description: 'Architecture Decision Records (ADRs) — how to find, write, and interpret architectural decisions for Fantasy Football PI. Use when: making a significant technology or design choice, understanding why a past decision was made, creating a new ADR, or evaluating alternatives to current approaches.'
argument-hint: 'Optional: specific decision topic to look up or create'
---

# Architecture Decision Records (ADRs)

## Why This Exists
ADRs capture the "why" behind significant technical choices. Without them, teams repeat the same debates (React vs Vue, Redux vs Context, ORM vs raw SQL) and can't evaluate whether past constraints still apply. This project's ADRs are in `docs/` and inline in `COPILOT_INSTRUCTIONS.md`.

## What Qualifies as an ADR
Write an ADR when:
- Choosing a framework, library, or tool (and it would affect the whole project)
- Deciding on a data architecture pattern (schema design, indexing strategy)
- Making a cross-layer decision (how frontend and backend share types)
- Reversing or changing a significant previous decision
- Choosing NOT to adopt a commonly suggested pattern (e.g., "why not Redux")

Don't write an ADR for:
- Implementation details within a single component
- Stylistic choices already covered by linting rules
- One-off scripts or tooling

## ADR Format

```markdown
# ADR-NNN: [Short Title]

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-NNN]

## Date
YYYY-MM-DD

## Context
What is the situation driving this decision? What constraints exist?
What options were considered?

## Decision
What was decided, and why? Reference concrete factors.

## Consequences
What becomes easier? What becomes harder? What technical debt is accepted?

## Related Decisions
- ADR-XXX: [Related decision]
```

## Existing Key Decisions

### Frontend Framework
- **Decision**: React 18 + Vite over Next.js
- **Rationale**: No SSR needed (private league app, requires auth); Vite is significantly faster for dev; React ecosystem familiarity
- **Consequence**: No server-side rendering; all routing is client-side (React Router)

### State Management
- **Decision**: React Context only — no Redux, Zustand, Jotai, or similar
- **Rationale**: App state is modest (league selection, theme, auth token); global stores add complexity without benefit at current scale
- **Consequence**: Complex async state requires React Query patterns; if features grow significantly, revisit

### Data Access
- **Decision**: SQLAlchemy ORM exclusively — no raw SQL in application code
- **Rationale**: ORM prevents SQL injection, enforces schema consistency, enables Alembic migrations, simplifies testing with in-memory SQLite
- **Consequence**: Complex analytics queries are verbose; occasionally use `.text()` in Alembic migration scripts only

### DTO Pattern
- **Decision**: Pydantic schemas in `backend/schemas/` serve as informal DTOs
- **Rationale**: Pydantic already validates inputs/outputs; a separate mapper layer adds no value at current scale
- **Consequence**: Frontend must not rely on SQLAlchemy model field names — only Pydantic schema fields

### CSS/Styling
- **Decision**: Tailwind CSS with light-first convention; no CSS files for components
- **Rationale**: Tailwind eliminates CSS naming conflicts; light-first prevents dark-mode regressions found in early development
- **Consequence**: Component styles are verbose inline classes; must consistently pair light+dark tokens

### Database
- **Decision**: PostgreSQL (not SQLite) in production; SQLite only in tests
- **Rationale**: Multi-season data requires JSON columns, complex queries, and full-text search capabilities unavailable in SQLite
- **Consequence**: Dev environment requires Docker for database

### Historical Users
- **Decision**: Historical MFL users stored as `User` rows with `hist_%` username pattern, never excluded at data import
- **Rationale**: Preserves full historical transaction and matchup history; allows cross-season analytics
- **Consequence**: Every current-season member-list query MUST explicitly filter `~User.username.like("hist_%")`

### Deployment
- **Decision**: Raspberry Pi 4 + Cloudflare Tunnel over VPS/cloud hosting
- **Rationale**: Zero hosting cost; Pi handles the traffic of a private league; Cloudflare provides TLS without port forwarding
- **Consequence**: Constrained RAM (4GB); build steps for frontend are slow on Pi hardware; must build on dev and push `dist/`

### Analytics Response Shape
- **Decision**: Standardized `{rows, meta}` envelope for all analytics endpoints
- **Rationale**: Consistent frontend consumption pattern; enables caching by `meta.computed_at`; simplifies test assertions
- **Consequence**: Simple single-value responses still use the envelope (minor overhead acceptable for consistency)

## Where ADRs Live
1. **This skill** — summary of key decisions (above)
2. **`docs/ARCHITECTURE.md`** — more detailed architecture notes
3. **`COPILOT_INSTRUCTIONS.md`** — enforced rules derived from decisions
4. **PR descriptions** — inline decisions for smaller choices
5. **`docs/` folder** — topic-specific runbooks reference the decisions they implement

## Writing a New ADR

1. Create `docs/ADR-NNN-short-title.md` using the format above
2. Reference it from `COPILOT_INSTRUCTIONS.md` if it produces an always-enforce rule
3. Link from this skill's "Existing Key Decisions" section
4. Tag the PR with label `decision-record`

## Always Do
- Write an ADR before implementing a significant architectural change
- Reference the ADR number in the PR body
- Update ADR status to "Deprecated" or "Superseded" when a decision changes
- Include "Consequences" section — good and bad trade-offs, not just justification

## Never Do
- Never override an accepted ADR without writing a superseding one
- Never document implementation details in ADRs — save those for code comments
- Never leave an ADR in "Proposed" status without a resolution timeline

## Related Skills
- [Architecture](../architecture/SKILL.md) — current architectural state
- [Git Workflow](../git-workflow/SKILL.md) — PR process for ADR submission
- [Maintenance](../maintenance/SKILL.md) — reviewing ADRs during dependency updates
- [Existing Decisions Reference](./references/existing-decisions.md)
