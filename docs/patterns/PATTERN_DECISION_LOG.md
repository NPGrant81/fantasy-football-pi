# Pattern Decision Log

Track accepted, superseded, and deprecated pattern decisions.

## Entries

### 2026-03-29 - Adopt shared commissioner deadline helper

- Status: accepted
- Decision: enforce trade and waiver commissioner deadlines through shared helper logic in `backend/services/commissioner_deadline_service.py`.
- Context: duplicated parse/compare blocks in trade and waiver paths caused pattern drift risk.
- Consequences:
  - trade and waiver deadline checks now use one enforcement contract.
  - invalid deadline values continue fail-open behavior, but now emit warning logs for observability.
  - helper-level tests define baseline behavior matrix (none/future/past/invalid).
- Related issues/PRs: #333, #307

### 2026-03-29 - Establish canonical pattern repository

- Status: accepted
- Decision: `docs/PATTERN_LIBRARY.md` is the canonical source for active cross-cutting implementation patterns.
- Context: repeated logic and policy drift (notably commissioner rule propagation and deadline enforcement) needed a single contract source.
- Consequences:
  - PRs should link to a pattern in `docs/PATTERN_LIBRARY.md` when introducing or changing cross-cutting behavior.
  - New cross-cutting contracts should be proposed through `docs/patterns/PATTERN_PROPOSAL_TEMPLATE.md` before broad rollout.
  - Governance review now includes pattern-related docs.
- Related issues/PRs: #307, #156
