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

| Area                 | Endpoint(s)                                                                                                                                                                                                         | Used by                                               |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| Auth                 | `POST /auth/token`, `GET /auth/me`, `PUT /auth/email`, `POST /auth/register`                                                                                                                                        | Login flow, user context, bug report email save       |
| NFL                  | `GET /nfl/schedule/{year}/{week}`                                                                                                                                                                                   | Weekly matchups page, analytics, imported data        |
| League               | `GET /leagues/{id}`, `GET /leagues/owners?league_id=`, `GET /leagues/{id}/news`, `GET/PUT /leagues/{id}/settings`, `POST /leagues/{id}/draft-year`, `GET /leagues/{id}/budgets`, `GET /leagues/{id}/waiver-budgets`, `GET/PUT/DELETE /leagues/{id}/history/team-owner-map`, `GET /leagues/{id}/history/unmapped-series-keys`, `GET /leagues/{id}/history/owner-gap-report?detail_limit=&season_limit=` | Home, Draft, My Team, Matchups, Waivers, Commissioner |
| Divisions            | `GET/PUT /leagues/{id}/divisions/config`, `POST /leagues/{id}/divisions/assignment-preview`, `POST /leagues/{id}/divisions/finalize`, `POST /leagues/{id}/divisions/undo-last`, `POST /leagues/{id}/divisions/report-name` | Commissioner Divisions management                     |
| Team                 | `GET /team/{owner_id}`, `GET /team/my-roster`, `POST /team/lineup`, `POST /team/submit-lineup`, `POST /team/taxi/promote`, `POST /team/taxi/demote`                                                             | My Team                                               |
| Keepers              | `GET /keepers`, `POST /keepers`, `POST /keepers/lock`, `DELETE /keepers/{player_id}`, `GET /keepers/admin`, `POST /keepers/admin/{owner_id}/veto`, `POST /keepers/admin/reset`, `GET/PUT /keepers/settings` (settings include cost_type/value method and inflation) | Keepers page, Commissioner settings                   |
| Dashboard            | `GET /dashboard/{owner_id}`                                                                                                                                                                                         | My Team, Waiver Wire                                  |
| Players              | `GET /players/`, `GET /players/search`, `GET /players/waiver-wire`, `GET /players/{player_id}/season-details`                                                                                                       | Draft, Waiver Wire, My Team                           |
| Draft                | `POST /draft/pick`, `GET /draft/history`, `GET /draft-history`                                                                                                                                                      | Draft Board                                           |
| Matchups             | `GET /matchups/week/{week}`, `GET /matchups/{id}`                                                                                                                                                                   | Matchups, Game Center                                 |
| Waivers              | `POST /waivers/claim` (and backend supports `POST /waivers/drop`)                                                                                                                                                   | Waiver Wire                                           |
| Trades               | `POST /trades/propose`, `GET /trades/pending`, `POST /trades/{trade_id}/approve`, `POST /trades/{trade_id}/reject`                                                                                                | My Team, Commissioner                                 |
| Feedback             | `POST /feedback/bug`                                                                                                                                                                                                | Bug Report                                            |
| Advisor (AI wrapper) | `GET /advisor/status`, `POST /advisor/ask`                                                                                                                                                                          | Global advisor widget                                 |
| Admin tools          | `POST /admin/nfl/sync`, `POST /admin/nfl/schedule/import`, `POST /admin/live-scoring/ingest`, `GET /admin/live-scoring/health`, `POST /admin/live-scoring/watchdog`, `GET /admin/live-scoring/watchdog/alerts`, `POST /admin/drafts/refresh-values`, `POST /admin/config/reload`, `POST /admin/tools/uat-draft-reset`, `POST /admin/tools/uat-team-reset`, `GET/POST/PUT/DELETE /admin/tools/commissioners`, `POST /admin/create-test-league`, `POST /admin/reset-draft`, `POST /admin/finalize-draft`, `POST /admin/reset-league` | Site Admin                                            |

## External APIs (third-party)

| Service                   | Integration point                                                       | Purpose                               | Internal entrypoint                                                                 |
| ------------------------- | ----------------------------------------------------------------------- | ------------------------------------- | ----------------------------------------------------------------------------------- |
| Google Gemini             | Python `google.genai` client (via `google-genai` SDK ≥1.64.0)           | AI responses for league advisor       | `POST /advisor/ask` in `backend/routers/advisor.py`                                 |
| GitHub REST API           | `https://api.github.com` via `requests`                                 | Create bug issues from in-app reports | `POST /feedback/bug` → `backend/utils/github_issues.py`                             |
| ESPN public NFL endpoints | `https://site.api.espn.com/apis/site/v2/sports/football/nfl/*`          | Player/stats ingestion scripts        | `backend/scripts/import_espn_players.py`, `backend/scripts/archive_weekly_stats.py` |
| Yahoo Fantasy API         | `https://football.fantasysports.yahoo.com/f1/draftanalysis?type=salcap` | Draft value ingestion                 | `backend/scripts/import_yahoo_players.py`                                           |
| Draftsharks ADP           | `https://www.draftsharks.com/adp/superflex/ppr/sleeper/12`              | Draft value ingestion                 | `backend/scripts/import_draftsharks_players.py`                                     |
| FantasyNerds Auction API  | `https://api.fantasynerds.com/v1/nfl/auction/`                          | Auction values with min/max context   | `POST /admin/drafts/refresh-values` via `etl/extract/extract_fantasynerds.py` |
| RubeSheets (optional)     | `https://rubesheets.com/Footballv2.aspx`                                | League-custom auction modeling option | Not enabled; documented fallback option only (WebForms scrape risk)                 |

## Draft Value API & Page Mapping

New endpoints and pages for draft value integration:

| Area        | Endpoint(s)                                           | Used by                                         |
| ----------- | ----------------------------------------------------- | ----------------------------------------------- |
| Draft Value | `GET /draft-value/players`, `GET /draft-value/{year}` | Draft analysis, player info, commissioner tools |

Draft value data is sourced from ESPN, Yahoo, and Draftsharks APIs, normalized, and exposed via these endpoints for frontend consumption.

## Draft Value Source Matrix (Pull -> Store -> Page Impact)

| Source | Pull method | Auth | Precheck gate | Stored in | Primary page impact | Current status |
| --- | --- | --- | --- | --- | --- | --- |
| ESPN | Public endpoint or authenticated ESPN path | Optional cookies for auth mode | None (extractor-level failure handling) | `platform_projections` -> `draft_values` | Draft Day Analyzer, Draft Board value views | Enabled |
| DraftSharks | HTML table scrape | None/public | None (extractor-level failure handling) | `platform_projections` -> `draft_values` | Draft Day Analyzer source comparisons | Enabled |
| Yahoo | Yahoo Fantasy API pull | OAuth2 (`YAHOO_*` env vars) | Yahoo precheck (fail-closed when enabled) | `platform_projections` -> `draft_values` | Draft Day Analyzer and downstream consensus | Enabled (optional in refresh payload) |
| FantasyNerds | JSON API pull | API key (`FANTASYNERDS_API_KEY`) | FantasyNerds precheck (fail-closed when enabled) | `platform_projections` -> `draft_values` | Draft Day Analyzer min/avg/max coverage improvement | Enabled |
| RubeSheets | ASP.NET WebForms form-post scrape | Session/form state | Not implemented | N/A | Potential future custom scoring feed | Not enabled; documented as brittle option |

Operational notes:

- Weekly source prechecks run via `.github/workflows/source-prechecks.yml`.
- `POST /admin/drafts/refresh-values` now supports fail-closed prechecks for Yahoo and FantasyNerds.
- RubeSheets is intentionally not integrated into production flow at this time due to brittle form-post parsing and maintenance risk.

---

## 2) Page ↔ API Correlation Matrix

Notes:

- `LeagueAdvisor` is rendered globally in `App` (authenticated app shell), so its endpoints are available from most logged-in pages.
- Methods shown as `METHOD /path`.

| Frontend Route/Page                             | Primary internal APIs called by that page                                                                                                                                                                                                                                                                                                                                                  |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Login view (`App.jsx` unauthenticated state)    | `POST /auth/token`                                                                                                                                                                                                                                                                                                                                                                         |
| Global app boot (`App.jsx` authenticated state) | `GET /auth/me`                                                                                                                                                                                                                                                                                                                                                                             |
| `/` Home                                        | `GET /leagues/{leagueId}`, `GET /leagues/owners?league_id={leagueId}`, `GET /leagues/{leagueId}/news`                                                                                                                                                                                                                                                                                      |
| `/draft` Draft Board                            | `GET /leagues/owners?league_id={leagueId}`, `GET /players/`, `GET /draft/history?session_id=...`, `POST /draft/pick`, `GET /leagues/{leagueId}`, `GET /auth/me`, `GET /leagues/{leagueId}/settings`, `GET /leagues/{leagueId}/budgets?year=...`, `GET /players/search?q=...&pos=...`                                                                                                       |
| `/team` and `/team/:ownerId` My Team            | `GET /auth/me`, `GET /leagues/{leagueId}`, `GET /leagues/owners?league_id={leagueId}`, `GET /leagues/{leagueId}/settings`, `GET /dashboard/{ownerId}`, `GET /team/{ownerId}`, `POST /trades/propose`, `GET /players/{player_id}/season-details`                                                                                                                                            |
| `/keepers` Keeper Management                     | `GET /keepers`, `POST /keepers`, `POST /keepers/lock`, `DELETE /keepers/{player_id}`, `GET /keepers/settings`, `PUT /keepers/settings`                                                                                                                                            |
| `/matchups` Matchups                            | `GET /auth/me`, `GET /leagues/{league_id}`, `GET /matchups/week/{week}`                                                                                                                                                                                                                                                                                                                    |
| `/matchup/:id` Game Center                      | `GET /matchups/{id}`                                                                                                                                                                                                                                                                                                                                                                       |
| `/waivers` Waiver Wire                          | `GET /players/waiver-wire`, `GET /dashboard/{ownerId}`, `GET /leagues/{leagueId}`, `GET /leagues/{leagueId}/settings`, `POST /waivers/claim`                                                                                                                                                                                                                                               |
| `/commissioner` Commissioner Dashboard + modals | `GET /leagues/{leagueId}/settings` (includes waiver rules and budget metadata), `GET /leagues/{leagueId}/waiver-budgets`, `GET /leagues/owners?league_id={leagueId}`, `PUT /leagues/{leagueId}/settings`, `POST /leagues/owners`, `GET /trades/pending`, `POST /trades/{tradeId}/{action}` (frontend reference), `POST /leagues/{leagueId}/draft-year`, `POST /leagues/{leagueId}/budgets` |
| `/commissioner/manage-divisions`               | `GET /leagues/owners?league_id={leagueId}`, `GET /leagues/{leagueId}/divisions/config`, `PUT /leagues/{leagueId}/divisions/config`, `POST /leagues/{leagueId}/divisions/assignment-preview`, `POST /leagues/{leagueId}/divisions/finalize`, `POST /leagues/{leagueId}/divisions/undo-last`, `POST /leagues/{leagueId}/divisions/report-name` |
| `/commissioner/history-owner-mapping`          | `GET /leagues/owners?league_id={leagueId}`, `GET /leagues/{leagueId}/history/team-owner-map`, `PUT /leagues/{leagueId}/history/team-owner-map`, `DELETE /leagues/{leagueId}/history/team-owner-map/{rowId}`, `GET /leagues/{leagueId}/history/unmapped-series-keys`, `GET /leagues/{leagueId}/history/owner-gap-report` |
| `/admin` Site Admin                             | `POST /admin/nfl/sync`, `POST /admin/nfl/schedule/import`, `POST /admin/tools/uat-draft-reset`, `POST /admin/tools/uat-team-reset`, `POST /admin/create-test-league`, `POST /admin/reset-draft`                                                                                                                                                                                           |
| `/admin/manage-commissioners`                   | `GET /admin/tools/commissioners`, `POST /admin/tools/commissioners`, `PUT /admin/tools/commissioners/{commissionerId}`, `DELETE /admin/tools/commissioners/{commissionerId}`                                                                                                                                                                                                             |
| `/bug-report` Bug Report                        | `PUT /auth/email`, `POST /feedback/bug`                                                                                                                                                                                                                                                                                                                                                    |
| `/analytics` Analytics Dashboard                | Uses `/analytics/league/{id}/leaderboard`, `/analytics/league/{id}/weekly-stats` and `/analytics/league/{id}/rivalry` endpoints to power charts and tables (efficiency, weekly trends, rivalry graph)                                                                                                                                                                                                                                           |
| `/playoffs` Playoff Bracket                     | `GET /playoffs/seasons`, `GET /playoffs/bracket` (via Home bracket accordion + playoffs page)                                                                                                                                                                                                                                                                                              |

## 2b) Page -> Data Fields Used (Quick Debug Matrix)

Use this table when validating why a page does or does not show values.

| Page | Core fields displayed | Primary backing table(s) | If missing, likely cause |
| --- | --- | --- | --- |
| Draft Day Analyzer (`/draft-day-analyzer`) | `player`, `position`, `team`, `auction_value`, `price_min`, `price_avg`, `price_max`, `adp`, `projected_points`, `confidence/source_count` | `draft_values`, `platform_projections`, `players` | Source precheck blocked load, upstream source empty, or low cross-source overlap |
| Draft Board (`/draft`) | `player`, `position`, `team`, value/price columns, active eligibility signals | `players`, `draft_values`, league context tables | Player filtered as inactive, no matching draft value row, or stale season context |
| Player search / value lookups (`/players/search`, Draft UI typeahead usage) | `name`, `position`, `team`, `adp`, value summary fields when available | `players`, `draft_values` | Name/team mismatch during load mapping, or source rows missing ADP/value |
| Commissioner draft tools (`/commissioner` + admin refresh actions) | refresh status, source load outcomes, season-level update effects | `platform_projections`, `draft_values` | Source auth failure, precheck threshold failure, or extractor parsing drift |

Field lineage quick map:

- `price_min/price_avg/price_max`: computed from positive `platform_projections.auction_value` rows for the season.
- `adp`: ingested per source, normalized in ETL, then aggregated into `draft_values`.
- `projected_points`: source-dependent; may be unavailable for some providers/modes.
- `confidence/source_count`: derived from number and agreement of contributing source rows.

---

## 3) Quick Risk/Gap Notes

- `POST /admin/create-test-league` and `POST /admin/reset-draft` are maintained as compatibility aliases in `backend/routers/admin.py`; newer system reset workflows are exposed via `/admin/tools/uat-draft-reset` and `/admin/tools/uat-team-reset`.
- `POST /feedback/bug` now persists bug reports even if GitHub issue creation fails, and returns `issue_warning` instead of failing the full request.
