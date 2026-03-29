# Pattern Standardization Plan

Updated: 2026-03-29
Owner: engineering
Tracking issue: #334

## Objective

Create a repeatable, testable process to detect content/code that violates
pattern expectations and converge the repository to the defined standards in
`docs/PATTERN_LIBRARY.md`.

## Current baseline snapshot (2026-03-29)

- `python -m scripts.repo_hygiene_check`: passed
- `python -m scripts.docs_review_sweep --warn-days 14`: passed
- Docs governance registry coverage:
  - total markdown docs under `docs/` (excluding `INDEX.md`): 82
  - governed docs in `docs/governance/doc_review_registry.json`: 19
  - coverage: 23.2%

Interpretation:
- Current standards checks are healthy for scoped, governed content.
- Main gap is coverage breadth: many docs are not yet in active review cadence,
  so drift can exist without being detected automatically.

## What counts as non-compliant content

- Code paths implementing cross-cutting behavior without the canonical helper or contract.
- Duplicate inline logic that an active pattern explicitly centralizes.
- Pattern docs/governance artifacts missing when introducing new cross-cutting behavior.
- PRs that modify cross-cutting behavior without explicit pattern impact declaration.

## Regression testing strategy

### 1. Automated policy checks (required)

- Use `python -m scripts.repo_hygiene_check` as baseline enforcement.
- Pattern-compliance checks fail when a scoped anti-pattern is detected.
- Current Stage 1 automated scope:
  - commissioner deadline helper usage in trade + waiver enforcement targets
  - ban inline `datetime.fromisoformat(...)` parsing in those targets
  - ensure pattern docs workspace files exist

### 2. Behavior regression tests (required)

- Keep helper-level behavior matrix tests for pattern-critical contracts:
  - no deadline
  - future deadline
  - past deadline
  - invalid format fallback/log path
- Add endpoint/service regression tests when a pattern is migrated into those paths.

### 3. Review gates (required)

- PR template must include pattern impact declaration for cross-cutting changes.
- Review checklist must verify pattern linkage and governance updates.

## Rollout phases

### Phase 1 - Baseline in place (completed)

- Canonical pattern library established.
- Pattern proposal and decision log created.
- Shared commissioner deadline helper introduced.
- Initial automated compliance checks enabled in repo hygiene script.

### Phase 2 - Inventory and coverage expansion

- Build inventory of active cross-cutting patterns and current implementations.
- Add scoped regression checks for top-priority patterns:
  - validation layering (boundary/dynamic/domain order)
  - router-service separation on targeted modules
  - error contract consistency for rule-lock failures
- Add missing tests per pattern matrix.
- Expand governed doc coverage from 23.2% to at least 60% for operational docs.

### Phase 3 - Enforced conformance

- Expand pattern checks from scoped modules to broader directories.
- Fail CI on confirmed pattern violations.
- Track remediation progress through issue-linked backlog items.

## Criticality model for non-compliant content

Use this rubric to decide fix urgency.

### Critical (fix immediately)

- Security/auth/runbook docs that could cause unsafe operation.
- API contract docs that can cause breaking implementation divergence.
- Rule-enforcement patterns affecting gameplay correctness (trade/waiver/keeper locks).

SLO: patch in current sprint (or hotfix if production-impacting).

### High (fix in next sprint)

- Deployment/ops/reliability docs used during active support.
- Data-quality and migration runbooks used by ETL/import workflows.
- Pattern contract violations in modules with frequent changes.

SLO: resolve in next planned sprint.

### Medium (batch remediation)

- Workflow docs used by contributors but with low production blast radius.
- Historical status or planning docs with minor drift.

SLO: monthly hygiene cycle.

### Low (defer or archive)

- Archive material and historical notes not used for current execution.
- Informational docs with no operational dependency.

SLO: quarterly cleanup cycle.

## How to decide if a page "meets standard"

A page meets standard when all are true:

1. It is either governed (in registry) or explicitly archived/deprecated.
2. It has a clear canonical role (not conflicting with another active doc).
3. Its linked issue/epic mapping is current where applicable.
4. Its content matches current implementation behavior.
5. It passes any automated checks scoped to its domain.

### Phase 4 - Continuous governance

- Monthly review of pattern check false positives/false negatives.
- Quarterly refresh of `docs/PATTERN_LIBRARY.md` and decision log.
- Keep correlation map and review registry synchronized with pattern changes.

## Prioritized remediation backlog template

For each non-compliant item:

1. Pattern name
2. Violating file/module
3. Violation type
4. Risk level
5. Owner
6. Target sprint/milestone
7. Verification test/check

## Definition of done

- Pattern gates are runnable locally and in CI with actionable output.
- High-priority cross-cutting patterns have explicit automated checks.
- Pattern-critical behavior has regression tests aligned to pattern matrix.
- New cross-cutting changes consistently include pattern impact + issue traceability.
