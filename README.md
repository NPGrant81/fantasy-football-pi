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

- **Google Gemini** via backend advisor route (`/advisor/ask`)
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
- `frontend/cypress/` — Cypress e2e specs and support files
- `.github/workflows/ci.yml` — updated to run backend tests, frontend tests with coverage, and Cypress E2E job


See the `backend/` and `frontend/` folders for additional installation and usage details.
