# Contributing to Fantasy Football PI

Thank you for your interest in contributing! This project follows a strict
"Debug‑First" workflow to keep the frontend maintainable and prevent
"works on my machine" bugs. Please read the sections below before opening a
PR.

---

## Git Worktree Workflow (Parallel Branches)

This repository may use Git worktrees to support parallel issue work without
constant branch switching.

1. **When to use worktrees**
    - Use a separate worktree only when you must keep multiple active branches
      open at the same time (for example, active PR plus urgent fix).

2. **Default limit**
    - Keep at most 2 active worktrees in day-to-day use:
      - one for `main`
      - one for the current issue branch
    - Create extra worktrees only for short-lived overlap, then remove them.

3. **Naming convention**
    - Use a branch name like `fix/issue-<number>` (or the team's agreed branch pattern)
      for issue-specific work.
    - For the worktree folder name (path), use `ffpi-issue-<number>` to match the issue.
    - Use descriptive short names for temporary repair worktrees.

4. **Cleanup routine (required)**
    - After a PR merges, remove its worktree immediately.
    - Weekly cleanup:
      - `git worktree list`
      - `git worktree remove <path>` for merged/obsolete branches
      - `git worktree prune`

5. **Safety checks before removal**
    - Confirm branch status is clean (`git status`).
    - Confirm PR is merged or intentionally abandoned.

---

## Frontend Verification & Debugging Standards

To ensure data integrity and system reliability, all frontend development
must follow the **Debug‑First protocol**. "It works on my screen" is not a
sufficient test.

1. **Mandatory Breakpoint Audit**
   - Every new or modified `.jsx` module must be verified using the VS Code
     Debugger (not just console.log). You must explicitly inspect three
     lifecycle stages of the component:
     1. **The Data Fetch (Entry):** Place a breakpoint at the start of every
        `useEffect` or custom hook that initiates an API call. Verify that
        parameters (like `leagueId` or `token`) are valid and not `undefined`
        before the request is fired.
     2. **The Transformation (Data Receipt):** Place a breakpoint immediately
        after an `await apiClient...` call or inside a `.then()` handler. In
        the _Variables_ pane, inspect the raw `response.data` and confirm its
        shape matches what the component expects (e.g. `is_taxi` is a
        boolean, not a string).
     3. **The User Action (Handler):** Place a breakpoint on the first line of
        any `handle*` function (e.g. `handleSubmit`, `handleTaxiMove`).
        Before the payload is sent, verify local state to ensure every field is
        correct.

2. **Naming & Case Sensitivity**
   - The codebase uses **PascalCase** for all React component file names
     (e.g. `ManageCommissioners.jsx`).
   - Never commit two files whose names differ only by case (e.g.,
     `manage-commissioners.jsx` vs. `ManageCommissioners.jsx`). This causes
     module resolution failures in CI/CD and production (Netlify, Vercel,
     etc.).
   - Before committing, run `git ls-files` or inspect your editor to ensure the
     file names exactly match their exported component names.

3. **Definition of Done (DoD)**
   A feature is not considered complete until all three of the following are
   satisfied:
   - ✅ **Test Pass:** `npm run test` (Vitest) completes with zero regressions.
   - ✅ **Debug Pass:** The developer has walked through the component
     lifecycle using the "Frontend: Chrome" VS Code launch config (see below)
     and verified state changes with at least one of the three required
     breakpoints.
   - ✅ **Clean Console:** No warnings about missing `key` props, unhandled
     promise rejections, or hydration errors appear in the browser console.

4. **Responsive Breakpoint Audit (Cross-Platform)**
   - Run the responsive audit on all frontend changes:
     - Linux/Raspberry Pi: `cd frontend && bash ../audit-breakpoints.sh`
     - Windows: use Git Bash/WSL for the same command, or run repo hygiene
       checks via `./scripts/run_repo_hygiene.ps1` from repo root.
   - For true non-layout wrapper components, add `/* ignore-breakpoints */`
     to explicitly opt out.
   - See `docs/RESPONSIVE_AUDIT_ENVIRONMENT.md` for full platform notes.

---

## Debugger Setup (VS Code)

Add the following section to `.vscode/launch.json` (or merge it into your
existing configuration) so you can step through the frontend code in Chrome:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Frontend: Chrome",
      "type": "chrome",
      "request": "launch",
      "url": "http://localhost:5173",
      "webRoot": "${workspaceFolder}/frontend",
      "sourceMapPathOverrides": {
        "webpack:///src/*": "${webRoot}/src/*"
      }
    }
  ]
}
```

Start the Vite dev server (`npm run dev`) and then launch this configuration to
hit breakpoints as you interact with the UI.

---

## Current Action Items

1. **Maintain naming and structure hygiene.**
   - Keep React component filenames in PascalCase and avoid case-only name
     differences in tracked files.
   - If you add a new route page or major module, place it under the existing
     feature folders (for example `src/pages/commissioner/`) rather than
     introducing ad-hoc top-level folders.

2. **Audit critical pages.**
   - Before adding new UI (e.g. Taxi Squad) or touching existing logic
     (LineupRules, WaiverRules, etc.), set breakpoints in each module’s
     fetch hooks and handlers as described above and walk through them using
     the VS Code debugger. Capture a screenshot of the _Variables_ pane for
     at least one component to prove the audit was done.

3. **Keep docs and route matrices synchronized.**
   - Any new page, endpoint surface, or major integration should be reflected
     in `docs/API_PAGE_MATRIX.md` and linked from `docs/INDEX.md`.
   - If docs in `docs/` change, ensure index updates are included in the same
     PR.

4. **UAT artifacts must be updated with every feature or behavior change.**
   - Any new feature, workflow change, validation rule, or UI behavior update
     must include matching updates in `docs/uat/uat_master.xlsx` and
     `docs/uat/uat_overview.pptx` in the same PR.
   - If you add/rename routes, pages, or user-visible actions, add or amend
     UAT rows so testers can validate the new behavior.
   - If screenshots are impacted, refresh deck images using the documented
     source mapping in `docs/uat/UAT_DECK_IMAGE_COVERAGE.md`.
   - If release-critical behavior changes, ensure impacted rows are marked with
     the correct `Execution Tier` (`P0/P1/P2`).
   - If a change affects expected outcomes, update
     `docs/uat/UAT_MASTER_DOCUMENT_INSTRUCTIONS.md` when policy/process needs
     clarification.

5. **Follow the DoD on every PR.** Any pull request lacking one of the three
   DoD checks (tests, debugger walkthrough, clean console) should be
   rejected until the developer demonstrates compliance.

6. **PR review gate: UAT sync check.**
   - Reviewers should reject PRs with user-facing changes if UAT artifacts were
     not updated.
   - Minimum expected evidence in PR description:
     - list of updated UAT IDs or sections
     - slides/pages/screenshots updated in `docs/uat/uat_overview.pptx`
     - whether `Execution Tier` changed for impacted scenarios
     - any new entries added to `Defect_Rollup` template fields if applicable

7. **Workflow YAML hygiene gate (new standard).**
   - Any edit under `.github/workflows/*.yml` must be made in the actual tracked file,
     not a temporary chat/editor buffer.
   - Before commit, verify workflow structure with:
     - one `- name:` per step item
     - `run`, `env`, `if`, and `uses` nested under the same step item only
     - no stray tokens/lines (for example isolated `-q` fragments)
   - Run a final sanity check before push:
     - `git diff -- .github/workflows/*.yml`
     - `python -m scripts.repo_hygiene_check`
   - PRs that modify workflows should include a brief note that YAML structure was
     reviewed and CI syntax is valid.

8. **Issue triage checklist (required before merge).**
   - Confirm whether each issue touched by the PR is:
     - `Resolved in code and ready to close`, or
     - `Still open with remaining implementation work`.
   - If resolved, update `docs/ISSUE_STATUS.md` (`Resolved Issue Closure Queue`) with:
     - issue number/title
     - implementation status
     - close-out note reference
   - Post/prepare a GitHub close comment that includes validation evidence.
   - Close resolved issues before creating new overlapping issues in the same area.
   - In the PR description, include an `Issue Hygiene` section with:
     - `Closed:` list
     - `Pending close:` list
     - `Net new:` list

9. **PR feedback closure gate (required before merge/issue close).**
   - Before merging any PR and before closing linked issues, confirm review feedback is resolved.
   - Required checks:
     - `gh pr view <PR_NUMBER> --repo NPGrant81/fantasy-football-pi --json comments,reviews,reviewDecision`
     - `gh api graphql -f query='query { repository(owner:"NPGrant81", name:"fantasy-football-pi") { pullRequest(number:<PR_NUMBER>) { reviewThreads(first:100) { nodes { isResolved isOutdated comments(first:20) { nodes { author { login } body path line } } } } } } }'`
   - Merge/closure rule:
     - If any actionable thread remains unresolved (`isResolved=false` and not outdated), do not merge yet.
     - Either address it in follow-up commits or explicitly defer it with rationale in PR comments before merge.

---

By adhering to these standards, the frontend stops being a black box and
becomes a maintainable, predictable codebase. Thank you for taking this
extra step! 👏
