---
name: git-workflow
description: 'Branch naming, Conventional Commits, PR creation, issue linking, GitHub Actions CI, code review process, and merge rules for Fantasy Football PI. Use when: creating branches, writing commits, opening PRs, linking issues, reviewing PRs, or understanding the CI pipeline.'
argument-hint: 'Optional: focus area (branches | commits | pr | ci | issue-linking | review)'
---

# Git Workflow

## Why This Exists
Consistent branch naming, commit messages, and PR structure keep the issue tracker accurate, enable automatic issue closing on merge, and make the history readable for ML audit trails and regression investigations.

## Branch Naming

```
feat/issue-<N>-<slug>        New feature
fix/issue-<N>-<slug>         Bug fix
chore/issue-<N>-<slug>       Non-functional changes (docs, deps, config)
perf/issue-<N>-<slug>        Performance improvements
refactor/issue-<N>-<slug>    Refactoring without behavior change
docs/issue-<N>-<slug>        Documentation only

# Multi-issue batches
feat/issue-<N1>-<N2>-<slug>
```

Examples:
```
feat/issue-48-waiver-opportunity-tracker
fix/issue-161-simulation-nan
chore/cloudflare-phase3-followup
perf/react-query-435
```

## Conventional Commits

Format: `<type>(<scope>): <description>`

| Type | When |
|------|------|
| `feat` | New user-facing feature |
| `fix` | Bug fix |
| `chore` | Maintenance, deps, CI, non-feature |
| `perf` | Performance improvement |
| `refactor` | Code restructure, no behavior change |
| `test` | Test additions or fixes |
| `docs` | Documentation only |
| `style` | Formatting, whitespace, Tailwind token cleanup |

```bash
# Good
feat: add waiver wire opportunity tracker endpoint

Implements rolling opportunity analysis for free agents.
Returns opportunity_score composite with trend detection.

Closes #48

# Also good — multi-issue
feat: analytics suite — luck index, player consistency, playoff bracket

Closes #46
Closes #50
Refs #154

# Bad — no type, no reference
updated some stuff
```

**Rules:**
- Subject line: imperative mood, ≤72 chars, no period
- Body: explain WHY, not what (the diff shows what)
- Footer: `Closes #N` (auto-closes issue on PR merge), `Refs #N` (cross-reference only)

## PR Process

## Repeatable Branch Sync Procedure (Required When Prompted)
When asked to "sync with main", "rebase current branch", or close out merge blockers caused by branch drift, run this exact safe flow.

### Goal
- Update local `main` from `origin/main`
- Rebase the current feature branch on top of latest `main`
- Preserve and restore any local tracked or untracked work

### Safe Rebase Flow
1. Confirm branch and working tree state:
```bash
git status --short --branch
git branch --show-current
```
2. If working tree is dirty, stash tracked and untracked changes:
```bash
git stash push -u -m "autostash-before-main-sync-$(date +%Y%m%d-%H%M%S)"
```
3. Update `main` safely:
```bash
git fetch origin --prune
git checkout main
git pull --ff-only origin main
```
4. Return to original feature branch and rebase:
```bash
git checkout -
git rebase main
```
5. If a stash was created, restore it:
```bash
git stash pop
```
6. Verify final state:
```bash
git status --short --branch
```

### Push Rules After Rebase
- If branch has never been pushed:
```bash
git push -u origin <branch>
```
- If branch was previously pushed and history changed due to rebase:
```bash
git push --force-with-lease
```

### Conflict Handling
- Rebase conflicts:
   - Resolve files
   - `git add <resolved-files>`
   - `git rebase --continue`
- Abort only if requested or necessary:
```bash
git rebase --abort
```
- Stash pop conflicts are handled the same way (resolve, stage, continue normal workflow).

### Opening a PR
1. Push branch: `git push origin feat/issue-48-waiver-tracker`
2. GitHub prints PR URL — open it and fill in the template
3. Title: `feat: waiver wire opportunity tracker (#48)`
4. Body must include:
   ```
   ## Summary
   Brief description of changes.

   ## Closes
   Closes #48

   ## Related Issues
   Refs #44 (Analytics Infrastructure parent)

   ## Testing
   - [ ] Backend: `python -m pytest tests/test_analytics_router.py`
   - [ ] Frontend: `npm test -- --run`
   - [ ] Build: `npm run build`
   ```
5. Assign yourself; add label matching issue type

### Test-Delta Title Gate (CI)
Some PR validation checks require test-file deltas for feature/fix PRs. If a change is operational/non-behavioral (for example CI-only, docs-only, refactor-only), use an exempt PR title prefix so the gate can skip test-delta enforcement.

Accepted exempt prefixes at title start:
- `chore:` / `chore(` / `chore `
- `docs:` / `docs(` / `docs `
- `refactor:` / `refactor(` / `refactor `
- `ci:` / `ci(` / `ci `
- `build:` / `build(` / `build `
- `style:` / `style(` / `style `
- `test:` / `test(` / `test `

Example:
```text
ci: implement dead/stale code detection reporting pipeline (#301)
```

If the PR is truly feature/bug behavior, keep `feat`/`fix` and include matching test file deltas.

### PR Review Checklist
See `.github/REVIEW_CHECKLIST.md` for full list. Key gates:
- All CI checks pass (lint, test, build)
- `hist_%` exclusion present on any new member-list query
- No raw SQL
- No dark-only Tailwind classes
- `Closes #N` in PR body
- Tests added for new logic

Validation architecture gates (Issue #76):
- Validation dependency install path is preserved in CI (`backend/requirements-validation.txt`)
- Validation-focused tests pass: `backend/tests/test_validation_service.py` and `etl/test_validation_framework.py`
- PR summary states which validation boundary changed (API boundary, dynamic rules, DataFrame schema, or expectations)

## Copilot Review Monitoring (Required)
For every opened PR, initiate Copilot review and actively monitor/respond until no actionable feedback remains.

Flow:
1. Open PR immediately after push (do not wait for deployment)
2. Request Copilot review on the PR
3. Monitor PR feedback cycles:
   - Check review comments and unresolved threads
   - Address code feedback in follow-up commits
   - Resolve threads only after fix is merged/pushed
4. Record outcomes in notes:
   - Add a short "Copilot Feedback" section to `docs/PR_NOTES.md`
   - Update related issue close-out notes with any behavioral changes introduced by review fixes

Minimum PR notes block:
```markdown
## Copilot Feedback
- Review requested: YYYY-MM-DD
- Threads opened: <N>
- Threads resolved: <N>
- Follow-up commits: <sha1>, <sha2>
- Residual risk: None / <brief note>
```

### Merge Rules
- Squash merge preferred for feature branches (clean history)
- Never force-push to `main`
- Never push directly to `main` — always via PR
- Delete branch after merge: `git branch -d feat/issue-48-...`

## CI Pipeline
On every push/PR, GitHub Actions runs:
1. **Backend lint** (`flake8` / `black --check`)
2. **Backend tests** (`pytest`)
3. **Frontend lint** (`npm run lint`)
4. **Frontend tests** (`npm test -- --run`)
5. **Frontend build** (`npm run build`)

All 5 must pass before merge is allowed.

### Local pre-commit checks
```bash
# Run before pushing to catch issues early
cd backend && python -m pytest
cd frontend && npm run lint && npm test -- --run && npm run build
```

Pre-commit hooks are configured in `.pre-commit-config.yaml`.

## Issue Linking
- `Closes #N` in commit or PR body → auto-closes issue when PR merges to main
- `Fixes #N` → same behavior
- `Refs #N` → cross-reference without auto-close
- Mention branch name in issue comments for tracking

## Issue Close-Out Notes (Tracking Requirement)
For analytics and multi-issue batches (like #46, #48, #50), auto-closing is not enough. Add an issue comment with implementation/deploy evidence so issue history is auditable.

Use this flow:
1. During PR: include `Closes #N` / `Refs #N` in PR body
2. After merge: add close-out comment to each issue with summary + evidence
3. After deploy: update comment (or add follow-up) confirming production validation

Recommended references:
- `ISSUE_STATUS.md` for roll-up status tracking
- `docs/PR_NOTES.md` for reusable close-out note snippets

### Posting Close-Out Comments via MCP
The GitHub MCP server is configured in `~/.config/Code/User/mcp.json`. Copilot can post issue comments directly using the `create_issue_comment` MCP tool — no manual browser step needed.

When asked to close out an issue, use this tool:
```
Tool: create_issue_comment
owner: NPGrant81
repo: fantasy-football-pi
issue_number: <N>
body: <close-out comment text>
```

The MCP server requires `GITHUB_TOKEN` in the environment (set via `~/.bashrc` → `export GITHUB_TOKEN=$(gh auth token)`). If the tool is unavailable, fall back to the manual `gh` CLI:
```bash
gh issue comment <N> --repo NPGrant81/fantasy-football-pi --body "..."
```

Issue comment template:
```markdown
## Close-Out Notes
- Implemented in PR #<N>
- Branch: <branch-name>
- Commits: <sha1>, <sha2>
- Validation:
   - [x] Backend tests passed
   - [x] Frontend tests/build passed
   - [x] Feature check completed
- Deployment: merged / deployed on YYYY-MM-DD
- Follow-ups: None / Refs #<N>
```

## Worktree Rules
- Max 2 active worktrees: `main` + current feature branch
- After PR merges: `git worktree remove <path>` + `git worktree prune`
- Never leave uncommitted changes in a worktree before switching

## Always Do
- Create a branch for every change — never commit directly to `main`
- Include `Closes #N` in the PR body for every issue being addressed
- Run the local test suite before pushing
- When prompted to sync/rebase, use the safe stash -> update main -> rebase -> restore flow above
- Reference the parent issue when working on sub-stories
- Keep commits atomic — one logical change per commit
- Post close-out notes on each related issue when work merges (and update after deploy)
- Request Copilot review on every PR and monitor threads to resolution

## Never Do
- Never `git push --force` on `main` or shared branches
- Never `git reset --hard` on a branch with unverified pushes
- Never commit `.env`, secrets, or `__pycache__`
- Never merge without CI passing
- Never rebase public branches after others have checked them out

## Related Skills
- [Project Bootstrap](../project-bootstrap/SKILL.md) — repo setup
- [Deployment](../deployment/SKILL.md) — release process
- [Testing](../testing/SKILL.md) — what CI runs
- [Security](../security/SKILL.md) — `.gitleaks.toml` secret scanning in pre-commit
