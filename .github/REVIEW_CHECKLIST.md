# Reviewer quick checklist

Use this as your go-to when triaging and reviewing PRs.

Triage (first 5–15 minutes)
- Read PR title/description. If missing, request:
  - summary, test steps, and impact.
- Confirm the PR targets the correct base branch.
- Check CI status and number of changed files (very large PRs should be split or accompanied by a walkthrough).
- Label PR as draft / ready / needs-info.

Automated checks
- Confirm required checks ran: backend tests, frontend lint/tests, E2E (if applicable).
- Confirm no new dependency vulnerabilities introduced (dependency checks).

Manual review
- Does the code do what the PR claims?
- Are tests present & meaningful for new logic?
- Is naming clear and functions small and readable?
- Edge cases & error handling included?
- Any secrets or environment values accidentally added?
- Pattern compliance:
  - Does the PR reference an existing entry in `docs/PATTERN_LIBRARY.md` for cross-cutting behavior?
  - If behavior introduces a new cross-cutting contract, is a pattern proposal included and decision path clear?
  - If a pattern changed, were docs/governance updates included (`docs/INDEX.md`, correlation map, review registry)?

Security & data
- Input validation and escaping present where required
- No hard-coded secrets or credentials
- Check DB migrations for destructive operations

Local validation (commands)
- Fetch + checkout a PR branch (two common ways):
  - If PR branch exists on origin:
    - git fetch origin
    - git checkout -b review/<branch-name> origin/<branch-name>
  - If you prefer fetching by PR number:
    - git fetch origin pull/<PR_NUMBER>/head:pr-<PR_NUMBER>
    - git checkout pr-<PR_NUMBER>
- Backend tests:
  - cd backend
  - Install deps (replace with your project’s method)
  - pytest -q
- Frontend tests:
  - cd frontend
  - npm ci
  - npm test
  - npm run lint

Merging & post-merge
- Ensure branch protection rules / required approvals satisfied.
- Rebase or request author to rebase if there are merge conflicts.
- Prefer squash-merge for concise main history (unless your team uses rebase/merge).
- Update CHANGELOG or release notes if required.
- Monitor CI/deploy and production errors after merging for a short period.

Frugal AI guidance (short)
- When asking AI for help, include: failing test output (full trace), small relevant code snippet, the exact command you ran, and what you expect to happen.
- Batch similar quick requests into a single prompt to save interactions.

If a PR is large (>500 LOC), ask the author to:
- split into smaller PRs, or
- provide a guided walkthrough (short video or a PR description with a stepwise explanation).
