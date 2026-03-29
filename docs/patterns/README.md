# Patterns Workspace

This folder supports the canonical pattern repository at `docs/PATTERN_LIBRARY.md`.

## Purpose

- Keep active reusable contracts in `docs/PATTERN_LIBRARY.md`.
- Capture proposed new patterns in `PATTERN_PROPOSAL_TEMPLATE.md`.
- Record accepted/superseded pattern decisions in `PATTERN_DECISION_LOG.md`.

## Workflow

1. Draft a proposal using `PATTERN_PROPOSAL_TEMPLATE.md`.
2. Review proposal in issue/PR discussion.
3. If accepted:
   - update `docs/PATTERN_LIBRARY.md`
   - append a decision record in `PATTERN_DECISION_LOG.md`
   - link issue/PR in `docs/DOC_ISSUE_CORRELATION_MAP.md` when relevant
4. Update governance review metadata for any canonical docs changed.

## Status conventions

- `proposed`: discussed but not approved.
- `accepted`: approved and active.
- `superseded`: replaced by a newer pattern.
- `deprecated`: scheduled for retirement.
