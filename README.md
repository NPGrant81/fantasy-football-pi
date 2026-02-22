# Fantasy Football Pi (The "War Room")

**A self-hosted, Python-based Fantasy Football platform designed to run on a Raspberry Pi (or local PC).**

This repository contains a FastAPI backend and a React (Vite + Tailwind) frontend for running an auction-style fantasy football league.

## Project Docs

- Core architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- UI/UX reference: [UI_REFERENCE.md](UI_REFERENCE.md)
- Testing guide: [TESTING_GUIDE.md](TESTING_GUIDE.md)
- Testing session summary: [TESTING_SESSION_SUMMARY.md](TESTING_SESSION_SUMMARY.md)
- Issue status tracker: [ISSUE_STATUS.md](ISSUE_STATUS.md)
- PR handoff notes: [PR_NOTES.md](PR_NOTES.md)
- Permissions notes: [permissions.md](permissions.md)
- API inventory + full page matrix: [API_PAGE_MATRIX.md](API_PAGE_MATRIX.md)

## API Overview (Condensed)

### Internal APIs (app-owned)

- **Auth:** `/auth/*`
- **League:** `/leagues/*`
- **Team:** `/team/*`
- **Dashboard:** `/dashboard/*`
- **Players:** `/players/*`
- **Draft:** `/draft/*` and `/draft-history`
- **Matchups:** `/matchups/*`
- **Waivers:** `/waivers/*`
- **Trades:** `/trades/*`
- **Feedback:** `/feedback/*`
- **Advisor:** `/advisor/*`
- **Admin tools:** `/admin/*`

### External APIs / integrations

- **Google Gemini** via backend advisor route (`/advisor/ask`) using the unified `google-genai` SDK (>=1.64.0).
  This replaces the earlier `google-ai-generativelanguage`/`google-generativeai` packages and is required for compatibility
  with Gemini's latest free‑tier models as of February 2026.
- **GitHub REST API** via bug report flow (`/feedback/bug`)
- **ESPN NFL endpoints** via backend ingestion scripts

### Page → API matrix (high level)

| Frontend route/page | Main APIs |
|---|---|
| Login (`App.jsx`) | `POST /auth/token` |
| Home (`/`) | `GET /leagues/{id}`, `GET /leagues/owners`, `GET /leagues/{id}/news` |
| Draft (`/draft`) | `GET /draft/history`, `POST /draft/pick`, `GET /players`, `GET /players/search`, `GET /leagues/*` |
| My Team (`/team`, `/team/:ownerId`) | `GET /auth/me`, `GET /team/{ownerId}`, `GET /dashboard/{ownerId}`, `POST /trades/propose`, `GET /players/{id}/season-details` |
| Matchups (`/matchups`) | `GET /matchups/week/{week}`, plus `GET /auth/me`, `GET /leagues/{id}` |
| Game Center (`/matchup/:id`) | `GET /matchups/{id}` |
| Waiver Wire (`/waivers`) | `GET /players/waiver-wire`, `POST /waivers/claim`, `GET /dashboard/{ownerId}`, `GET /leagues/*` |
| Commissioner (`/commissioner`) | `GET/PUT /leagues/{id}/settings`, `GET /leagues/owners`, `GET /trades/pending`, budget + draft-year endpoints |
| Site Admin (`/admin`) | `POST /admin/tools/sync-nfl`, `POST /admin/create-test-league`, `POST /admin/reset-draft` |
| Bug Report (`/bug-report`) | `PUT /auth/email`, `POST /feedback/bug` |
| Analytics (`/analytics`) | No direct API call in dashboard shell (chart components may evolve) |

For the full endpoint-level matrix (including notes and gaps), see [API_PAGE_MATRIX.md](API_PAGE_MATRIX.md).

## CI

 - **GitHub Actions:** The repository runs backend tests on push and PR via `.github/workflows/ci.yml`.
 - **Badge:** [![CI](https://github.com/NPGrant81/fantasy-football-pi/actions/workflows/ci.yml/badge.svg)](https://github.com/NPGrant81/fantasy-football-pi/actions/workflows/ci.yml)

---

Frontend testing & local run

- Install dependencies and run dev server:

```bash
cd frontend
npm install
npm run dev
```

- Run frontend tests (Vitest + React Testing Library):

```bash
cd frontend
npm ci
npm test
```

Backend testing & local run

- Install backend dependencies and run tests:

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

- Reproducible backend install (frozen set):

```bash
cd backend
pip install -r requirements-lock.txt
```

- Refresh backend freeze after dependency changes:

```bash
cd backend
python -m pip freeze > requirements-lock.txt
```

CI behavior

- The GitHub Actions workflow `.github/workflows/ci.yml` runs both backend (`pytest`) and frontend (`vitest`) tests on push and PR to `main`. The badge above links to the workflow run history.

Coverage and E2E

- Frontend coverage: run `npm run test:coverage` in the `frontend/` folder. CI produces coverage artifacts and uploads them as workflow artifacts.
- Backend coverage: run `pytest --cov=backend` locally; CI stores coverage XML as an artifact.
- End-to-end tests: scaffolded Cypress tests can be run with `npm run e2e` (CI runs these using `cypress-io/github-action`).

Files added for testing

- `frontend/tests/` — unit tests (Vitest + RTL)

---

## 📦 Dependency Maintenance

Keeping dependencies current is critical for security and stability. This
repo ships with a helper script and a scheduled check:

```bash
# from workspace root
python backend/scripts/check_dependencies.py
```

The script reports outdated packages and runs `pip audit` for known
vulnerabilities; it also writes a summary to `dependency-report.md`.

Automation is provided via `.github/workflows/dependency-check.yml`, which runs
the helper on the first of every month (and on demand).  The workflow fails if
any outdated packages or audit advisories are found, making it easy to spot
when a maintenance action is needed.  Alternatively you can schedule the
script yourself with cron or another task runner.

When the helper flags a major upgrade or security fix, update
`requirements.txt` and regenerate the lock file (`python -m pip freeze > backend/requirements-lock.txt`),
then run tests.
Dependabot or similar services are also encouraged; they can create PRs when
new versions hit PyPI or npm. Document any version constraints (e.g. the
Google Gemini client) directly in the requirements files so they persist.

- `frontend/cypress/` — Cypress e2e specs and support files
- `.github/workflows/ci.yml` — updated to run backend tests, frontend tests with coverage, and Cypress E2E job


See the `backend/` and `frontend/` folders for additional installation and usage details.

---

## Draft Value Database & Data Integration

This project now includes a database for fantasy football draft value information, sourced from multiple APIs and platforms. The database is designed to support draft analysis, player valuation, and integration with historical and current draft results.

### Minimum Fields:
- Key (for joining to player tables)
- Player Name
- Position
- Team
- Year
- Draft Value
- Bye Week

### Optional/Normalized Fields:
- Position Rank (e.g., WR2, RB1)
- Projected Points
- ADP (Average Draft Position)

### Data Sources:
- ESPN
- Yahoo ([Yahoo Draft Analysis](https://football.fantasysports.yahoo.com/f1/draftanalysis?type=salcap))
- Draftsharks ([Draftsharks ADP](https://www.draftsharks.com/adp/superflex/ppr/sleeper/12))

### Example API Integration Code

#### ESPN
```python
from espn_api.football import League
import pandas as pd

# Initialize connection
league = League(
	league_id=12345678,
	year=2025,
	espn_s2='YOUR_ESPN_S2_COOKIE',
	swid='YOUR_SWID_COOKIE'
)

# Fetch Top 300 Players
top_players = league.free_agents(size=300)

# Parse and export
draft_kit = []
for rank, player in enumerate(top_players, start=1):
	draft_kit.append({
		'Rank': rank,
		'Name': player.name,
		'Position': player.position,
		'Pro Team': player.proTeam,
		'Projected Points': player.projected_total_points
	})
df = pd.DataFrame(draft_kit)
print(df.head(15))
# df.to_json('draft_rankings_2025.json', orient='records')
```

#### Yahoo
```python
from yahoo_oauth import OAuth2
import pandas as pd

oauth = OAuth2(None, None, from_file='oauth2.json')
top_players = []
for start in range(0, 100, 25):
	url = f"https://fantasysports.yahooapis.com/fantasy/v2/game/nfl/players;sort=ADP;start={start}?format=json"
	response = oauth.session.get(url)
	if response.status_code == 200:
		data = response.json()
		try:
			players_data = data['fantasy_content']['game'][1]['players']
			for key in players_data.keys():
				if key != 'count':
					player_info = players_data[key]['player']
					name = player_info[0][2]['name']['full']
					position = player_info[0][4]['display_position']
					nfl_team = player_info[0][5]['editorial_team_abbr']
					adp = "N/A"
					for item in player_info[1:]:
						if 'average_pick' in item:
							adp = item['average_pick']
					top_players.append({
						'Name': name,
						'Position': position,
						'Team': nfl_team.upper(),
						'ADP': adp
					})
		except KeyError:
			print("Reached the end of the available player list or encountered an unexpected JSON structure.")
			break
	else:
		print(f"Failed to fetch data: {response.status_code}")
df = pd.DataFrame(top_players)
print(df.head(15))
```

#### Draftsharks
See [Draftsharks ADP](https://www.draftsharks.com/adp/superflex/ppr/sleeper/12) for manual or scripted data extraction.

---