Pull request test branch: feature/tests-ci

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

## Bulk Close Comment Pack (Resolved Open Issues)

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
