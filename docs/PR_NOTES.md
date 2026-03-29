Pull request test branch: feature/tests-ci

> Historical snapshot: This file records point-in-time PR and issue close-out notes.
> For current state, use GitHub PR/issue threads and `docs/ISSUE_STATUS.md` as canonical sources.

This branch was created to trigger CI for backend and frontend tests.

---

## PR #140 — Corrected scope description

The original PR #140 description ("Refresh UAT deck assets and capture automation") only covered a
subset of the work merged in that branch. The full scope is documented below so reviewers can
assess impact and risk across all areas.

### Summary

- **Scoring rules — schema & API (Issues #39–#42)**
  - Add `ScoringRule` model, Alembic migration, and `GET/POST/PUT/DELETE /scoring/rules` endpoints
  - Implement per-position, per-stat calculation engine (`scoring_service.py`)
  - Add migration import tooling so existing league configs can seed rule rows
- **Commissioner scoring UI**
  - `ManageScoringRules` page: list, create, and edit rules with position/stat filters
  - Hardened form validation: requires at least one stat weight before saving
- **Player deduplication audit + CI gate**
  - `backend/scripts/audit_player_duplicates.py` scans for players grouped by
    `player_service.canonical_player_key()` (prefers `gsis_id`/`espn_id`, then falls back to
    normalized name + position + canonicalized team)
  - New `dedupe_players` management command resolves rows without data loss
  - CI job (`ci.yml` backend stage) fails the build if duplicates are detected
- **Draft Day Analyzer improvements**
  - Analyzer is now served via the `/draft-day-analyzer` frontend route with its own page component
  - Current vs previous season ranking toggle uses `rankingSeasonOffset` in `localStorage` (drives `/draft/rankings?season=...` requests)
  - Shows logged-in owner's team context in the strategy panel
  - Removes deprecated detail-action calls; falls back to embedded player insights
- **Deployment documentation**
  - `docs/RASPBERRY_PI_DEPLOYMENT.md` — nginx reverse-proxy + systemd service runbook
  - `docs/CLOUDFLARE_TUNNEL_SETUP.md` — Cloudflare tunnel config for `pplinsighthub.com`
- **UAT artifacts refresh**
  - Updated `docs/uat/uat_master.xlsx` and `docs/uat/uat_overview.pptx` for the current page set
  - New Cypress capture spec (`frontend/cypress/e2e/uat_capture_pages.spec.js`)
  - `scripts/update_uat_deck_images.py` automation for future deck refreshes
  - `docs/uat/UAT_DECK_IMAGE_COVERAGE.md` tracks slide→screenshot mapping

### Validation

- New `/scoring/rules` API endpoints manually smoke-tested in a local dev environment
- Player dedup CI gate verified in contributor workflow (`ci-contributor.yml`)
- UAT deck images regenerated and spot-checked against latest page screenshots

---

## Issue #81 Close-Out Notes

Issue: `#81` - Phase 1: Raspberry Pi OS Setup

### Resolution summary

- Added a Phase 1 section to the Raspberry Pi deployment runbook for fresh-host bring-up.
- Documented Raspberry Pi Imager choices for a headless Raspberry Pi OS Lite (64-bit) install.
- Added first-boot SSH onboarding guidance, including hostname and direct-IP fallback paths.
- Added immediate post-boot validation commands and reboot verification steps.
- Clarified the handoff boundary between base host setup and later deployment work such as Nginx, systemd, TLS, and Cloudflare.

### Verification checklist for issue closure

- [x] Fresh-image workflow is documented from Raspberry Pi Imager through first SSH login.
- [x] Headless bring-up includes hostname and IP-based access fallback.
- [x] Immediate host validation commands are documented.
- [x] The runbook cleanly separates Phase 1 from later deployment phases.

### Suggested GitHub Issue close comment

```md
Status update: moving this issue to **Complete**.

What was delivered:
- Added Phase 1 Raspberry Pi OS setup guidance to `docs/RASPBERRY_PI_DEPLOYMENT.md`.
- Documented Raspberry Pi Imager settings for a headless Raspberry Pi OS Lite (64-bit) install.
- Added first-boot SSH onboarding guidance with hostname and IP fallback.
- Added immediate post-boot validation commands and clarified the transition into later deployment phases.

Validation evidence:
- Reviewed updated Phase 1 runbook content in `docs/RASPBERRY_PI_DEPLOYMENT.md`.
- Markdown validation passed for the updated runbook and issue draft.

References:
- Repo docs: `docs/RASPBERRY_PI_DEPLOYMENT.md`
- Local issue draft: `issues/milestone-2-raspberry-pi-setup.md`

Close-out:
- Follow-on host preparation remains tracked in `#290`.
```

---

## Issue #290 Carryover Notes

Issue: `#290` - Pre-Deploy Raspberry Pi Host Foundation Checklist (Packages, Hardening, Service Readiness)

### Current status

- Execution-complete for baseline host preparation on the Raspberry Pi.
- Intentionally still open because remaining work is app-coupled and was deferred by scope.

### Completed this pass

- Captured exact package, firewall, and service enablement results in the local issue draft.
- Prepared the parent issue update note in `issues/pre-deploy-raspberry-pi-host-foundation-parent-note.md`.
- Marked the child checklist as complete for the baseline host foundation work.

### Deferred follow-on before Cloudflare cutover

- Final app Nginx site wiring on the Pi
- Backend production env/secrets finalization
- Backup timer activation against the final database target
- Cloudflared production credential placement and service cutover

### Suggested GitHub issue status comment

```md
Status update: issue remains **In Progress**.

Completed this pass:
- Baseline Raspberry Pi host foundation work is complete: required packages installed, UFW enabled with OpenSSH and Nginx rules, fail2ban enabled, and nginx/fail2ban verified active.
- Execution notes and verification details are captured in the repo issue draft.
- Parent update note for `#79` is prepared.

Remaining scope:
- Final app Nginx site + runtime wiring
- Backend production env/secrets finalization
- Backup timer activation against the final DB target
- Cloudflared production credential placement and service cutover

References:
- Child issue draft: `issues/pre-deploy-raspberry-pi-host-foundation-checklist.md`
- Parent note draft: `issues/pre-deploy-raspberry-pi-host-foundation-parent-note.md`

Carryover tracking:
- Cloudflare/public routing work remains in `#83`
```

---

## Issue #131 Close-Out Notes

Issue: `#131` - Create Dedicated Draft Day Analyzer Page + Fix Advisor & Simulation Failures

### Resolution summary

- Added a dedicated Analyzer route at `/draft-day-analyzer` and surfaced it in sidebar navigation.
- Removed Analyzer-specific experience from shared War Room space so strategy tooling is isolated.
- Consolidated Analyzer page composition around dedicated modules (insights, rankings, advisor, simulation).
- Implemented persistence for lightweight UI state (selection/filter/sort/search) while avoiding persistence of simulation/model output.
- Updated simulation and advisor interaction behavior to align with current backend integration and user-facing fallbacks.
- Added player-list performance and usability improvements to support larger draft datasets.

### Verification checklist for issue closure

- [x] Sidebar entry opens `/draft-day-analyzer`.
- [x] War Room no longer renders Draft Day Analyzer feature block.
- [x] Analyzer state persists only lightweight UI state.
- [x] Simulation requests no longer fail due to stale endpoint wiring.
- [x] Error states are handled with actionable user messaging.

### Suggested GitHub Issue close comment

```md
Closed via `feature/scoring-integration-analytics`.

Issue #131 is complete:
- Draft Day Analyzer now has a dedicated route (`/draft-day-analyzer`) and sidebar nav entry.
- Analyzer functionality was removed from War Room to keep league/shared space clean.
- Analyzer modules are now grouped into a standalone page flow.
- Lightweight state persistence (selected player, filter, sort, search) is retained across reloads.
- Simulation/advisor interactions were aligned to current backend integration with improved fallback handling.
- Large player-list interactions were optimized for draft-day usage.

Validation: route/navigation, War Room separation, persistence behavior, and simulation/advisor interactions were re-tested in the current branch.
```

---

## Issue #186 Close-Out Notes

Issue: `#186` - Bug Report System Cannot Create GitHub Issues (GitHub App Credentials Not Configured)

### Resolution summary

- Implemented PAT-first GitHub authentication for issue creation (`GITHUB_TOKEN`/`GH_TOKEN`) with GitHub App credentials as fallback.
- Added explicit warning/error logging for GitHub issue creation failures while preserving successful in-app bug report persistence.
- Standardized auth/header flow for GitHub API requests and improved failure message clarity.
- Added backend utility tests covering PAT path, App fallback path, and missing-auth failure path.
- Added endpoint integration coverage for `/feedback/bug` success and warning responses.

### Verification checklist for issue closure

- [x] Bug report submissions succeed even when GitHub issue creation fails.
- [x] PAT auth path is tested and used as primary when configured.
- [x] App fallback path is tested and available when PAT is absent.
- [x] `/feedback/bug` integration tests validate returned issue URL and warning behavior.

### Suggested GitHub Issue close comment

```md
Closed via `feature/scoring-integration-analytics`.

Issue #186 is complete:
- Added PAT-first GitHub auth for bug-report issue creation (`GITHUB_TOKEN` / `GH_TOKEN`).
- Added GitHub App credential fallback when PAT is not configured.
- Hardened error/warning logging so report persistence and GitHub issue creation failures are clearly separated.
- Added backend tests for PAT path, App fallback, and no-auth failure.
- Added `/feedback/bug` integration coverage for both success and warning outcomes.

Validation: targeted backend tests pass for utility and router flows, and bug reports now degrade gracefully when GitHub issue creation is unavailable.
```

---

## Issue #187 Close-Out Notes

Issue: `#187` - Improve Bug Report UI to Display GitHub Issue Link and Better Error Handling

### Resolution summary

- Enhanced success/warning/error UX on `/bug-report` to clearly communicate outcome states.
- Added loading state with submit-button text update and full form disablement during submission.
- Added retry flow for failed submissions using preserved request payload (`Retry Submit`).
- Kept success path issue-link surfacing and warning-path guidance for manual follow-up when needed.
- Added dedicated frontend tests for loading/disable state and retry flow.

### Verification checklist for issue closure

- [x] Submit button enters loading state during async submission.
- [x] Form controls are disabled while a submission is in flight.
- [x] Error state presents retry action.
- [x] Retry path reuses last payload and can complete successfully.
- [x] Frontend tests validate loading and retry behavior.

### Suggested GitHub Issue close comment

```md
Closed via `feature/scoring-integration-analytics`.

Issue #187 is complete:
- Improved bug-report success/warning/error messaging to reduce ambiguity.
- Added loading UX (`Submitting...`) and disabled form controls during submit.
- Added retry action (`Retry Submit`) for transient failures.
- Preserved issue-link surfacing when GitHub issue creation succeeds.
- Added dedicated frontend tests for loading/disable and retry flows.

Validation: `frontend/tests/BugReport.test.jsx` passes (2/2), and frontend production build passes after the UX changes.
```

---

## Issue #188 Close-Out Notes

Issue: `#188` - Add Support for Mermaid Diagrams in Markdown (MD) Across the Platform

### Resolution summary

- Added shared markdown rendering support for Mermaid diagrams in frontend markdown contexts.
- Introduced Mermaid diagram component integration and wiring in key markdown display surfaces.
- Added targeted frontend tests for Mermaid rendering and shared markdown renderer behavior.
- Applied review follow-up hardening to ID/language handling to stabilize Mermaid parsing/render behavior.

### Verification checklist for issue closure

- [x] Mermaid fenced code blocks render through shared markdown path.
- [x] Existing markdown rendering continues to work for non-Mermaid content.
- [x] Frontend tests cover renderer + Mermaid component behavior.
- [x] Frontend build succeeds with Mermaid dependency integrated.

### Suggested GitHub Issue close comment

```md
Closed via `feature/scoring-integration-analytics` (merged PR #191 commits).

Issue #188 is complete:
- Added Mermaid support in shared Markdown rendering.
- Integrated Mermaid diagram rendering component into markdown display flows.
- Added frontend test coverage for Mermaid + markdown renderer behavior.
- Included review-driven hardening updates for stable rendering behavior.

Validation: targeted Mermaid tests pass and frontend build succeeds with Mermaid enabled.
```

---

## Bulk Close Comment Pack (Resolved Open Issues)

## Issue Status Update Template Pack (New)

Use these templates to keep GitHub issue status transitions consistent with project policy.

### Template A: Start Work (`To Do` -> `In Progress`)

```md
Status update: moving this issue to **In Progress**.

Scope started:
- [short summary of implementation being started]

Execution references:
- Branch: `<branch-name>`
- PR: `<pr-link-or-number>` (use `TBD` if PR not opened yet)

Planned validation:
- [test command / smoke checks you intend to run]

Next update will include validation evidence and either:
- transition to **Complete**, or
- explicit carryover scope if work remains.
```

### Template B: Completion Update (`In Progress` -> `Complete`)

```md
Status update: moving this issue to **Complete**.

What was delivered:
- [change 1]
- [change 2]

Validation evidence:
- [test command + result]
- [smoke/manual verification + result]

References:
- PR: `<pr-link-or-number>`
- Commits: `<short-sha list>`

Close-out:
- Added to `docs/ISSUE_STATUS.md` closure queue (if closure action is not immediate).
- If any follow-up scope remains, it is tracked in: `<follow-up-issue-link-or-number>`.
```

### Template C: Carryover/Partial Completion (stays `In Progress`)

```md
Status update: issue remains **In Progress**.

Completed this pass:
- [completed item]

Remaining scope:
- [remaining item]

References:
- PR: `<pr-link-or-number>`
- Validation run: [commands/results]

Carryover tracking:
- Follow-up issue: `<issue-link-or-number>`
- Reason for not moving to Complete: [brief rationale]
```

### Issue #19

```md
Closing as resolved.

Story 5.3 (Waiver Processing Logic) is implemented in the current codebase:
- Waiver processing logic is wired through backend waiver services/scripts.
- Claim evaluation, ordering, and processing flow are in place for waiver execution.
- Supporting validations and error handling are integrated with the waiver workflow.

Validation: waiver processing behavior has been exercised through existing backend/frontend waiver flows and tracked in project status docs.
```

### Issue #20

```md
Closing as resolved.

Story 5.4 (Waiver Result Notifications) is implemented:
- Email notification templates for waiver outcomes are present under `templates/email/`.
- Waiver processing includes user-facing notification support in current workflow.

Validation: notification templates and related waiver workflow integration are present and tracked in completed waiver-system scope.
```

### Issue #31

```md
Closing as resolved.

Waiver Wire Rules Page Setup & Navigation is complete:
- Commissioner waiver-rules page/navigation exists and is linked in current commissioner flows.
- Waiver rules management entry point is available as part of the implemented commissioner tooling.

Validation: page routing/navigation for waiver-rule management is available in the current branch implementation.
```

### Issue #32

```md
Closing as resolved.

Waiver Wire Rules Configuration Form is complete:
- Commissioners can configure waiver settings (mode/tie-breaker/budget-related fields) via implemented form UI.
- Form wiring and persistence are connected to backend settings support.

Validation: configuration fields and save/reload behavior are part of the completed waiver-rules implementation.
```

### Issue #33

```md
Closing as resolved.

Waiver Wire Transactions History & Audit is complete:
- Waiver transaction/claim history is available through current waiver data surfaces.
- Audit-oriented visibility is included in the implemented waiver management experience.

Validation: waiver history/audit access is present in existing waiver UI/API behavior and tracked as completed scope.
```

### Issue #34

```md
Closing as resolved.

Waiver Wire Backend Integration is complete:
- Waiver settings and claim actions are wired through backend router/service logic.
- Frontend waiver flows are integrated with backend endpoints.

Validation: backend integration is present in current waiver feature set and reflected in project completion notes.
```

### Issue #35

```md
Closing as resolved.

Waiver Wire Testing scope is complete for current baseline:
- Waiver-related flows are covered by the existing frontend/backend test strategy and CI runs.
- Feature behavior is validated within current regression workflow.

Validation: tests and CI checks for waiver functionality are included in ongoing repository validation.
```
