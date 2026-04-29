## Summary

- Short description of the change (1–3 lines):
- Related issue(s): # (if any)
- Type of change: bugfix / feature / chore / docs / tests / refactor / breaking change

## Motivation

Why this change is needed and the high-level approach.

## Pattern impact (required for cross-cutting behavior changes)

- Pattern referenced (if applicable):
  - `docs/PATTERN_LIBRARY.md#...`
- Pattern action: reuse / update existing / propose new
- If proposing new pattern:
  - proposal file: `docs/patterns/PATTERN_PROPOSAL_TEMPLATE.md` (copy into PR description or linked doc)
  - expected migration scope:

## How to test locally

Backend
- Ensure a dev database is available (see README or project docs).
- From repo root:
  - cd backend
  - Install dependencies (replace with your install tool if not pip): `pip install -r requirements.txt`
  - Seed DB if needed (project-specific): `./scripts/seed_db.sh` (or see README)
  - Run tests: `pytest -q`

Frontend
- From repo root:
  - cd frontend
  - Install deps: `npm ci`
  - Run unit tests: `npm test`
  - Lint/format: `npm run lint` / `npm run format`

End-to-end
- Start the dev server (as described in README)
- From repo root or frontend/: `npm run e2e`

CI
- CI runs: backend pytest (with coverage), frontend lint & tests, and Cypress E2E. Make sure your PR passes those checks.

## Test delta (required for every feature/bugfix PR)

> Skip this section only for PRs whose title starts with one of these conventional-commit types (followed by `:`, `(`, or a space): `chore`, `docs`, `refactor`, `ci`, `build`, `style`, or `test`. All other feature/bugfix PRs must include a test delta.

- [ ] At least one test file was **added or modified** in this PR
- [ ] `tests/feature_test_matrix.yaml` updated with any new test files (add a row under the correct lane)
- [ ] `tests/local_pre_pr_check.sh changed` passes locally (run from repo root)

If no test delta is included, explain why:
<!-- e.g. "pure docs update", "config-only change with no testable behaviour" -->

## Checklist (required before marking ready)
- [ ] I added/updated tests covering the change
- [ ] I updated any relevant documentation (README, migrations, or CHANGELOG)
- [ ] Linter/formatters pass locally (pre-commit)
- [ ] No secrets or large binaries added
- [ ] CI checks are green (or explained why not)
- [ ] If startup behavior/docs changed: Linux and Windows startup parity was validated (or not applicable with rationale)

## Security checklist (required for auth, API, infra, or dependency changes)
- [ ] Inputs are validated server-side and errors do not leak sensitive internals
- [ ] Protected endpoints enforce auth/role boundaries as expected
- [ ] No credentials/tokens are stored in plain text or committed artifacts
- [ ] New dependencies were reviewed for known vulnerabilities
- [ ] Added/changed headers, CORS, or auth behavior is validated locally

## Notes for reviewers
- Any migration / data changes to be aware of:
- Any backwards compatibility considerations:
- Expected runtime / performance changes:
- Any special steps for deploy / post-merge:

If this is a draft PR, mark it as Draft — I will not request a full review until ready.
