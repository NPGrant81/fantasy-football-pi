# Documentation Classification Guardrails

Updated: 2026-03-29
Owner: engineering

## Purpose

Define how markdown files are classified (domain and artifact type), and how
we detect drift early before docs become stale, orphaned, or ambiguous.

## Classification Model

Each markdown doc should map to:

1. domain: who primarily owns and consumes the content.
2. artifact type: what kind of document it is (policy, runbook, roadmap, etc.).

Primary domains used by automation:

- governance
- backend
- frontend
- platform
- security
- data
- qa
- product
- engineering
- archive

## Path-Based Routing Rules

Automation classifies docs using deterministic path rules first:

- `docs/governance/*` -> governance/policy
- `docs/patterns/*` -> governance/pattern-workspace
- `docs/archive/*` -> archive/historical
- `docs/milestones/*` -> product/roadmap
- `docs/uat/*` -> qa/uat
- `docs/diagrams/*` -> engineering/diagram
- `docs/data-migration/*` -> data/migration
- `docs/pi-setup/*` -> platform/setup
- `docs/architecture/*` -> engineering/architecture
- `docs/gaps/*` -> product/gap-analysis

Then filename heuristics apply for top-level docs.

## Warning and Failure Signals

The repo hygiene check now fails when any of these occur:

1. A markdown file exists under `docs/` but is missing from governance registry.
2. A registry entry points to a missing doc.
3. A doc path cannot be classified by current guardrail rules.
4. A registry owner is invalid.
5. A registry entry is malformed or duplicated.

This turns potential drift into immediate, actionable errors.

## What To Do When a New Doc Is Added

1. Add the file.
2. Add a registry entry in `docs/governance/doc_review_registry.json`.
3. Ensure path classification is recognized by guardrails.
4. Update `docs/INDEX.md` where appropriate.
5. Run:
   - `python -m scripts.repo_hygiene_check`
   - `python -m scripts.docs_review_sweep --warn-days 14`

## Ownership Clarification

`owner` in registry is the operational steward for review cadence.
It does not restrict who can edit a file.

## Escalation Rule

If classification is unclear, default to:

- owner: `engineering`
- cadence: 60 days

Then resolve domain ownership in the next docs governance review rather than
leaving the file ungoverned.
