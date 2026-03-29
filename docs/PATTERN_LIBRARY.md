# Pattern Library

Updated: 2026-03-29
Owner: engineering

This document is the canonical repository of cross-cutting implementation
patterns for this codebase. Use it when adding features, writing tests,
reviewing PRs, or designing refactors.

## Why this exists

- Prevent duplicate ad-hoc logic across routers/services.
- Keep behavior consistent across backend, frontend, and operations workflows.
- Make PR reviews objective with explicit contracts and acceptance checks.

## How to use this library

1. Before implementing a feature, identify the matching pattern here.
2. Reuse the existing contract and tests from that pattern.
3. If no pattern exists, create one in this file in the same PR as the feature.
4. Link PRs/issues that introduce or update patterns in `docs/DOC_ISSUE_CORRELATION_MAP.md`.

## Pattern Template

Every pattern entry should include:

- `Intent`: what problem it solves.
- `Contract`: required behavior and invariants.
- `Implementation`: where the logic should live.
- `Testing`: minimum test matrix.
- `Anti-patterns`: what to avoid.

## Active Patterns

### 1) Commissioner Deadline Enforcement

- Intent: enforce league-level time-based locks consistently (trade, waiver, keeper, and future deadlines).
- Contract:
  - Deadline source of truth is `LeagueSettings`.
  - Deadline comparison must be timezone-safe and deterministic.
  - Invalid deadline strings must follow one explicit policy (fail closed preferred; fail open only with warning logs).
  - Error message must include user-facing lock reason.
- Implementation:
  - Shared helper in backend services (do not duplicate parse/compare logic in multiple routers).
  - Routers stay thin and call the helper.
- Testing:
  - No deadline set -> allowed.
  - Future deadline -> allowed.
  - Past deadline -> blocked.
  - Invalid deadline -> behavior matches policy.
- Anti-patterns:
  - Copy/pasted `fromisoformat` blocks per endpoint.
  - Silent parse failures with no logs.

### 2) Validation Layering (Boundary + Dynamic + Domain)

- Intent: keep request validation consistent and reviewable.
- Contract:
  - Boundary validation checks shape/types/ranges.
  - Dynamic validation checks current state constraints.
  - Domain/business rules run after validation and before mutation.
- Implementation:
  - Use validation service helpers for boundary/dynamic rules.
  - Keep router handlers focused on orchestration and HTTP translation.
- Testing:
  - Separate tests for boundary failures, dynamic failures, and domain rule failures.
- Anti-patterns:
  - Mixed validation and persistence in a single large handler block.

### 3) Router-Service Separation

- Intent: preserve maintainability and testability.
- Contract:
  - Routers handle auth, request parsing, and response codes.
  - Services contain business logic and reusable workflows.
- Implementation:
  - Place reusable rule logic in `backend/services`.
  - Avoid embedding multi-step domain rules directly in router files.
- Testing:
  - Service unit tests for behavior.
  - Router tests for HTTP contract and dependency wiring.
- Anti-patterns:
  - Business rule drift where one endpoint bypasses a service-level rule.

### 4) Historical User Exclusion

- Intent: keep historical import accounts out of current-season operations.
- Contract:
  - Member-list queries must exclude usernames matching `hist_%`.
  - Exclusion applies to standings, waivers, trades, budgets, and similar views.
- Implementation:
  - Apply the exclusion predicate in all member-list ORM queries.
- Testing:
  - Include at least one query-path test proving historical users are filtered.
- Anti-patterns:
  - Hardcoded explicit username deny-lists.

### 5) Ledger-Backed Economic Mutations

- Intent: preserve auditable financial state for FAAB and future draft currency.
- Contract:
  - Mutations that move or consume economic value must create ledger entries.
  - Balances are derived from ledger history, not mutable counters alone.
- Implementation:
  - Use shared ledger service methods for recording and reading balances.
- Testing:
  - Successful mutation writes exactly one expected ledger entry.
  - Insufficient balance paths reject and avoid partial writes.
- Anti-patterns:
  - Directly mutating balances without ledger entries.

### 6) Error Contract Consistency

- Intent: make UI handling predictable and reduce support/debug effort.
- Contract:
  - Use stable HTTP status codes and detail message shape for common failure classes.
  - Rule-lock messages should be human-readable and consistent.
- Implementation:
  - Reuse shared exception helpers/messages where possible.
- Testing:
  - Assert status code and key message phrase for each rule failure path.
- Anti-patterns:
  - Same failure class returning different status codes across endpoints.

### 7) Settings Propagation Integrity

- Intent: ensure commissioner settings updates are reflected across all consuming workflows.
- Contract:
  - Every writable setting has at least one downstream consumption test.
  - Read models include all authoritative fields needed by downstream UI/services.
- Implementation:
  - Pair write-path changes with at least one read/behavior assertion.
- Testing:
  - Round-trip coverage (set -> retrieve -> behavior affected).
- Anti-patterns:
  - Write succeeds but read models silently omit fields.

### 8) Regression Test Pattern for Rule Changes

- Intent: prevent relapses after bug fixes or policy updates.
- Contract:
  - Each production rule fix includes one focused regression test tied to the issue/PR.
  - Tests name the business intent clearly.
- Implementation:
  - Add tests near existing module tests in `backend/tests` or `frontend/tests`.
- Testing:
  - Positive and negative path where applicable.
- Anti-patterns:
  - Broad integration-only tests without targeted boundary checks.

### 9) Observability for Policy Bypasses

- Intent: detect configuration and parsing issues early.
- Contract:
  - Any policy bypass (for example invalid date format fallback) emits a warning log with enough context.
- Implementation:
  - Use shared logger names and structured fields when possible.
- Testing:
  - At least one test validates warning emission for bypass path.
- Anti-patterns:
  - Silent fallback behavior in critical rule enforcement.

### 10) Documentation Sync in Code PRs

- Intent: keep docs and implementation aligned as a standard operating practice.
- Contract:
  - Domain-impacting behavior changes update relevant docs in the same PR.
  - Docs index and issue-correlation map are updated when a new canonical doc is added.
- Implementation:
  - Follow `docs/DOCUMENTATION_UPDATE_PROCESS_PLAN.md` governance flow.
- Testing:
  - CI/governance checks pass; index remains current.
- Anti-patterns:
  - Deferring doc updates to later PRs for behavior changes.

## Add or Update a Pattern

1. Add/update the pattern entry in this document.
2. Update `docs/INDEX.md` if document links changed.
3. Update `docs/DOC_ISSUE_CORRELATION_MAP.md` with related issue IDs.
4. Update `docs/governance/doc_review_registry.json` review metadata.
5. Reference the pattern change explicitly in the PR summary.