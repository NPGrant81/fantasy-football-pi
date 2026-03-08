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
  - Updated `uat_master.xlsx` and `uat_overview.pptx` for the current page set
  - New Cypress capture spec (`cypress/e2e/uat_screenshot_capture.cy.js`)
  - `scripts/update_deck_images.py` automation for future deck refreshes
  - `docs/uat/UAT_DECK_IMAGE_COVERAGE.md` tracks slide→screenshot mapping

### Validation

- All new API endpoints covered by `backend/tests/test_scoring_router.py`
- Player dedup CI gate verified in contributor workflow (`ci-contributor.yml`)
- UAT deck images regenerated and spot-checked against latest page screenshots
