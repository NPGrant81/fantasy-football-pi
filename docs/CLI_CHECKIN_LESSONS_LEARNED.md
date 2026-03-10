# CLI Check-In Lessons Learned

Date: 2026-03-08
Scope: Recent implementation and debugging sessions on `feature/scoring-integration-analytics`

## Why this file exists
This file records concrete break/fix learnings from CLI-driven check-ins so future build-outs can avoid repeat regressions.

## Lessons and Applied Fixes

1. Stale editor buffers can produce false failure signals
- Symptom: CI YAML appeared broken in Problems panel while on-disk workflow file was valid.
- Fix applied: Verified disk content directly and avoided patching based on unsaved/temporary buffer diagnostics.
- Guardrail: Confirm source-of-truth file content before fixing parser/lint errors.

2. Vite proxy prefixes can hijack SPA routes
- Symptom: Frontend paths like `/playoffs` were intercepted by dev proxy and failed page routing.
- Fix applied: Narrowed proxy entries to API-style prefixes (for example `/playoffs/`, `/keepers/`).
- Guardrail: Reserve top-level UI routes for SPA and keep proxy scope explicit.

3. Legacy NULL league links still matter in production-like data
- Symptom: Scoring and lineup reads missed legacy records where `league_id` was NULL.
- Fix applied: Included `league_id IS NULL` compatibility filters where required.
- Guardrail: Add legacy compatibility assertions in tests for any league-scoped query.

4. Dedupe steps can silently destroy ranking order
- Symptom: Top free-agent ranking reordered unexpectedly after dedupe step.
- Fix applied: Added explicit post-dedupe sort by ranking keys.
- Guardrail: After dedupe/merge transforms, re-assert ordering contract in code and tests.

5. Issue hygiene prevents duplicate implementation paths
- Symptom: Completed work remained open in GitHub and risked duplicate follow-up work.
- Fix applied: Closed completed issues, split remaining scope to a dedicated carryover issue.
- Guardrail: For partial completion, close finished parent scope and open focused follow-up issue with explicit dependency links.

6. PR review feedback must be cleared before merge/closure
- Symptom: A PR was merged while automated review threads still contained unresolved actionable comments.
- Fix applied: Added a required pre-close PR check to verify no unresolved review threads remain.
- Guardrail: Do not merge or close linked issues until review feedback is audited and either resolved in code/docs or explicitly deferred in PR comments.

## CLI Workflow Practices That Worked
- Use targeted smoke calls after backend changes (API payload checks before UI assumptions).
- Run narrow pytest modules first, then broader groups when stable.
- Capture close-out comments with commit and validation evidence before issue closure.

## Action Items for Future Sessions
- Keep this file updated whenever a regression root cause is found and fixed.
- Link each major lesson to a related issue when possible.
- Promote recurring guardrails into `CONTRIBUTING.md` when they become team standards.

## Required Pre-Close PR Check (New)
Before merging a PR and closing related issue(s), run this checklist:

1. Check conversation-level comments and reviews.
- `gh pr view <PR_NUMBER> --repo NPGrant81/fantasy-football-pi --json comments,reviews,reviewDecision`

2. Check inline review threads for unresolved feedback.
- `gh api graphql -f query='query { repository(owner:"NPGrant81", name:"fantasy-football-pi") { pullRequest(number:<PR_NUMBER>) { reviewThreads(first:100) { nodes { isResolved isOutdated comments(first:20) { nodes { author { login } body path line } } } } } } }'`

3. Merge gate.
- If any actionable thread is unresolved (`isResolved=false` and not outdated), do not merge yet.
- Resolve in follow-up commit(s), then re-check before merging and closing issue(s).
