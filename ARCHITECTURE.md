War Room Alpha: Technical Architecture
This document outlines the high-level organization and logical patterns of the War Room Alpha backend.
1. Directory Structure
The project follows a Service-Oriented Architecture to separate web interfaces from core business logic.


backend/
├── core/              # 1.1 Security, Auth context, and Constants
├── data/              # 1.2 Raw CSV files (Players, Teams, Rules)
├── routers/           # 1.3 FastAPI route definitions (The Front Door)
├── services/          # 1.4 Business logic and DB operations (The Engine)
├── scripts/           # 1.5 CLI tools (Reset, Seed, Sync)
├── models.py          # 1.6 SQLAlchemy database models
├── database.py        # 1.7 Database engine and session setup
└── main.py            # 1.8 Application entry point


2. Logic Numbering Standard
To maintain a consistent flow across routers and services, all functions follow a tiered numbering system within code comments:
1.x: Validation & Data Retrieval
• 1.1 Security Checks: Verify JWT tokens or user roles (e.g., Commissioner/Superuser).
• 1.2 Data Sourcing: Fetch required records from the database or external APIs.
• 1.3 Input Validation: Ensure the incoming request meets business rules (e.g., checking roster limits).
2.x: Execution & Response
• 2.1 Core Action: Perform the primary task (e.g., adding a player, calculating a score).
• 2.2 Persistence: Commit changes to the PostgreSQL database.
• 2.3 Response: Return the final status and payload to the client.
3. Core Logic Layers
Scoring Service
The scoring_service.py is the primary engine for calculating performance. It pulls dynamic rules from the ScoringRule table, allowing different leagues to maintain unique scoring settings without code changes.
Security Bouncers
Access control is managed via FastAPI Dependencies in core/security.py. These act as "bouncers" at the router level, preventing non-commissioners from accessing administrative endpoints.
Seeding & Maintenance
One-time setup tasks and destructive actions (like resetting the draft) are isolated in the scripts/ folder. This ensures that "nuclear" logic is never accidentally executed by the web server.
Why this works:
• Separation of Concerns: You can update the "Waiver Claim" logic in the service layer without touching the API endpoint in the router.
• Scalability: New features (like Trades or Playoff Brackets) have a clear, predetermined home in the directory tree.
• AI Coordination: Maintaining this file helps AI tools understand your specific architectural invariants, leading to better code suggestions.

4. Frontend Architecture, Naming, and Testing
The frontend is a Vite + React SPA in `frontend/`.

4.1 Frontend Structure (Feature-First with Colocation)
Use this structure as the default:

frontend/src/
├── api/                    # API clients and request wrappers
├── components/             # Shared, cross-feature components only
├── hooks/                  # Shared hooks
├── utils/                  # Shared utilities/constants
├── pages/                  # Route-level features
│   ├── home/
│   │   ├── Home.jsx
│   │   └── components/
│   ├── matchups/
│   │   ├── Matchups.jsx
│   │   └── GameCenter.jsx
│   ├── team-owner/
│   │   └── MyTeam.jsx
│   ├── commissioner/
│   │   ├── CommissionerDashboard.jsx
│   │   └── components/     # Components used only by commissioner pages
│   └── admin/
│       └── SiteAdmin.jsx
├── App.jsx                 # Router and auth/league guards
└── main.jsx                # App bootstrap

Rule of thumb:
- If a component is used by one page/feature, keep it inside that feature folder (`pages/<feature>/components`).
- If a component is reused across multiple features, promote it to `src/components`.

4.2 Current Migration Pattern (Safe Refactor)
To avoid breaking imports/tests while reorganizing:
- New canonical files live under page-local feature folders.
- Legacy paths in `src/components/...` can remain as thin re-export shims during migration.
- App/router imports should prefer canonical feature paths.

This allows incremental cleanup without large breakage risk.

Note: During migration, top-level `pages/*.jsx` files may temporarily exist as compatibility wrappers that re-export from the canonical feature folder.

4.3 Naming Conventions (Long-Term)
- Page components: PascalCase route files (e.g., `CommissionerDashboard.jsx`).
- Page-local components: PascalCase in `pages/<feature>/components/`.
- Shared components: PascalCase in `src/components/`.
- Utility files: camelCase in `src/utils/`.
- Avoid duplicate route files in both top-level `pages/` and nested feature folders; prefer nested feature folder and keep top-level wrappers only as temporary compatibility shims.

4.4 Frontend Runtime Notes
- `src/api/client.js`: Central axios instance with auth token handling and 401 behavior.
- `App.jsx`: Handles initial auth/league gate, then mounts `Layout` and routes.

4.5 Testing Strategy
- Backend: `pytest` tests under `backend/tests/`.
- Frontend unit/integration: `vitest` + React Testing Library under `frontend/tests/`.
- E2E: Cypress specs under `frontend/cypress/e2e/`.
- CI: GitHub Actions runs backend tests, frontend tests, and Cypress E2E.

Recommendations
- Keep `apiClient` thin and test-friendly.
- Mock network calls in component tests and isolate business logic for faster feedback.
- During folder migrations, prefer re-export shims first, then remove them after import cleanup is complete.
