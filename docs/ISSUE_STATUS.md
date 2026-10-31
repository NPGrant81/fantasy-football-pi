# GitHub Issues Status Report
**Date:** October 31, 2026


**Current GitHub snapshot:** 118 open issues as of October 31, 2026. The open-issue register at the end of this report is authoritative for issue state, priority, workflow labels, and last-updated date.

---

## Documentation Governance Sweep Updates

- **Issue #156 pass 3 (2026-05-05):** Completed docs freshness sweep for API/deployment/process governance docs.
- **Key outputs:** Updated API base URL guidance, added governance tracker links in operational docs, expanded doc-to-issue map, and archived pass-3 sweep report at `docs/archive/MARKDOWN_GOVERNANCE_SWEEP_REPORT_2026-05-05.md`.
- **Guardrail confirmation:** Documentation-only changes; no architecture change and no regression to March baseline behavior.

## Resolved Issue Closure Queue (New Standard)

- **Issue #81**: `Phase 1: Raspberry Pi OS Setup`
  - **Implementation Status:** Resolved in current branch via Raspberry Pi Phase 1 runbook updates
  - **GitHub Status:** Closed (March 19, 2026) with close-out comment
  - **Close-Out Notes:** Captured in `docs/PR_NOTES.md` under `Issue #81 Close-Out Notes`

- **Issue #131**: `Create Dedicated Draft Day Analyzer Page + Fix Advisor & Simulation Failures`
  - **Implementation Status:** Resolved in `feature/scoring-integration-analytics`
  - **GitHub Status:** Closed (March 8, 2026) with close-out comment
  - **Close-Out Notes:** Captured in `docs/PR_NOTES.md` under `Issue #131 Close-Out Notes`
- **Issue #19**: `Story 5.3: Waiver Processing Logic Description`
  - **Implementation Status:** Resolved in current waiver system implementation
  - **GitHub Status:** Closed (March 8, 2026) with close-out comment
  - **Close-Out Notes:** Captured in `docs/PR_NOTES.md` under `Bulk Close Comment Pack (Resolved Open Issues)`
- **Issue #20**: `Story 5.4: Waiver Result Notifications Description`
  - **Implementation Status:** Resolved in current waiver notification flow
  - **GitHub Status:** Closed (March 8, 2026) with close-out comment
  - **Close-Out Notes:** Captured in `docs/PR_NOTES.md` under `Bulk Close Comment Pack (Resolved Open Issues)`
- **Issue #31**: `Waiver Wire Rules: Page Setup & Navigation`
  - **Implementation Status:** Resolved in commissioner waiver-rules page rollout
  - **GitHub Status:** Closed (March 8, 2026) with close-out comment
  - **Close-Out Notes:** Captured in `docs/PR_NOTES.md` under `Bulk Close Comment Pack (Resolved Open Issues)`
- **Issue #32**: `Waiver Wire Rules: Configuration Form`
  - **Implementation Status:** Resolved in commissioner waiver-rules configuration UI
  - **GitHub Status:** Closed (March 8, 2026) with close-out comment
  - **Close-Out Notes:** Captured in `docs/PR_NOTES.md` under `Bulk Close Comment Pack (Resolved Open Issues)`
- **Issue #33**: `Waiver Wire Rules: Transactions History & Audit`
  - **Implementation Status:** Resolved in waiver history/audit surfaces
  - **GitHub Status:** Closed (March 8, 2026) with close-out comment
  - **Close-Out Notes:** Captured in `docs/PR_NOTES.md` under `Bulk Close Comment Pack (Resolved Open Issues)`
- **Issue #34**: `Waiver Wire Rules: Backend Integration`
  - **Implementation Status:** Resolved in waiver backend/router/service integration
  - **GitHub Status:** Closed (March 8, 2026) with close-out comment
  - **Close-Out Notes:** Captured in `docs/PR_NOTES.md` under `Bulk Close Comment Pack (Resolved Open Issues)`
- **Issue #35**: `Waiver Wire Rules: Testing`
  - **Implementation Status:** Resolved for current waiver baseline and CI workflow
  - **GitHub Status:** Closed (March 8, 2026) with close-out comment
  - **Close-Out Notes:** Captured in `docs/PR_NOTES.md` under `Bulk Close Comment Pack (Resolved Open Issues)`
- **Issue #186**: `Bug Report System Cannot Create GitHub Issues (GitHub App Credentials Not Configured)`
  - **Implementation Status:** Resolved in `feature/scoring-integration-analytics`
  - **GitHub Status:** Closed (March 8, 2026) with close-out comment
  - **Close-Out Notes:** Captured in `docs/PR_NOTES.md` under `Issue #186 Close-Out Notes`
- **Issue #187**: `Improve Bug Report UI to Display GitHub Issue Link and Better Error Handling`
  - **Implementation Status:** Resolved in `feature/scoring-integration-analytics`
  - **GitHub Status:** Closed (March 8, 2026) with close-out comment
  - **Close-Out Notes:** Captured in `docs/PR_NOTES.md` under `Issue #187 Close-Out Notes`
- **Issue #188**: `Add Support for Mermaid Diagrams in Markdown (MD) Across the Platform`
  - **Implementation Status:** Resolved in `feature/scoring-integration-analytics` via merged PR #191 commits
  - **GitHub Status:** Closed (March 8, 2026) with close-out comment
  - **Close-Out Notes:** Captured in `docs/PR_NOTES.md` under `Issue #188 Close-Out Notes`

### Issue Hygiene Protocol

- When work is complete in code, add the issue to this queue immediately.
- Post a close-out comment with verification summary, then close the GitHub issue.
- If closure cannot be completed in the same session, keep an explicit `Pending` entry here to avoid duplicate net-new issue creation.
- During sprint planning, treat `Pending` items as administrative closure tasks first, before creating new overlapping issues.

### Issue Status Transition Standard (New)

- Canonical flow for active work: `To Do` -> `In Progress` -> `Complete`.
- Move an issue to `In Progress` as soon as implementation begins (code, tests, or docs changes linked to the issue).
- Move an issue to `Complete` only after acceptance criteria and validation evidence are recorded.
- Do not keep actively implemented items in `To Do`.
- If work pauses or scope splits, keep the original issue at `In Progress` and link any carryover issue explicitly.

#### Required evidence at each transition

- `To Do` -> `In Progress`
  - Working branch/PR reference added to issue comments or body.
  - Initial implementation note posted (what started, expected scope).
- `In Progress` -> `Complete`
  - Validation summary posted (tests, smoke checks, or manual verification).
  - PR/commit references posted.
  - Issue moved to closure queue with close-out note link when applicable.

---


## ✅ COMPLETED STORIES

### Story 5.1: Free Agent Search

- **Status:** ✅ COMPLETED
- **Frontend:** [WaiverWire.jsx](frontend/src/pages/WaiverWire.jsx) - Search and display with filtering
- **Backend:** `GET /players/search` endpoint fully implemented
- **Details:** Users can search for and view free agent players, filter by position, sort by points
- **Verification:** All acceptance criteria met


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
- **Frontend:** [WaiverWire.jsx](frontend/src/pages/WaiverWire.jsx) with bid management; new `WaiverRules.jsx` and commissioner pages for rules/budgets
- **Backend:** `/waivers` router with processing logic, notifications, blind bidding; `/leagues/{id}/settings` supports new budget/system/tiebreaker fields; `/leagues/{id}/waiver-budgets` endpoint added
- **Details:** Full waiver processing with blind bid management, result notifications, and commissioner‑configurable budgets/rules
- **Verification:** Waivers processed on schedule, results posted; rules editable by commissioner; budget data accessible

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
- **Notes:** Full feedback form implemented on `/bug-report`; backend persists reports, creates GitHub issues using PAT-first auth with App fallback, and records user email. UX includes loading/success/warning/error states and retry support.
- **Complexity:** Low - form + email/storage

### Story 1.2: Historical Data Archiving

- **Status:** ✅ COMPLETED (Initial Scope)
- **Priority:** Low
- **Notes:** Story issue `#6` is closed. Additional historical pipeline work continues under newer issues (for example `#286`, `#288`, and `#341` for League 60 historical owner identity backfill).
- **Complexity:** Medium - migration and cleanup scripts

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

---

## CURRENT GITHUB ISSUE STATUS

**Snapshot date:** 2026-10-31. GitHub currently reports 118 open issues. This is a point-in-time register, not a claim that every open issue is actively being worked.

| Priority label | Open issues |
| --- | ---: |
| P0 | 2 |
| P1 | 54 |
| P2 | 50 |
| P3 | 10 |
| No priority label | 2 |

| Workflow label | Open issues |
| --- | ---: |
| `status:ready` | 38 |
| `status:blocked` | 14 |
| No explicit ready/blocked label | 66 |

GitHub's open/closed state is the issue status of record. `status:ready` and `status:blocked` are explicit workflow labels; where neither is present, this report does not infer that work is in progress. Labels below are captured as-is and may need triage when an issue is revisited.

### Related current workstreams

- **CI and deployment reliability:** #519–#522 remain open; the #519 epic tracks configuration-aware workflows and deploy gates.
- **Historical data integrity:** #523 and #524–#529 remain open; #529 is marked blocked, while the other listed issues are marked ready.
- **Application stabilization:** #531–#538 remain open. The semantic data-layer issue #540 is also open and is scoped to a shared contract, with existing data-contract and schema work explicitly kept in their current workstreams.
- **Data contracts and league-rule propagation:** #398–#400 remain open as the existing Layer A–C epics.

### Open issue register

| Issue | Title | Priority | Workflow label | Other labels | Updated |
| --- | --- | --- | --- | --- | --- |
| [#54](https://github.com/NPGrant81/fantasy-football-pi/issues/54) | [FRONTEND] Analytics Charts — Phase 1: Build with Mock Data | priority:P2 | none | frontend, analytics | 2026-08-30 |
| [#55](https://github.com/NPGrant81/fantasy-football-pi/issues/55) | Weekly Matchup Comparison Chart — Mock Data Phase | priority:P2 | none | frontend, analytics | 2026-08-30 |
| [#75](https://github.com/NPGrant81/fantasy-football-pi/issues/75) | Improve Color Contrast for Light/Dark Mode Theme | priority:P2 | none | enhancement, frontend | 2026-08-30 |
| [#78](https://github.com/NPGrant81/fantasy-football-pi/issues/78) | Cross‑Platform Development & Deployment Strategy (Windows → Raspberry Pi) | priority:P1 | none | devops, deployment | 2026-08-30 |
| [#79](https://github.com/NPGrant81/fantasy-football-pi/issues/79) | Unified Architecture, Security, and Cross‑Platform Development Strategy | priority:P1 | none | devops, security, deployment | 2026-08-30 |
| [#84](https://github.com/NPGrant81/fantasy-football-pi/issues/84) | Phase 4: Project Deployment | priority:P2 | none | devops, deployment | 2026-08-30 |
| [#92](https://github.com/NPGrant81/fantasy-football-pi/issues/92) | League Analytics — Navigation Buttons, Player Interaction, Layout Cleanup, and Visual Consistency | priority:P2 | none | frontend, analytics | 2026-08-30 |
| [#98](https://github.com/NPGrant81/fantasy-football-pi/issues/98) | Integration Test: End Draft Workflow (Commissioner → System‑Wide Updates) | priority:P1 | none | Backend, frontend, devops, testing | 2026-08-30 |
| [#99](https://github.com/NPGrant81/fantasy-football-pi/issues/99) | Integration Test: Submit Lineups (Team Page → Matchup Page, Current & Future Weeks) | priority:P1 | none | frontend, testing | 2026-08-30 |
| [#101](https://github.com/NPGrant81/fantasy-football-pi/issues/101) | UI/UX & Backend: UAT Isolation Model & Fast-Forward Controls | priority:P1 | none | Backend, frontend | 2026-08-30 |
| [#108](https://github.com/NPGrant81/fantasy-football-pi/issues/108) | ML Model Training & Evaluation Pipeline | priority:P2 | none | Machine Learning, analytics | 2026-08-30 |
| [#109](https://github.com/NPGrant81/fantasy-football-pi/issues/109) | Model Serving & Integration with PPL Draft Analyzer | priority:P2 | status:blocked | Machine Learning, analytics | 2026-08-30 |
| [#111](https://github.com/NPGrant81/fantasy-football-pi/issues/111) | Draft Day Mode with Chatbot Integration | priority:P3 | status:blocked | Machine Learning, analytics | 2026-08-30 |
| [#112](https://github.com/NPGrant81/fantasy-football-pi/issues/112) | Post-Draft Analysis & Season Outlook | priority:P2 | status:blocked | Machine Learning, analytics | 2026-08-30 |
| [#120](https://github.com/NPGrant81/fantasy-football-pi/issues/120) | Implement League Divisions (Configuration, UI, ML Balancing, Playoffs, History) | priority:P2 | none | frontend | 2026-08-30 |
| [#132](https://github.com/NPGrant81/fantasy-football-pi/issues/132) | Remove Keepers & Ledger from Sidebar Navigation | priority:P2 | none | enhancement, frontend | 2026-08-30 |
| [#150](https://github.com/NPGrant81/fantasy-football-pi/issues/150) | GitHub Issue Draft — UAT Overview + UAT Master Tester Onboarding | priority:P1 | none | testing | 2026-08-30 |
| [#153](https://github.com/NPGrant81/fantasy-football-pi/issues/153) | Valuation Model Specification | priority:P2 | none | Backend, analytics | 2026-08-30 |
| [#155](https://github.com/NPGrant81/fantasy-football-pi/issues/155) | Quality Sweep: Cross-Module Edge-Case Test Matrix (Beyond #43 and #100) | priority:P1 | none | Backend, devops | 2026-08-30 |
| [#156](https://github.com/NPGrant81/fantasy-football-pi/issues/156) | Documentation Governance Sweep: Staleness, Directive Drift, and Issue Correlation | priority:P2 | none | documentation, devops, docs | 2026-08-30 |
| [#157](https://github.com/NPGrant81/fantasy-football-pi/issues/157) | Trade Analyzer – UI Wireframe Acceptance Criteria | priority:P2 | none | Backend, frontend, analytics | 2026-08-30 |
| [#165](https://github.com/NPGrant81/fantasy-football-pi/issues/165) | Enhance Propose Trade Workflow (Multi‑Player Support + Trade Analyzer Integration) | priority:P2 | none | enhancement, Backend, frontend, analytics | 2026-08-30 |
| [#178](https://github.com/NPGrant81/fantasy-football-pi/issues/178) | Issue: Add Documentation & UI Explanations for Scoring Rule Types, Terminology, and Logic Application | priority:P2 | none | enhancement, Backend, frontend, database | 2026-08-30 |
| [#182](https://github.com/NPGrant81/fantasy-football-pi/issues/182) | Add Export to CSV/XLSX for Simulation Results | priority:P3 | none | enhancement, Backend, frontend, analytics | 2026-08-30 |
| [#183](https://github.com/NPGrant81/fantasy-football-pi/issues/183) | Add Simulation Results Explainer Panel / Tooltips | priority:P3 | none | enhancement, Backend, frontend, analytics | 2026-08-30 |
| [#184](https://github.com/NPGrant81/fantasy-football-pi/issues/184) | Add Total Spend + Positional Spend to Simulation Output and UI | priority:P2 | none | enhancement, Backend, frontend, analytics | 2026-08-30 |
| [#185](https://github.com/NPGrant81/fantasy-football-pi/issues/185) | Confirm Simulation Results Are Not Persisted in Database (Architecture Check) | priority:P1 | none | enhancement, Backend, frontend, analytics | 2026-08-30 |
| [#239](https://github.com/NPGrant81/fantasy-football-pi/issues/239) | Add “League Champions” Modal to Homepage | priority:P2 | none | enhancement, frontend | 2026-08-30 |
| [#255](https://github.com/NPGrant81/fantasy-football-pi/issues/255) | Data Migration – League History Reports (Export → Transform → Import) | priority:P2 | status:ready | documentation, Backend, database, data-migration | 2026-10-09 |
| [#256](https://github.com/NPGrant81/fantasy-football-pi/issues/256) | Define Data Requirements & Schemas | priority:P2 | status:ready | Backend, database, data-migration | 2026-08-30 |
| [#257](https://github.com/NPGrant81/fantasy-football-pi/issues/257) | Build Extraction API (Legacy → CSV) | priority:P2 | none | Backend, database, data-migration | 2026-08-30 |
| [#258](https://github.com/NPGrant81/fantasy-football-pi/issues/258) | Implement CSV Import Pipeline (CSV → New App) | priority:P2 | none | Backend, database, data-migration | 2026-08-30 |
| [#259](https://github.com/NPGrant81/fantasy-football-pi/issues/259) | Data Integrity & Reconciliation | priority:P2 | none | Backend, database, data-migration | 2026-08-30 |
| [#260](https://github.com/NPGrant81/fantasy-football-pi/issues/260) | Migration Workflow & Documentation | priority:P2 | none | Backend, database, data-migration | 2026-08-30 |
| [#262](https://github.com/NPGrant81/fantasy-football-pi/issues/262) | Live Scoring Integration (ESPN API → Normalized Game Data → Real‑Time Updates) | priority:P1 | status:ready | Backend, devops, database | 2026-08-30 |
| [#263](https://github.com/NPGrant81/fantasy-football-pi/issues/263) | 1. ESPN API Discovery & Data Contract Definition | priority:P1 | status:ready | Backend, devops, database | 2026-08-30 |
| [#264](https://github.com/NPGrant81/fantasy-football-pi/issues/264) | 2. Backend Ingestion Layer | priority:P1 | status:blocked | Backend, devops, database | 2026-08-30 |
| [#265](https://github.com/NPGrant81/fantasy-football-pi/issues/265) | 3. Polling & Scheduling | priority:P1 | status:blocked | Backend, devops, database | 2026-08-30 |
| [#266](https://github.com/NPGrant81/fantasy-football-pi/issues/266) | 4. Fantasy Scoring Engine Integration | priority:P1 | status:blocked | Backend, devops, database | 2026-08-30 |
| [#267](https://github.com/NPGrant81/fantasy-football-pi/issues/267) | 5. Real‑Time Update Delivery | priority:P1 | status:blocked | Backend, devops, database | 2026-08-30 |
| [#268](https://github.com/NPGrant81/fantasy-football-pi/issues/268) | 6. Data Persistence & History | priority:P1 | status:blocked | Backend, devops, database | 2026-08-30 |
| [#269](https://github.com/NPGrant81/fantasy-football-pi/issues/269) | 7. Monitoring & Observability | priority:P1 | status:blocked | Backend, devops, database, observability | 2026-08-30 |
| [#270](https://github.com/NPGrant81/fantasy-football-pi/issues/270) | 8. Documentation & Developer Workflow | priority:P1 | status:blocked | Backend, devops, database | 2026-08-30 |
| [#288](https://github.com/NPGrant81/fantasy-football-pi/issues/288) | Implement Year‑End Data Rollup Pipeline for Historical League Records | priority:P2 | none | enhancement, Backend, database, data-migration | 2026-08-30 |
| [#290](https://github.com/NPGrant81/fantasy-football-pi/issues/290) | Pre-Deploy Raspberry Pi Host Foundation Checklist (Packages, Hardening, Service Readiness) | priority:P1 | none | enhancement, devops, security, deployment | 2026-08-30 |
| [#297](https://github.com/NPGrant81/fantasy-football-pi/issues/297) | Post-merge operational closeout: manual draft backfill + import/reconcile evidence | priority:P2 | none | Backend, database, data-migration | 2026-08-30 |
| [#298](https://github.com/NPGrant81/fantasy-football-pi/issues/298) | Raspberry Pi production cutover readiness | priority:P1 | none | Backend, devops, docs, deployment, observability | 2026-09-23 |
| [#300](https://github.com/NPGrant81/fantasy-football-pi/issues/300) | Dockerize the App + Configure systemd + Nginx Reverse Proxy | priority:P2 | none | enhancement, devops, deployment | 2026-08-30 |
| [#301](https://github.com/NPGrant81/fantasy-football-pi/issues/301) | Implement Dead/Stale Code Detection & Pruning System | priority:P3 | none | enhancement, Backend, devops | 2026-08-30 |
| [#302](https://github.com/NPGrant81/fantasy-football-pi/issues/302) | Clarify Architecture — Is the App Containerized or Microserviced? | priority:P2 | none | devops, docs, deployment | 2026-08-30 |
| [#305](https://github.com/NPGrant81/fantasy-football-pi/issues/305) | Pi cutover remaining work after Docker baseline | priority:P1 | none | Backend, devops, docs, deployment | 2026-08-30 |
| [#307](https://github.com/NPGrant81/fantasy-football-pi/issues/307) | Integration Test: Commissioner Settings Propagation (Non-Scoring Rules) | priority:P2 | none | Backend, frontend, testing | 2026-08-30 |
| [#308](https://github.com/NPGrant81/fantasy-football-pi/issues/308) | Documentation Governance Follow-Up: Stale/Conflicting Instruction Cleanup Pipeline | priority:P3 | none | enhancement, docs | 2026-08-30 |
| [#335](https://github.com/NPGrant81/fantasy-football-pi/issues/335) | Governance Steady State: docs classification, cadence, and drift prevention | priority:P3 | none | enhancement, docs | 2026-08-30 |
| [#342](https://github.com/NPGrant81/fantasy-football-pi/issues/342) | War Room Enhancements — Undo Draft, Permissions, Session Controls, Timer, and UI Consolidation | priority:P2 | none | enhancement | 2026-08-30 |
| [#343](https://github.com/NPGrant81/fantasy-football-pi/issues/343) | Trade System Overhaul — Timeline, Approval Workflow, Future Draft Capital, and Email Notifications | priority:P1 | none | enhancement, Backend, frontend, database, epic | 2026-08-30 |
| [#360](https://github.com/NPGrant81/fantasy-football-pi/issues/360) | [ML Program] #103-#111 Execution Tracker and Risk Matrix | priority:P2 | none | Machine Learning, analytics | 2026-08-30 |
| [#361](https://github.com/NPGrant81/fantasy-football-pi/issues/361) | [Phase 1] #103 Implementation: Canonical Player Metadata Pipeline + Gate Evidence | priority:P2 | none | Machine Learning, analytics | 2026-08-30 |
| [#362](https://github.com/NPGrant81/fantasy-football-pi/issues/362) | [Phase 1] #104 Implementation: Owner Budget Timeline + Behavior Feature Prep | priority:P2 | none | Machine Learning, analytics | 2026-08-30 |
| [#370](https://github.com/NPGrant81/fantasy-football-pi/issues/370) | Epic: Test-First Delivery + Local Pre-PR Gates | priority:P2 | status:ready | enhancement, testing, epic | 2026-08-30 |
| [#375](https://github.com/NPGrant81/fantasy-football-pi/issues/375) | Phase 4: Load, resilience, and security test lanes | priority:P2 | status:ready | enhancement, testing, security, performance | 2026-08-30 |
| [#376](https://github.com/NPGrant81/fantasy-football-pi/issues/376) | Phase 5: Testing governance cadence | priority:P3 | status:ready | enhancement, testing | 2026-08-30 |
| [#396](https://github.com/NPGrant81/fantasy-football-pi/issues/396) | Refresh Cloudflare-based deployment strategy for Raspberry Pi production | priority:P1 | status:ready | enhancement, devops, docs, deployment | 2026-08-30 |
| [#398](https://github.com/NPGrant81/fantasy-football-pi/issues/398) | Epic: Layer A — External Data Contract Adapters | priority:P1 | status:ready | Backend, devops, epic | 2026-08-30 |
| [#399](https://github.com/NPGrant81/fantasy-football-pi/issues/399) | Epic: Layer B — League Settings Propagation Service | priority:P1 | status:ready | enhancement, Backend, epic | 2026-08-30 |
| [#400](https://github.com/NPGrant81/fantasy-football-pi/issues/400) | Epic: Layer C — Graceful Degradation + Schema Drift Guards | priority:P1 | status:ready | Backend, devops, testing, epic | 2026-08-30 |
| [#402](https://github.com/NPGrant81/fantasy-football-pi/issues/402) | Epic: Production Security Hardening Program for External Hosting | priority:P1 | none | enhancement, epic, security | 2026-08-30 |
| [#407](https://github.com/NPGrant81/fantasy-football-pi/issues/407) | [Security][#402] Remove Token Storage from Browser Storage | priority:P1 | status:ready | enhancement, frontend, epic, security | 2026-08-30 |
| [#410](https://github.com/NPGrant81/fantasy-football-pi/issues/410) | [Security][#402] API PII Exposure Audit + Response Hardening | priority:P1 | status:ready | enhancement, Backend, testing, epic, security | 2026-08-30 |
| [#411](https://github.com/NPGrant81/fantasy-football-pi/issues/411) | [Security][#402] Tighten CORS Header Policy | priority:P1 | status:ready | enhancement, Backend, epic, security | 2026-08-30 |
| [#413](https://github.com/NPGrant81/fantasy-football-pi/issues/413) | [Security][#402] HTTPS Enforcement + HSTS Preload Decision | priority:P1 | status:ready | enhancement, devops, docs, epic, security, deployment | 2026-08-30 |
| [#418](https://github.com/NPGrant81/fantasy-football-pi/issues/418) | [Security][#402] Dependabot + Dependency Vulnerability Automation | priority:P1 | status:ready | enhancement, Backend, frontend, devops, epic, security | 2026-08-30 |
| [#430](https://github.com/NPGrant81/fantasy-football-pi/issues/430) | perf: fix N+1 query pattern in update_rosters.py | priority:P2 | none | enhancement, Backend, database, performance | 2026-08-30 |
| [#431](https://github.com/NPGrant81/fantasy-football-pi/issues/431) | perf: fix N+1 query pattern in trade_service.py keeper update | priority:P2 | none | enhancement, Backend, database, performance | 2026-08-30 |
| [#432](https://github.com/NPGrant81/fantasy-football-pi/issues/432) | perf: add missing database indexes for hot query columns | priority:P2 | none | enhancement, database, performance | 2026-08-30 |
| [#433](https://github.com/NPGrant81/fantasy-football-pi/issues/433) | perf: background-task blocking model prediction and Monte Carlo simulation endpoints | priority:P1 | none | enhancement, Backend, Machine Learning, performance, analytics | 2026-08-30 |
| [#434](https://github.com/NPGrant81/fantasy-football-pi/issues/434) | perf: add in-process cache for frequently-read, rarely-changing queries | priority:P2 | none | enhancement, Backend, performance | 2026-08-30 |
| [#435](https://github.com/NPGrant81/fantasy-football-pi/issues/435) | perf: replace manual fetch/useEffect with TanStack Query (React Query) for server state | priority:P3 | none | enhancement, frontend, performance | 2026-08-30 |
| [#451](https://github.com/NPGrant81/fantasy-football-pi/issues/451) | feat(#103 Phase 3): ETL write-back — populate canonical_player_snapshots from canonicalization pipeline | priority:P2 | none | enhancement, Backend, Machine Learning, analytics, data-migration | 2026-08-30 |
| [#452](https://github.com/NPGrant81/fantasy-football-pi/issues/452) | feat(#103): Expose Position registry via API endpoint + frontend consumption | priority:P2 | none | enhancement, Backend, frontend, analytics | 2026-08-30 |
| [#455](https://github.com/NPGrant81/fantasy-football-pi/issues/455) | feat: resolve new-season player position gaps in draft validator (annual recurring) | priority:P1 | none | enhancement, etl, data-quality, analytics, data-migration | 2026-08-30 |
| [#475](https://github.com/NPGrant81/fantasy-football-pi/issues/475) | Ops: League 60 container data sync + Windows parity validation | priority:P1 | none | deployment, data-migration | 2026-08-30 |
| [#478](https://github.com/NPGrant81/fantasy-football-pi/issues/478) | Docs Governance Sweep Failure | priority:P3 | none | — | 2026-10-26 |
| [#484](https://github.com/NPGrant81/fantasy-football-pi/issues/484) | refactor(scripts): eliminate remaining import-time database side effects | priority:P1 | status:ready | — | 2026-08-30 |
| [#485](https://github.com/NPGrant81/fantasy-football-pi/issues/485) | Blind Bidding System | priority:P2 | none | — | 2026-08-30 |
| [#491](https://github.com/NPGrant81/fantasy-football-pi/issues/491) | Code-review agent skill | priority:P3 | status:blocked | — | 2026-08-30 |
| [#492](https://github.com/NPGrant81/fantasy-football-pi/issues/492) | docs(governance): reconcile standards inventory and promote emerging contracts | priority:P1 | status:ready | — | 2026-08-30 |
| [#493](https://github.com/NPGrant81/fantasy-football-pi/issues/493) | docs(governance): replace dead sweep targets and map successors | priority:P2 | status:ready | — | 2026-08-30 |
| [#494](https://github.com/NPGrant81/fantasy-football-pi/issues/494) | docs(architecture): consolidate canonical authority and terminology | priority:P1 | status:blocked | — | 2026-08-30 |
| [#495](https://github.com/NPGrant81/fantasy-football-pi/issues/495) | docs(database): codify deterministic startup migration lifecycle | priority:P1 | status:blocked | deployment | 2026-08-30 |
| [#496](https://github.com/NPGrant81/fantasy-football-pi/issues/496) | docs(ui): align standards, skills, and runtime token contracts | priority:P2 | status:ready | — | 2026-08-30 |
| [#497](https://github.com/NPGrant81/fantasy-football-pi/issues/497) | docs(dependencies): align maintenance policy with automated controls | priority:P2 | status:ready | security | 2026-08-30 |
| [#498](https://github.com/NPGrant81/fantasy-football-pi/issues/498) | docs(governance): establish FMEA and 5S successor ownership | priority:P2 | status:ready | — | 2026-08-30 |
| [#499](https://github.com/NPGrant81/fantasy-football-pi/issues/499) | docs(governance): complete overdue standards reviews with evidence | priority:P2 | status:ready | — | 2026-08-30 |
| [#500](https://github.com/NPGrant81/fantasy-football-pi/issues/500) | docs(architecture): reconcile architecture drift and promote current runtime contracts | priority:P0 | status:ready | — | 2026-10-31 |
| [#502](https://github.com/NPGrant81/fantasy-football-pi/issues/502) | chore(database): reconcile legacy and canonical Alembic inventories | priority:P0 | status:ready | — | 2026-09-02 |
| [#504](https://github.com/NPGrant81/fantasy-football-pi/issues/504) | test(database): enforce bootstrap and incremental schema equivalence | priority:P1 | status:ready | — | 2026-08-30 |
| [#508](https://github.com/NPGrant81/fantasy-football-pi/issues/508) | ci(database): test migration-backed E2E and established-database upgrades | priority:P1 | status:ready | deployment | 2026-08-30 |
| [#519](https://github.com/NPGrant81/fantasy-football-pi/issues/519) | ci: make scheduled workflows configuration-aware and keep main deployable | priority:P1 | status:ready | epic, security, release-blocker, deployment, area:ci | 2026-10-01 |
| [#520](https://github.com/NPGrant81/fantasy-football-pi/issues/520) | ci: require immutable verified refs for deployment | priority:P1 | status:ready | release-blocker, deployment, area:security, area:ci | 2026-10-01 |
| [#521](https://github.com/NPGrant81/fantasy-football-pi/issues/521) | security: remediate frontend audit findings and automate updates | priority:P1 | status:ready | security, release-blocker, area:frontend, area:security, area:dependencies | 2026-10-01 |
| [#522](https://github.com/NPGrant81/fantasy-football-pi/issues/522) | ci: add configuration-aware workflow integration contracts | priority:P1 | status:ready | testing, release-blocker, deployment, area:ci | 2026-10-01 |
| [#523](https://github.com/NPGrant81/fantasy-football-pi/issues/523) | epic(database): Hardening Historical League & Ingestion SQL Data Models for Referential & Ingestion Integrity | priority:P1 | status:ready | Backend, database, epic, etl, data-quality | 2026-10-09 |
| [#524](https://github.com/NPGrant81/fantasy-football-pi/issues/524) | feat(database): Add idempotency unique constraints and indexes to draft_picks and transaction_history | priority:P1 | status:ready | Backend, database, data-quality | 2026-10-03 |
| [#525](https://github.com/NPGrant81/fantasy-football-pi/issues/525) | feat(database): Update waiver_budgets composite unique constraint to support multi-season history | priority:P1 | status:ready | Backend, database, data-quality | 2026-10-03 |
| [#526](https://github.com/NPGrant81/fantasy-football-pi/issues/526) | feat(database): Add native mfl_id and sleeper_id provider identity columns to Player model | priority:P1 | status:ready | Backend, database, etl, data-quality | 2026-10-09 |
| [#527](https://github.com/NPGrant81/fantasy-football-pi/issues/527) | feat(database): Add is_historical_stub flag to users table and classify historical archive accounts | priority:P1 | status:ready | Backend, database, security | 2026-10-03 |
| [#528](https://github.com/NPGrant81/fantasy-football-pi/issues/528) | chore(database): Author Alembic migration and update ORM models with schema readiness parity | priority:P1 | status:ready | Backend, database | 2026-10-09 |
| [#529](https://github.com/NPGrant81/fantasy-football-pi/issues/529) | Resolve 2004 MFL player identity ambiguities and apply PlayerSeason import | priority:P1 | status:blocked | etl, data-quality, data-migration | 2026-10-09 |
| [#531](https://github.com/NPGrant81/fantasy-football-pi/issues/531) | epic: stabilize application wiring, quality gates and operational readiness | priority:P1 | none | epic | 2026-10-30 |
| [#532](https://github.com/NPGrant81/fantasy-football-pi/issues/532) | fix(ingress): align API proxy ownership and preserve SPA reloads | priority:P1 | none | bug, devops | 2026-10-30 |
| [#533](https://github.com/NPGrant81/fantasy-football-pi/issues/533) | ci(frontend): require the full regression suite instead of smoke-only coverage | priority:P1 | none | devops, testing | 2026-10-30 |
| [#534](https://github.com/NPGrant81/fantasy-football-pi/issues/534) | fix(waivers): connect commissioner claim history and surface request failures | priority:P2 | none | bug, frontend | 2026-10-30 |
| [#535](https://github.com/NPGrant81/fantasy-football-pi/issues/535) | test(frontend): exercise real query failure and cache-invalidation behavior | priority:P2 | none | frontend, testing | 2026-10-30 |
| [#536](https://github.com/NPGrant81/fantasy-football-pi/issues/536) | fix(ci): restore executable accessibility and UI automation checks | priority:P2 | none | bug, devops, testing | 2026-10-30 |
| [#537](https://github.com/NPGrant81/fantasy-football-pi/issues/537) | fix(recovery): verify backup restoration in a disposable database | priority:P2 | none | devops, database, testing | 2026-10-30 |
| [#538](https://github.com/NPGrant81/fantasy-football-pi/issues/538) | test(ui): replace no-op screenshot baseline check with visual comparison | unprioritized | none | — | 2026-10-30 |
| [#540](https://github.com/NPGrant81/fantasy-football-pi/issues/540) | feat(data): establish a shared semantic data layer | unprioritized | status:ready | Backend, database, data-quality, analytics | 2026-10-31 |

The story and infrastructure sections above are retained as historical implementation notes. Check the live issue before treating those notes as current delivery status; use the register above for the current GitHub state.
