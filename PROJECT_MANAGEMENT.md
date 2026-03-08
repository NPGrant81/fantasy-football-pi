# Project Management

**Date:** February 20, 2026  
**Branch:** main

---

## Issue Hygiene (Resolved vs Open)

To avoid confusion between completed scope and net-new backlog:

- Mark implementation-complete items in `docs/ISSUE_STATUS.md` under `Resolved Issue Closure Queue`.
- Post close-out notes and close the GitHub issue promptly after verification.
- Keep unresolved administrative closures explicitly marked as `Pending` until closed.
- Clear pending closure items before creating new issues for the same problem area.
- Feed recurring break/fix patterns from `docs/CLI_CHECKIN_LESSONS_LEARNED.md` into planning and standards updates.
- Use issue `#156` as the governing tracker for markdown staleness and doc-to-issue correlation updates.

---

## 🗺️ PROJECT MILESTONES

The project is organized into 7 milestones that map development phases from foundation through Release 1.0.  
See [`docs/milestones/`](docs/milestones/README.md) for full milestone definitions, scope, and completion criteria.

| # | Milestone | Status |
|---|-----------|--------|
| 1 | [Core Application Foundation](docs/milestones/milestone-1-core-foundation.md) | 🔄 In Progress |
| 2 | [Cross‑Platform Compatibility & Deployment](docs/milestones/milestone-2-cross-platform-deployment.md) | ⏳ Planned |
| 3 | [Security Hardening](docs/milestones/milestone-3-security-hardening.md) | ⏳ Planned |
| 4 | [Data‑Validation Architecture](docs/milestones/milestone-4-data-validation.md) | ⏳ Planned |
| 5 | [Gameplay Logic & League Operations](docs/milestones/milestone-5-gameplay-logic.md) | 🔄 In Progress |
| 6 | [Production Readiness & Monitoring](docs/milestones/milestone-6-production-readiness.md) | ⏳ Planned |
| 7 | [Release 1.0](docs/milestones/milestone-7-release-1.0.md) | ⏳ Planned |

---

## 📖 STORY NUMBERING FRAMEWORK

This project uses **Agile Story numbering** to organize features and tasks with clear structure for VS Code file mapping and development sequencing.

### Story Format: `X.Y`

- **X** = Epic/Feature Area (Major category)
- **Y** = Sequence number within that epic (Order of creation or execution)

### Story Categories

| Story # | Epic/Feature Area                   | Description                                             |
| ------- | ----------------------------------- | ------------------------------------------------------- |
| **0.x** | **Backend DevOps & Infrastructure** | Docker, databases, deployment, monitoring, backups      |
| **1.x** | **Login & Authentication**          | User authentication, sessions, security                 |
| **2.x** | **Draft System**                    | Draft board, pick management, player selection          |
| **3.x** | **Team Management**                 | Team customization, roster management                   |
| **4.x** | **Scoring & Rules**                 | Scoring rules, league settings, commissioner tools      |
| **5.x** | **Free Agents & Waivers**           | Free agent search, waiver processing, blind bidding     |
| **6.x** | **Matchups & Standings**            | Game center, standings, playoff brackets                |
| **7.x** | **UI/UX & Polish**                  | Themes, accessibility, bug reporting                    |
| **8.x** | **Commissioner Tools**              | Advanced admin features, voting, rule management        |
| **9.x** | **Analytics & Visualizations**      | Python visualizations, Plotly/Chart.js, AI chat advisor |

### Sequence Logic (Y)

- **Sequential execution:** When stories must be done in order (e.g., 0.1 before 0.2)
- **Creation order:** When stories are independent but numbered by when they were created
- Use `.1, .2, .3...` to indicate granular sub-tasks within a feature

**Example:**

- `Story 0.1` = Install Docker & Postgres (must be done first)
- `Story 0.2` = Cloudflare Tunnel Setup (depends on 0.1)
- `Story 1.1` = Basic login form
- `Story 1.2` = Historical data archiving (independent, created later)

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

### Story 6: Matchups & Game Center (Core)

- **Status:** ✅ COMPLETED (Core Features)
- **Frontend:** [Matchups.jsx](frontend/src/pages/Matchups.jsx), [GameCenter.jsx](frontend/src/pages/GameCenter.jsx)
- **Backend:** `GET /matchups/week/{week_num}`, `GET /matchups/{matchup_id}`, matchups router
- **Details:** Week-by-week matchups with detailed game scoring
- **Verification:** Matchups display correctly, scores calculate

### Story 0.1: Install Docker & Postgres on Pi

- **Status:** ✅ COMPLETED
- **Details:**
  - docker-compose.yml configured with PostgreSQL
  - Backend running in Docker containers
  - Data persistence with volume mapping
  - Port 5432 accessible
- **Verification:** Services running, database persistent

---

## 🔄 PARTIALLY IMPLEMENTED

### Story 6.1: League Standings

- **Status:** 🔄 PARTIAL (60% complete)
- **Completed:** Basic standings table with Rank, Team, Owner display
- **Missing:**
  - W-L-T (Wins-Losses-Ties) column
  - PF (Points For) column
  - PA (Points Against) column
  - Sortable columns functionality
  - Backend API enhancement needed
- **Frontend:** [Home.jsx](frontend/src/pages/Home.jsx) - Basic table exists
- **Backend:** `/leagues/owners` returns only id, username, team_name (missing stats)
- **Next Steps:**
  1. Enhance `/leagues/owners` endpoint to return W-L-T, PF, PA stats
  2. Add sorting functionality to standings table
  3. Add missing columns to UI

### Story 6.3: Top Free Agents Module

- **Status:** 🔄 PARTIAL
- **Completed:** Free agent search and waiver wire display in [WaiverWire.jsx](frontend/src/pages/WaiverWire.jsx)
- **Missing:**
  - Top/Featured agents ranking algorithm
  - ADP (Average Draft Position) or pickup rate ranking
  - Dashboard widget for top pickups
- **Next Steps:** Implement ranking algorithm, add to dashboard

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

- **Status:** ❌ NOT STARTED
- **Priority:** Low
- **Notes:** UI enhancement - app currently dark-themed only
- **Complexity:** Medium - theme system implementation

### Story 7.3: Bug Reporting Form

- **Status:** ✅ COMPLETED
- **Priority:** Low
- **Notes:** Users can submit bug or feature reports via `/bug-report` page; backend stores entries and opens GitHub issues automatically (with warning on failure).
- **Complexity:** Low - form + email/storage

### Story 1.2: Historical Data Archiving

- **Status:** ❌ NOT STARTED
- **Priority:** Low
- **Notes:** Data retention and archive strategy for historical seasons
- **Complexity:** Medium - migration and cleanup scripts

---

## 🏗️ INFRASTRUCTURE TASKS (Story 0.x)

### Story 0.2: Cloudflare Tunnel Setup

- **Status:** ⏳ IN PROGRESS / OPTIONAL
- **Notes:** External access setup; local development functional
- **Blockers:** Requires domain name and Cloudflare account
- **Next Steps:** Domain setup (optional, not MVP-blocking)

### Story 0.3: Database Scheduled Backups

- **Status:** ⏳ IN PROGRESS / NOT REQUIRED YET
- **Notes:** Basic database working; backup scripts planned
- **Complexity:** Low - cron job + backup script

---

## 🆕 COMMISSIONER TOOLS (Story 8.x)

### Story 8.1: Commissioner - Waiver Wire Rules Page

- **GitHub Issues:** [#30](https://github.com/NPGrant81/fantasy-football-pi/issues/30) (Parent)
  - [#31](https://github.com/NPGrant81/fantasy-football-pi/issues/31) - Page Setup & Navigation
  - [#32](https://github.com/NPGrant81/fantasy-football-pi/issues/32) - Configuration Form
  - [#33](https://github.com/NPGrant81/fantasy-football-pi/issues/33) - Transactions History & Audit
  - [#34](https://github.com/NPGrant81/fantasy-football-pi/issues/34) - Backend Integration
  - [#35](https://github.com/NPGrant81/fantasy-football-pi/issues/35) - Testing
  - [#36](https://github.com/NPGrant81/fantasy-football-pi/issues/36) - Documentation
- **Status:** ⏳ PLANNED
- **Priority:** High
- **Details:** Commissioner UI to manage waiver rules, processing times, bidding settings

### Story 8.2: Commissioner - Scoring Rules Page

- **GitHub Issue:** [#37](https://github.com/NPGrant81/fantasy-football-pi/issues/37)
- **Status:** ⏳ PLANNED
- **Priority:** High
- **Details:** Flexible scoring configuration with CSV import, templates, and voting

### Story 8.3: Backend - Scoring Rules System Infrastructure

- **GitHub Issues:** [#38](https://github.com/NPGrant81/fantasy-football-pi/issues/38) (Parent)
  - [#39](https://github.com/NPGrant81/fantasy-football-pi/issues/39) - Database Schema
  - [#40](https://github.com/NPGrant81/fantasy-football-pi/issues/40) - API Endpoints
  - [#41](https://github.com/NPGrant81/fantasy-football-pi/issues/41) - Calculation Engine
  - [#42](https://github.com/NPGrant81/fantasy-football-pi/issues/42) - Data Migration & Import Tools
  - [#43](https://github.com/NPGrant81/fantasy-football-pi/issues/43) - Unit & Integration Testing
- **Status:** ⏳ PLANNED
- **Priority:** High
- **Details:** Backend foundation for flexible scoring rules, templates, and audit trails

---

## Draft Value Database & API Integration (Issue #56, #57)

Story: Create a database that pulls in information from source APIs (ESPN, Yahoo, Draftsharks) for fantasy football draft purposes.

Tasks:

- Design and implement draft value database/table
- Integrate API scripts for ESPN, Yahoo, Draftsharks
- Normalize and cleanse data for blending with player, draft, and team tables
- Expose draft value endpoints for frontend consumption
- Add UI components/pages for draft value analysis and player info
- Document data flow and ERD updates

---

## 📋 RECENT IMPROVEMENTS

### ✨ Login Form Enhancement

- **Commit:** `ee31db4` - "feat: add league ID input to login form with 'The Big Show' as default"
- **Change:** Modified login to accept league ID instead of league selection post-login
- **Impact:** League persistence at login time, eliminates LeagueSelector step
- **Default League:** "The Big Show" (League ID 1) for test environment

### 📊 Project Management Documentation

- **Change:** Renamed ISSUE_STATUS.md to PROJECT_MANAGEMENT.md
- **Added:** Story X.X numbering framework for better organization
- **Impact:** Clear roadmap structure matching VS Code organization

---

## SUMMARY

- **Total Stories Tracked:** Dynamic; use GitHub issue board as source of truth.
- **✅ Fully Completed:** Includes Story `6.4` and Story `7.3`.
- **🔄 Partially Completed:** Stories `6.1`, `6.2`, `6.3`.
- **❌ Not Started:** Stories `1.2` and `7.2` remain explicitly not started.
- **⏳ Planned (Story 8.x):** 3 commissioner tool features
- **🏗️ Infrastructure (Story 0.x):** 1 complete, 2 in progress
- **Total Stories Tracked:** 35+
- **⏳ Planned (Story 9.x):** 10 analytics & visualization features

---

## RECOMMENDATIONS FOR NEXT SPRINTS

### Sprint 1: Complete Story 6.x (Dashboard & Standings)

1. **Complete Story 6.1** - Enhance standings with W-L-T, PF, PA stats and sorting
   - Effort: 1 day
   - Impact: Core dashboard feature
2. **Complete Story 6.3** - Add top free agents ranking to dashboard
   - Effort: 0.5 days
   - Impact: Useful for team management

### Sprint 2: Commissioner Tools (Story 8.x)

3. **Story 8.3 (Backend)** - Scoring Rules System Infrastructure
   - Effort: 3-5 days
   - Impact: Foundation for advanced commissioner features
4. **Story 8.2 (Frontend)** - Commissioner Scoring Rules Page
   - Effort: 2-3 days
   - Impact: Flexible league customization

5. **Story 8.1** - Commissioner Waiver Wire Rules Page
   - Effort: 2-3 days
   - Impact: Complete commissioner control panel

### Sprint 3: Playoff Features (Story 6.x)

6. **Story 6.2 follow-up** - Dynamic commissioner-settings bracket structure
  - Effort: 2-3 days
  - Impact: Correct bracket behavior across league formats
  - Tracking: GitHub issue [#154](https://github.com/NPGrant81/fantasy-football-pi/issues/154)

7. **Quality hardening sweep** - Edge-case tests and docs governance
  - Effort: 2-4 days
  - Impact: Lower regression risk and cleaner contributor pathways
  - Tracking: GitHub issues [#43](https://github.com/NPGrant81/fantasy-football-pi/issues/43), [#100](https://github.com/NPGrant81/fantasy-football-pi/issues/100), [#155](https://github.com/NPGrant81/fantasy-football-pi/issues/155), [#156](https://github.com/NPGrant81/fantasy-football-pi/issues/156)

### Backlog (Low Priority / Polish)

- **Story 7.2** - Dark/Light mode toggle
- **Story 7.3** - Bug reporting form enhancements (optional polish only; core delivered)
- **Story 1.2** - Historical data archiving
- **Story 0.2** - Cloudflare Tunnel Setup (optional)
- **Story 0.3** - Database Scheduled Backups

---

## VS CODE FILE MAPPING

Stories should map to feature branches and directories:

- `Story 0.x` → `backend/infrastructure/`, `docker/`, deployment configs
- `Story 1.x` → `backend/routers/auth.py`, `frontend/src/pages/Login.jsx`
- `Story 2.x` → `backend/routers/draft.py`, `frontend/src/pages/DraftBoard.jsx`
- `Story 3.x` → `backend/routers/team.py`, `frontend/src/pages/MyTeam.jsx`
- `Story 4.x` → `backend/routers/scoring.py`, `frontend/src/pages/ManageScoringRules.jsx`
- `Story 5.x` → `backend/routers/waivers.py`, `frontend/src/pages/WaiverWire.jsx`
- `Story 6.x` → `backend/routers/matchups.py`, `frontend/src/pages/{Home,Matchups,GameCenter}.jsx`
- `Story 7.x` → `frontend/src/components/`, theme files
- `Story 8.x` → `frontend/src/pages/Commissioner/`, `backend/routers/league.py`
- `Story 9.x` → `backend/routers/analytics.py`, `frontend/src/pages/Analytics/`, `frontend/src/components/charts/`

---

**Reference this document for:**

- Understanding story numbering conventions
- Tracking feature completion status
- Planning sprint priorities
- Mapping GitHub issues to codebase structure

## 📊 ANALYTICS & VISUALIZATIONS (Story 9.x)

### Story 9.1: Analytics Infrastructure Setup

- **GitHub Issue:** [#44](https://github.com/NPGrant81/fantasy-football-pi/issues/44) (Parent)
- **Status:** ⏳ PLANNED
- **Priority:** High
- **Details:** Establish backend infrastructure for Python-native analytics and visualizations
  - Integrate Plotly/Bokeh for server-side chart generation
  - Chart.js integration for client-side rendering
  - Database query optimization for analytics endpoints
  - JSON data pipeline from backend to frontend

### Story 9.2: Core Dashboard Visualizations

- **GitHub Issue:** [#45](https://github.com/NPGrant81/fantasy-football-pi/issues/45)
- **Status:** ⏳ PLANNED
- **Priority:** High
- **Details:** Implement key analytics charts
  - Draft Value Board: Scatter plot (ADP vs Projected Points)
  - Manager Trend Analysis: Line chart of weekly scoring averages
  - Enhanced League Standings: Visual performance indicators

### Story 9.3: Advanced Analytics - The "Luck" Index

- **GitHub Issue:** [#46](https://github.com/NPGrant81/fantasy-football-pi/issues/46)
- **Status:** ⏳ PLANNED
- **Priority:** Medium
- **Details:** Schedule analysis with scatter plot visualization
  - Calculate hypothetical records across all schedules
  - Four quadrants: Good/Lucky, Good/Unlucky, Bad/Lucky, Bad/Unlucky
  - Points For vs Points Against analysis

### Story 9.4: Trade Analyzer & Roster Strength

- **GitHub Issue:** [#47](https://github.com/NPGrant81/fantasy-football-pi/issues/47)
- **Status:** ⏳ PLANNED
- **Priority:** Medium
- **Details:** Radar/Spider chart for positional strength analysis
  - Before/after trade impact visualization
  - QB, RB, WR, TE position group analysis
  - Rest-of-season projection comparisons

### Story 9.5: Waiver Wire Opportunity Tracker

- **GitHub Issue:** [#48](https://github.com/NPGrant81/fantasy-football-pi/issues/48)
- **Status:** ⏳ PLANNED
- **Priority:** Medium
- **Details:** Heatmap for breakout candidate identification
  - Snap counts, route participation tracking
  - Red-zone target analysis
  - Rolling 4-week trend visualization

### Story 9.6: Manager Efficiency Tracker

- **GitHub Issue:** [#49](https://github.com/NPGrant81/fantasy-football-pi/issues/49)
- **Status:** ⏳ PLANNED
- **Priority:** Medium
- **Details:** "Points Left on the Bench" analysis
  - Stacked bar chart: actual vs optimal lineup
  - Weekly efficiency percentage calculations
  - Start/sit decision tracking

### Story 9.7: Player Consistency Ratings

- **GitHub Issue:** [#50](https://github.com/NPGrant81/fantasy-football-pi/issues/50)
- **Status:** ⏳ PLANNED
- **Priority:** Medium
- **Details:** Box-and-whisker plots for reliability analysis
  - Floor/ceiling/median scoring breakdowns
  - Variance calculations for consistency
  - "Set-and-forget" starter identification

### Story 9.8: League Rivalry & History Graphs

- **GitHub Issue:** [#51](https://github.com/NPGrant81/fantasy-football-pi/issues/51)
- **Status:** ⏳ PLANNED
- **Priority:** Low
- **Details:** Chord diagram or network graph visualization
  - Head-to-head historical records
  - Trade relationship mapping
  - Playoff matchup history

### Story 9.9: Positional Heat Map Visualizations

- **GitHub Issue:** [#52](https://github.com/NPGrant81/fantasy-football-pi/issues/52)
- **Status:** ⏳ PLANNED
- **Priority:** Medium
- **Details:** Defense vs position matchup analysis
  - Heatmap grid: teams vs NFL positions
  - Weekly streaming recommendations
  - Positional weakness identification

### Story 9.10: AI-Powered Analytics Chat Advisor

- **GitHub Issue:** [#53](https://github.com/NPGrant81/fantasy-football-pi/issues/53)
- **Status:** ⏳ PLANNED
- **Priority:** High
- **Details:** Intelligent chat assistant with Gemini API integration
  - RAG-style architecture: database + LLM
  - Structured JSON outputs (advisor_text, chart_type, chart_data)
  - Dynamic chart rendering in conversational UI
  - Context-aware analytics queries

---

### Sprint 4: Analytics & Visualizations (Story 9.x)

8. **Story 9.1** - Analytics Infrastructure Setup
   - Effort: 2-3 days
   - Impact: Foundation for all analytics features

9. **Story 9.2** - Core Dashboard Visualizations
   - Effort: 2-3 days
   - Impact: Draft value boards and trend analysis

10. **Story 9.10** - AI-Powered Analytics Chat Advisor
    - Effort: 3-4 days
    - Impact: Game-changing interactive analytics
