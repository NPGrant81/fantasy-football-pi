# GitHub Issues Status Report

**Date:** March 8, 2026  
**Branch:** feature/scoring-integration-analytics

---

## Resolved Issue Closure Queue (March 2026)

- **Issue #186**: `Bug Report System Cannot Create GitHub Issues (GitHub App Credentials Not Configured)`
  - **Implementation Status:** Resolved in `feature/scoring-integration-analytics`
  - **GitHub Status:** Closed (March 8, 2026) with close-out comment
  - **Close-Out Evidence:** `d957f4e` (PAT-first auth + App fallback), `0604b59` (integration coverage)
  - **Close Comment Source:** `docs/PR_NOTES.md` -> `Issue #186 Close-Out Notes`
- **Issue #187**: `Improve Bug Report UI to Display GitHub Issue Link and Better Error Handling`
  - **Implementation Status:** Resolved in `feature/scoring-integration-analytics`
  - **GitHub Status:** Closed (March 8, 2026) with close-out comment
  - **Close-Out Evidence:** `d957f4e` (success/warning messaging), `8e0b05b` (loading/disable/retry + frontend tests)
  - **Close Comment Source:** `docs/PR_NOTES.md` -> `Issue #187 Close-Out Notes`
- **Issue #188**: `Add Support for Mermaid Diagrams in Markdown (MD) Across the Platform`
  - **Implementation Status:** Resolved in `feature/scoring-integration-analytics` via merged PR #191 commits
  - **GitHub Status:** Closed (March 8, 2026) with close-out comment
  - **Close-Out Evidence:** `1fa6eb7` (Mermaid rendering support), `65197ff` (follow-up review hardening)
  - **Close Comment Source:** `docs/PR_NOTES.md` -> `Issue #188 Close-Out Notes`

---

## ✅ COMPLETED STORIES

### Story 5.1: Free Agent Search

- **Status:** ✅ COMPLETED
- **Frontend:** [WaiverWire.jsx](frontend/src/pages/WaiverWire.jsx) - Search and display with filtering
- **Backend:** `GET /players/search` endpoint fully implemented
- **Details:** Users can search for and view free agent players, filter by position, sort by points
- **Verification:** All acceptance criteria met

### Story 2.1-2.3: Draft System

- **Status:** ✅ COMPLETED
- **Frontend:** [DraftBoard.jsx](frontend/src/pages/DraftBoard.jsx)
- **Backend:** `/draft` router with pick management, state tracking, and finalize endpoints
- **Details:** Full draft board with player selection, bye weeks respect, position tracking
- **Verification:** Draft flow complete, rosters populate correctly

### Story 4.2-4.4: Scoring & Rules Management

- **Status:** ✅ COMPLETED
- **Frontend:** [ManageScoringRules.jsx](frontend/src/pages/ManageScoringRules.jsx)
- **Backend:** `GET /leagues/{league_id}/settings`, `/scoring` router, scoring service
- **Details:** Commissioner can manage scoring rules, weekly locks, excel overrides
- **Verification:** Scoring rules persisted and applied to matchups

### Story 5.2-5.4: Waiver System

- **Status:** ✅ COMPLETED
- **Frontend:** [WaiverWire.jsx](frontend/src/pages/WaiverWire.jsx) with bid management
- **Backend:** `/waivers` router with processing logic, notifications, blind bidding
- **Details:** Full waiver processing with blind bid management and result notifications
- **Verification:** Waivers processed on schedule, results posted

### Story 3.1: Team Customization

- **Status:** ✅ COMPLETED
- **Frontend:** [MyTeam.jsx](frontend/src/pages/MyTeam.jsx)
- **Backend:** `/team` router with roster and team info endpoints
- **Details:** Users can manage team name, view roster, customize settings
- **Verification:** Team name persists, roster displays correctly

### Story 6 (Matchups): Matchups & Game Center

- **Status:** ✅ COMPLETED (Core Features)
- **Frontend:** [Matchups.jsx](frontend/src/pages/Matchups.jsx), [GameCenter.jsx](frontend/src/pages/GameCenter.jsx)
- **Backend:** `GET /matchups/week/{week_num}`, `GET /matchups/{matchup_id}`, matchups router
- **Details:** Week-by-week matchups with detailed game scoring
- **Verification:** Matchups display correctly, scores calculate

---

## 🔄 PARTIALLY IMPLEMENTED

### Story 6.1: League Standings

- **Status:** ✅ COMPLETED
- **Completed:** Standings completion follow-ups were delivered and closed.
- **Close-Out Evidence:** GitHub issues `#21`, `#200`, and `#201` are closed.
- **Notes:** Keep this story closed unless a net-new standings scope is opened.

### Story 6.3: Top Free Agents Module

- **Status:** ✅ COMPLETED
- **Completed:** Top free agents follow-up work is closed.
- **Close-Out Evidence:** GitHub issues `#23` and `#203` are closed.
- **Notes:** Re-open only if new ranking dimensions are requested.

---

## ⏳ NOT YET IMPLEMENTED

### Story 6.2: Playoff Bracket Visualization

- **Status:** 🔄 PARTIAL (Core delivered, dynamic structure follow-up open)
- **Priority:** Medium
- **Notes:** Baseline bracket, historical mode, and bracket-type UX delivered. Remaining dynamic commissioner-settings behavior is tracked in GitHub issue [#154](https://github.com/NPGrant81/fantasy-football-pi/issues/154).
- **Complexity:** Medium/High - structure mapping across league configurations

### Story 6.4: Matchup Win Probability

- **Status:** ✅ COMPLETED
- **Priority:** Medium
- **Notes:** Implemented projected win percentage formula and progress bar UX in Matchups + Game Center. Closed via GitHub issue `#24`.
- **Complexity:** Baseline complete; future refinements can extend model sophistication.

### Story 7.2: Dark/Light Mode Toggle

- **Status:** ✅ COMPLETED (Baseline)
- **Priority:** Low
- **Notes:** Story issue `#26` is closed. Ongoing theme polish is tracked separately in issue `#75`.
- **Complexity:** Medium - theme system implementation

### Story 7.3: Bug Reporting Form

- **Status:** ✅ COMPLETED
- **Priority:** Low
- **Notes:** Users can submit bug or feature reports via `/bug-report`; backend stores entries and opens GitHub issues with PAT-first auth and GitHub App fallback. UI now includes success/warning/error feedback, issue links, loading disablement, and retry action.
- **Complexity:** Low - form + email/storage

### Story 1.2: Historical Data Archiving

- **Status:** ✅ COMPLETED (Initial Scope)
- **Priority:** Low
- **Notes:** Story issue `#6` is closed. Additional historical pipeline work continues under newer issues (for example `#286`, `#288`, and `#341` for League 60 historical owner identity backfill).
- **Complexity:** Medium - migration and cleanup scripts

---

## Draft Value Database & API Integration

- [x] Issue #56: Create draft value database for fantasy football draft purposes
- [x] Issue #57: Create APIs to pull in draft value information from ESPN, Yahoo, Draftsharks

---

## 🏗️ INFRASTRUCTURE TASKS

### Story 0.1: Install Docker & Postgres on Pi

- **Status:** ✅ COMPLETED
- **Details:**
  - docker-compose.yml configured with PostgreSQL
  - Backend running in Docker containers
  - Data persistence with volume mapping
  - Port 5432 accessible
- **Verification:** Services running, database persistent

### Story 0.2: Cloudflare Tunnel Setup

- **Status:** ⏳ IN PROGRESS / OPTIONAL
- **Notes:** External access setup; local development functional
- **Blockers:** Requires domain name and Cloudflare account
- **Next Steps:** Domain setup (optional, not MVP-blocking)

### Story 0.3: Database Scheduled Backups

- **Status:** ✅ COMPLETED
- **Details:** Implemented microSD-targeted database backup automation with a bash backup script, systemd service/timer examples, retention pruning, and a restore runbook.
- **Evidence:** `ops/backup/microsd_db_backup.sh`, `deploy/systemd/microsd-db-backup.service.example`, `deploy/systemd/microsd-db-backup.timer.example`, `docs/restore.md`
- **Verification:** Backup automation artifacts are present and documented for deployment/restore workflows.

---

## 📋 RECENT IMPROVEMENTS (This Session)

### ✨ Login Form Enhancement

- **Commit:** `ee31db4` - "feat: add league ID input to login form with 'The Big Show' as default"
- **Change:** Modified login to accept league ID instead of league selection post-login
- **Impact:** League persistence at login time, eliminates LeagueSelector step
- **Default League:** "The Big Show" (League ID 1) for test environment

### 📊 Issue Status Documentation

- **Commit:** `e739f93` - "docs: add GitHub issues status report and completion tracking"
- **Change:** Created comprehensive tracking of feature completion
- **Impact:** Clear roadmap for remaining work

### 🧠 Player Metadata Normalization Learning (Issue #103)

- **Issue:** `#103 - Player Metadata Cleanup & Standardization`
- **Learning Captured:** Player identity must be independent from season/team state.
- **Phase-1 Changes Implemented:**
  - Added normalized tables: `player_seasons` and `player_aliases`
  - Added Alembic migration: `backend/alembic/versions/20260312_01_player_identity_normalization.py`
  - Added ingestion utility: `backend/services/player_identity_service.py`
  - Updated sync pipelines to upsert season-dependent rows:
    - `backend/scripts/import_espn_players.py`
    - `backend/scripts/daily_sync.py`
    - `backend/scripts/run_uat_sync.py`
- **Operational Outcome:** Active-season updates now write to dependent player-season state without relying solely on mutable base-player columns.

### 🐞 Bug Report Reliability + UX Hardening

- **Commit(s):** `d957f4e`, `0604b59`, `8e0b05b`
- **Change:** Added PAT-first GitHub issue auth with App fallback, endpoint-level integration tests, and frontend loading/retry UX coverage.
- **Impact:** Bug reports now degrade gracefully and provide clearer user outcomes when GitHub issue creation fails.

### 🧩 Mermaid Markdown Rendering

- **Commit(s):** `1fa6eb7`, `65197ff`
- **Change:** Added Mermaid diagram support in shared markdown rendering paths and follow-up reliability fixes.
- **Impact:** Platform markdown views can render Mermaid diagrams for richer technical documentation.

---

## SUMMARY

- **Total Open Issues:** Dynamic; use `gh issue list --state open` for current count.
- **✅ Fully Completed:** Includes Stories `1.2`, `6.1`, `6.3`, `6.4`, `7.2`, and `7.3`.
- **🔄 Partially Completed:** Story `6.2` dynamic structure follow-up only.
- **📌 Active Follow-Ups:** Track open operational scope in GitHub issues rather than reopening closed story-description issues. Current example: `#341` covers League 60 historical owner identity enrichment and backfill.
- **🏗️ Infrastructure:** 3 tasks (0.1 ✅, 0.2 ⏳, 0.3 ⏳)

---

## RECOMMENDATIONS FOR NEXT SPRINTS

### P1 (High Priority)

1. **Complete Story 6.2 follow-up** - Dynamic commissioner-settings bracket structure
  - Effort: 2-3 days
  - Impact: Correct bracket behavior across league formats
  - Tracking: GitHub issue [#154](https://github.com/NPGrant81/fantasy-football-pi/issues/154)
2. **Theme polish follow-up** - Improve light/dark readability and contrast
  - Effort: 0.5-1 day
  - Impact: Better accessibility and visual consistency
  - Tracking: GitHub issue [#75](https://github.com/NPGrant81/fantasy-football-pi/issues/75)

### P2 (Medium Priority)

3. **Story 6.2 follow-up** - Dynamic commissioner-settings bracket structure
  - Effort: 2-3 days
  - Impact: Correct bracket behavior across league formats
  - Tracking: GitHub issue [#154](https://github.com/NPGrant81/fantasy-football-pi/issues/154)

4. **Quality hardening sweep** - Edge-case tests and docs governance
  - Effort: 2-4 days
  - Impact: Lower regression risk and cleaner contributor pathways
  - Tracking: GitHub issues [#43](https://github.com/NPGrant81/fantasy-football-pi/issues/43), [#100](https://github.com/NPGrant81/fantasy-football-pi/issues/100), [#155](https://github.com/NPGrant81/fantasy-football-pi/issues/155), [#156](https://github.com/NPGrant81/fantasy-football-pi/issues/156)

### P3 (Low Priority / Polish)

5. **Story 7.2** - Dark/Light mode toggle
6. **Story 1.2** - Historical data archiving

---

## READY TO CLOSE (When PR merged)

- Story 5.1: Free Agent Search ✅
- Story 2.1-2.3: Draft System ✅
- Story 4.2-4.4: Scoring Management ✅
- Story 5.2-5.4: Waiver System ✅
- Story 3.1: Team Customization ✅
- Story 6 (Core): Matchups ✅
- Story 0.1: Docker/Postgres Setup ✅

**Action:** Link this ISSUE_STATUS.md to a summary comment on each GitHub issue or create a tracking project for remaining work.
