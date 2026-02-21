# API Inventory and Page Correlation Matrix

## Scope
This document maps:
- **Internal APIs**: FastAPI routes served by this repo (`backend/routers/*`)
- **External APIs**: third-party services called by backend code
- **API ↔ Page correlation**: which frontend routes use which API endpoints

---

## 1) Internal vs External API Inventory

## Internal APIs (application-owned)
Base URL (frontend client): `http://127.0.0.1:8000`

| Area | Endpoint(s) | Used by |
|---|---|---|
| Auth | `POST /auth/token`, `GET /auth/me`, `PUT /auth/email`, `POST /auth/register` | Login flow, user context, bug report email save |
| League | `GET /leagues/{id}`, `GET /leagues/owners?league_id=`, `GET /leagues/{id}/news`, `GET/PUT /leagues/{id}/settings`, `POST /leagues/{id}/draft-year`, `GET /leagues/{id}/budgets` | Home, Draft, My Team, Matchups, Waivers, Commissioner |
| Team | `GET /team/{owner_id}` | My Team |
| Dashboard | `GET /dashboard/{owner_id}` | My Team, Waiver Wire |
| Players | `GET /players/`, `GET /players/search`, `GET /players/waiver-wire`, `GET /players/{player_id}/season-details` | Draft, Waiver Wire, My Team |
| Draft | `POST /draft/pick`, `GET /draft/history` | Draft Board |
| Matchups | `GET /matchups/week/{week}`, `GET /matchups/{id}` | Matchups, Game Center |
| Waivers | `POST /waivers/claim` (and backend supports `POST /waivers/drop`) | Waiver Wire |
| Trades | `POST /trades/propose`, `GET /trades/pending` | My Team, Commissioner |
| Feedback | `POST /feedback/bug` | Bug Report |
| Advisor (AI wrapper) | `GET /advisor/status`, `POST /advisor/ask` | Global advisor widget |
| Admin tools | `POST /admin/tools/sync-nfl`, `POST /admin/create-test-league`, `POST /admin/reset-draft` | Site Admin |

## External APIs (third-party)

| Service | Integration point | Purpose | Internal entrypoint |
|---|---|---|---|
| Google Gemini | Python `google.genai` client | AI responses for league advisor | `POST /advisor/ask` in `backend/routers/advisor.py` |
| GitHub REST API | `https://api.github.com` via `requests` | Create bug issues from in-app reports | `POST /feedback/bug` → `backend/utils/github_issues.py` |
| ESPN public NFL endpoints | `https://site.api.espn.com/apis/site/v2/sports/football/nfl/*` | Player/stats ingestion scripts | `backend/scripts/import_espn_players.py`, `backend/scripts/archive_weekly_stats.py` |
| Yahoo Fantasy API | `https://football.fantasysports.yahoo.com/f1/draftanalysis?type=salcap` | Draft value ingestion | `backend/scripts/import_yahoo_players.py` |
| Draftsharks ADP | `https://www.draftsharks.com/adp/superflex/ppr/sleeper/12` | Draft value ingestion | `backend/scripts/import_draftsharks_players.py` |
## Draft Value API & Page Mapping

New endpoints and pages for draft value integration:

| Area | Endpoint(s) | Used by |
|---|---|---|
| Draft Value | `GET /draft-value/players`, `GET /draft-value/{year}` | Draft analysis, player info, commissioner tools |

Draft value data is sourced from ESPN, Yahoo, and Draftsharks APIs, normalized, and exposed via these endpoints for frontend consumption.

---

## 2) Page ↔ API Correlation Matrix

Notes:
- `LeagueAdvisor` is rendered globally in `App` (authenticated app shell), so its endpoints are available from most logged-in pages.
- Methods shown as `METHOD /path`.

| Frontend Route/Page | Primary internal APIs called by that page |
|---|---|
| Login view (`App.jsx` unauthenticated state) | `POST /auth/token` |
| Global app boot (`App.jsx` authenticated state) | `GET /auth/me` |
| `/` Home | `GET /leagues/{leagueId}`, `GET /leagues/owners?league_id={leagueId}`, `GET /leagues/{leagueId}/news` |
| `/draft` Draft Board | `GET /leagues/owners?league_id={leagueId}`, `GET /players/`, `GET /draft/history?session_id=...`, `POST /draft/pick`, `GET /leagues/{leagueId}`, `GET /auth/me`, `GET /leagues/{leagueId}/settings`, `GET /leagues/{leagueId}/budgets?year=...`, `GET /players/search?q=...&pos=...` |
| `/team` and `/team/:ownerId` My Team | `GET /auth/me`, `GET /leagues/{leagueId}`, `GET /leagues/owners?league_id={leagueId}`, `GET /leagues/{leagueId}/settings`, `GET /dashboard/{ownerId}`, `GET /team/{ownerId}`, `POST /trades/propose`, `GET /players/{player_id}/season-details` |
| `/matchups` Matchups | `GET /auth/me`, `GET /leagues/{league_id}`, `GET /matchups/week/{week}` |
| `/matchup/:id` Game Center | `GET /matchups/{id}` |
| `/waivers` Waiver Wire | `GET /players/waiver-wire`, `GET /dashboard/{ownerId}`, `GET /leagues/{leagueId}`, `GET /leagues/{leagueId}/settings`, `POST /waivers/claim` |
| `/commissioner` Commissioner Dashboard + modals | `GET /leagues/{leagueId}/settings`, `GET /leagues/owners?league_id={leagueId}`, `PUT /leagues/{leagueId}/settings`, `POST /leagues/owners`, `GET /trades/pending`, `POST /trades/{tradeId}/{action}` (frontend reference), `POST /leagues/{leagueId}/draft-year`, `POST /leagues/{leagueId}/budgets` |
| `/admin` Site Admin | `POST /admin/tools/sync-nfl`, `POST /admin/create-test-league`, `POST /admin/reset-draft` |
| `/bug-report` Bug Report | `PUT /auth/email`, `POST /feedback/bug` |
| `/analytics` Analytics Dashboard | No direct API call in `AnalyticsDashboard.jsx` (chart components may evolve later) |

---

## 3) Quick Risk/Gap Notes

- The commissioner UI references `POST /trades/{tradeId}/{action}` from `ManageTrades.jsx`; current `backend/routers/trades.py` exposes `POST /trades/propose` and `GET /trades/pending` only. If commissioner approve/veto is required, add matching backend endpoints.
- `POST /feedback/bug` now persists bug reports even if GitHub issue creation fails, and returns `issue_warning` instead of failing the full request.
