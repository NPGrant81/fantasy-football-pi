# Milestone 5 — Gameplay Logic & League Operations

This milestone implements the core fantasy‑football mechanics.

---

## Status

- status: `in-progress`
- owner: `backend`
- source of truth for active progress: `docs/milestones/README.md` and linked child issue files under `issues/`

---

## Scope

- Roster rules and constraints (size limits, position constraints)
- Scoring engine
- Weekly matchups
- Standings and tiebreakers
- Commissioner tools
- Audit logs for gameplay actions

---

## Completion Criteria

- [ ] Full league lifecycle supported
- [ ] Scoring validated and reproducible
- [ ] All gameplay rules enforced server‑side
- [ ] UI supports roster management and matchup views

Status hygiene note:

- Keep checklist items unchecked until objective acceptance evidence is linked.

---

## Child Issues

| Issue | Title | Labels |
|-------|-------|--------|
| [Issue 15](../../issues/milestone-5-roster-rules.md) | Gameplay Logic: Roster Rules | `gameplay`, `backend` |
| [Issue 16](../../issues/milestone-5-scoring-engine.md) | Gameplay Logic: Scoring Engine | `gameplay`, `backend`, `analytics` |

---

## Dependencies

- Milestone 1 — Core Application Foundation
- Milestone 3 — Security Hardening (commissioner authorization)
- Milestone 4 — Data‑Validation Architecture (scoring validation)

---

## Notes

Related story families in [PROJECT_MANAGEMENT.md](../PROJECT_MANAGEMENT.md):

- Story 2.x: Draft system workstream
- Story 4.x: Scoring and rules management workstream
- Story 5.x: Free agents and waivers workstream
- Story 6.x: Matchups and standings workstream
