## Summary

- Short description of the change (1–3 lines):
- Related issue(s): # (if any)
- Type of change: bugfix / feature / chore / docs / tests / refactor / breaking change

## Motivation

Why this change is needed and the high-level approach.

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

## Checklist (required before marking ready)
- [ ] I added/updated tests covering the change
- [ ] I updated any relevant documentation (README, migrations, or CHANGELOG)
- [ ] Linter/formatters pass locally (pre-commit)
- [ ] No secrets or large binaries added
- [ ] CI checks are green (or explained why not)

## Notes for reviewers
- Any migration / data changes to be aware of:
- Any backwards compatibility considerations:
- Expected runtime / performance changes:
- Any special steps for deploy / post-merge:

If this is a draft PR, mark it as Draft — I will not request a full review until ready.
