# Copilot Instructions for Fantasy Football PI

This document provides repository‑specific guidelines that GitHub Copilot (and other AI tools) should follow when generating code, suggestions, or assisting with pull‑requests. It reflects the architecture and conventions of the `fantasy-football-pi` project.

---
## 1. Project Architecture

### Backend structure (`backend/`)
- Core FastAPI app lives at `backend/main.py`.
- Routers/controllers live under `backend/routers/` (e.g. `playoffs.py`, `analytics.py`, `auth.py`).
- Data models are declared in `backend/models.py` and additional modules like `models_draft_value.py` and `models/trade_review.py`.
- Business logic and helpers are placed in `backend/services/` and `backend/utils/`.
- Database configuration and session helpers are in `backend/database.py` and `alembic/` for migrations.
- Tests mirror the router layout in `backend/tests/` using pytest fixtures from `conftest.py`.
- **Rules:**
  - Route handlers are thin; all domain logic goes into services or models.
  - Access the database exclusively through SQLAlchemy ORM, never hand‑write raw SQL.
  - Use Pydantic schemas from `backend/schemas/` for request/response validation.
  - **Historical user exclusion (required for all member-list queries):** Historical
    franchise users imported from MFL are stored as `User` rows with usernames matching
    the pattern `hist_YYYY_XXXX` (e.g. `hist_2003_0002`). They must **never** appear in
    current-season operational views (standings, waivers, trades, budgets, divisions).
    Any backend query that returns a list of league members filtered by `league_id` MUST
    also exclude historical users with:
    ```python
    ~models.User.username.like("hist_%")
    ```
    Do **not** rely on username exclusion lists alone — that pattern does not cover
    historical users.

### Frontend structure (`frontend/`)
- Entry point is `frontend/src/App.jsx` with routing defined there.
- UI components live in `frontend/src/components/` and are grouped by feature.
- Pages/views appear under `frontend/src/pages/` (e.g. `home`, `playoffs`, `analytics`) with sub‑components in the same folder.
- API interactions must go through `frontend/src/api/client.js` abstraction.
- Styling is achieved with Tailwind classes; minimal custom CSS is allowed.
- Tests mirror source structure under `frontend/tests/` and use Vitest + Testing Library.
- **Rules:**
  - Use functional React components and hooks; prefer lazy loading for large pages.
  - Do not bypass the `apiClient` when performing network calls (no raw `fetch` or `axios` outside the wrapper).
  - Put shared UI helpers in `frontend/src/utils/` or `components/` where appropriate.

### Cross‑layer rules
- Keep presentation logic in the frontend; business and data logic stays in the backend.
- Follow existing file & naming patterns when adding features; avoid introducing novel abstractions unless the benefit is clear.
- Use consistent terminology (`leagueId`, `ownerId`, `matchups`, etc.) across both layers.

#### Repository layout snapshot
Copilot can rely on this simple map when proposing where to put new files:
```
backend/
  routers/
  services/
  utils/
  schemas/
  models.py
  database.py
frontend/
  src/
    components/
    pages/
    api/
    utils/
```

#### When adding new features
*Backend* must include:
- a router file under `backend/routers/`
- service functions in `backend/services/`
- Pydantic schemas in `backend/schemas/`
- tests in `backend/tests/` mirroring the source paths

*Frontend* must include:
- a page under `frontend/src/pages/`
- any new components in `frontend/src/components/`
- API call logic using `frontend/src/api/client.js`
- tests in `frontend/tests/` matching the component/page

*UAT and release validation* must include:
- update `docs/uat/uat_master.xlsx` for any user-visible feature, workflow,
  validation, permission, or content change
- update `docs/uat/uat_overview.pptx` screenshots/content when routes, modals,
  page purpose, or user flows change
- assign/update `Execution Tier` (`P0/P1/P2`) for impacted rows
- keep row wording in plain user language aligned with UI labels/menu paths
- keep screenshot coverage mapping current in `docs/uat/UAT_DECK_IMAGE_COVERAGE.md`
- update `docs/uat/UAT_MASTER_DOCUMENT_INSTRUCTIONS.md` when UAT process rules
  or required fields change

#### Do not generate
- raw SQL anywhere in the backend
- new global state stores (no Redux/Zustand unless already used)
- new CSS files; stick to Tailwind classes
- class‑based React components
- additional backend frameworks/ORMs (only FastAPI/SQLAlchemy)

> Copilot should not autonomously add new API endpoints unless the prompt explicitly asks for a route; maintaining strict control over the API surface is preferred.

#### Preferred patterns
- Depend on injected service objects instead of putting logic in routers.
- Use the asynchronous database session (`async_session`) over sync sessions.
- Prefer composition (hooks/HOC) over inheritance in React.
- When making API requests on the frontend, use the existing `apiClient` pattern below.

#### Example schemas
```python
class Team(BaseModel):
    id: int
    name: str
    owner_id: int
```

#### Example API call pattern (frontend)
```js
// in a component or hook
import apiClient from '../api/client';

const fetchOwners = async (leagueId) => {
  const res = await apiClient.get(`/leagues/owners?league_id=${leagueId}`);
  return res.data;
};
```

---
## 2. Language, Framework, and Dependency Rules

### Backend (Python)
- Target Python **3.11+**.
- All new modules must use full type hints on functions and return types.
- Import with absolute paths relative to the project root (e.g. `from backend.routers import ...`).
- Maintain the existing async/await patterns; database calls are asynchronous via `async_session` by default.
- The codebase currently uses **async** SQLAlchemy sessions; continue that pattern for new code.
- Copilot may propose generating Alembic migration files when models change; these should be reviewed by a maintainer before applying.
- FastAPI generates OpenAPI documentation automatically from route signatures and Pydantic schemas; Copilot need not update docs manually unless specifically requested.
- Prefer the shared logging facilities in `backend` (`logging.getLogger('fantasy')`) rather than `print()`.

### Frontend (JavaScript/TypeScript)
- New source files should be TypeScript (`.tsx`/`.ts`) unless there is a strong reason to remain JavaScript.
- Components should be functional and use React hooks; class components are deprecated.
- Styling uses Tailwind CSS throughout; avoid writing custom CSS unless necessary for a specific situation.
- State management is primarily handled via **React Context** (as seen in `ThemeContext` and others); continue with that pattern.
- File names for React components should use **PascalCase** (e.g. `MyComponent.tsx`).
- Copilot can generate TypeScript types from backend Pydantic models when creating shared interfaces, but cross‑layer type inference is optional and should be confirmed by a human.

### Shared
- Environment variables read through existing config utilities (`dotenv` on backend, `import.meta.env` on frontend).
- Error‑handling patterns should match existing conventions (raise `HTTPException` on backend, display toast/alert on frontend).

> **Note on utility scripts:** many developer helpers such as `audit-breakpoints.sh` are written in Bash; run them from a Unix-like shell (WSL, Git Bash, etc.) or via `bash -c` from PowerShell. The CI pipeline itself uses a Linux runner, so the script will work there without modification.

---
## 3. Testing Requirements

### Backend tests
- Every new function or service method requires a corresponding `pytest` test in `backend/tests/`.
- Use fixtures from `backend/conftest.py` to mock the database; avoid hitting a real database.
- External APIs should be mocked (e.g. using `responses` or `requests_mock`).
- Test file layout should mirror source (e.g. `tests/test_playoff_router.py` for routes in `routers/playoffs.py`).

### Frontend tests
- Use Vitest with `@testing-library/react`.
- Component tests should assert basic rendering, prop handling, and user interactions.
- Network calls via `apiClient` should be mocked using `vi.mock('../src/api/client')`.
- Match directory structure: e.g. tests for `Home.jsx` live in `frontend/tests/Home.test.jsx`.

### Cross‑layer testing
- No integration tests unless explicitly requested by maintainers; unit tests are sufficient for most features.
- Tests should not rely on external network services.

---
## 4. Code Style and Documentation

### Naming conventions
- **Python:** `snake_case` for variables/functions, `PascalCase` for classes, `UPPER_CASE` for constants.
- **JS/TS:** `camelCase` for variables/functions, `PascalCase` for React components, `UPPER_CASE` for constants.

### Documentation
- Backend: every public class or function must include a docstring explaining purpose, parameters, return values, and side effects.
- Frontend: use JSDoc/TSDoc for complex utilities or components.
- Document notable decisions in comments or relevant markdown docs (see `docs/` folder).

### Formatting
- Backend: format with **Black** and ensure code conforms to PEP8.
- Frontend: use **Prettier** and the existing ESLint configuration.
- Committers should run `npm run lint`/`npm run lint:fix` and `black` before pushing.

---
## 5. Git, CI, and Workflow Rules

- All code must pass linting, type checks, and tests before merging.
- Pull requests should reference this document when suggesting or reviewing changes.
- Commit messages should follow **Conventional Commits** (e.g. `feat: add playoffs sidebar link`).
- Add new dependencies only after discussing justification in the PR description.
- CI pipelines validate backend lint, frontend lint, unit tests, and build steps.

---
## 6. AI Behavior Expectations

When Copilot or any AI assistant is generating code for this repository, it should:
- Respect existing architecture and file organization; avoid inventing new folders or layers without direction.
- Name files and symbols consistently with current conventions (e.g. `analytics.py`, `MyTeam.jsx`).
- Assume Python backend with type hints, FastAPI, SQLAlchemy, Alembic; TypeScript frontend with React, TailwindCSS; pytest and Vitest test frameworks.
- Generate documentation comments (docstrings/JSDoc) when creating new functions.
- Offer project‑specific suggestions rather than generic best practices.
- Treat UAT synchronization as required completion work for user-facing changes,
  not an optional follow-up.

> ⚠️ Copilot should not suggest moving business logic into route handlers or using raw SQL; similarly, it should not bypass `apiClient` on the frontend.

---
These guidelines are meant to keep the codebase consistent, maintainable, and easy for contributors to understand. Update this document as the project evolves.

---
## 7. Additional Rules

### Alembic migrations
- Copilot may propose Alembic migration files when SQLAlchemy models change, but all generated migrations are drafts requiring human review.
- Copilot must not create or modify Alembic environment files (`env.py`, `script.py.mako`) unless explicitly asked.

### Async SQLAlchemy
- All database interactions must use the project’s asynchronous SQLAlchemy session (`async_session`).
- Do not generate synchronous engine/session code or patterns unless explicitly requested.
- Use `await session.execute(...)` and `await session.commit()` consistently.

### Cross‑layer type generation
- Copilot may generate TypeScript types/interfaces based on Pydantic models when helpful.
- Generated types must be placed in `frontend/src/types/` unless another location is specified.
- Do not assume automatic synchronization between backend and frontend types; all generated types require human review.

### React Context state management
- State management must use **React Context** unless maintainers explicitly request another pattern.
- Copilot must not introduce Redux, Zustand, Jotai, or other global state libraries.
- New context modules should follow the pattern established by `ThemeContext`.

### Component and file naming
- React component files must use **PascalCase** (`MyComponent.tsx`).
- Filenames must match the component names exactly.
- Copilot must not generate kebab-case or snake_case filenames for components.

### Endpoint creation restrictions
- Copilot must not create new API routes, endpoints, or router files unless the prompt explicitly requests one.
- When modifying existing endpoints, preserve request/response schemas and existing URL patterns.
- Copilot must not infer new API shapes based solely on frontend usage.

### Git worktree hygiene
- Copilot may use Git worktrees for parallel tasks when necessary.
- Default to a maximum of 2 active worktrees (`main` + current issue branch) unless the user explicitly requests more.
- After a PR merges, remove the corresponding worktree and run `git worktree prune`.
- Before removing any worktree, verify it has no uncommitted changes and is no longer needed.

These additional rules act as guardrails to ensure the agent’s output stays within the project’s expectations.
