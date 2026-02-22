# Frontend (Fantasy Football PI)

Vite + React frontend for the Fantasy Football PI app.

## Quick Start

- Install: `npm install`
- Run dev server: `npm run dev`
- Run tests: `npm test -- --run`
- Run lint: `npm run lint`
- Verify pre-commit checks: `npm run verify`

## Dependency Compatibility (React 19)

- This project uses React 19.
- Keep `@testing-library/react` and `@testing-library/user-event` on current versions (React 19 compatible).
- If install fails with peer dependency errors, run:

```bash
npm install -D @testing-library/react@latest @testing-library/user-event@latest
npm install
```

This prevents broken installs where runtime deps (like `chart.js`) are missing and Vite fails with import-analysis errors.

## Folder Map (Canonical Structure)

Use a feature-first page structure in `src/pages`.

```text
src/
├── api/                      # API client and request wrappers
├── components/               # Shared cross-feature UI only
├── hooks/                    # Shared hooks
├── utils/                    # Shared helpers/constants
├── pages/
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
│   │   └── components/
│   └── admin/
│       └── SiteAdmin.jsx
├── App.jsx
└── main.jsx
```

## Organization Rules

1. If used by one page/feature, colocate it under that page folder.
2. If reused across multiple features, promote to `src/components`.
3. Keep route modules in canonical feature folders (example: `pages/matchups/Matchups.jsx`).
4. Use top-level `pages/*.jsx` files only as temporary re-export wrappers during migration.
5. Remove wrappers after imports/tests are fully migrated.

## Naming Conventions

- Page components: PascalCase (`Home.jsx`, `SiteAdmin.jsx`).

- **API base URL (VITE_API_BASE_URL)** – by default the client sends requests to a relative path so
  the development server can proxy them to the Python backend (avoids CORS).
  Set `VITE_API_BASE_URL` in production to your actual API host (e.g. `https://api.example.com`).
  During local development you can override it or leave it blank; the proxy in
  `vite.config.js` handles `/team`, `/league`, `/admin/tools`, etc.
- Page-local components: PascalCase under `pages/<feature>/components`.
- Shared components: PascalCase under `src/components`.
- Utilities: camelCase under `src/utils`.

## Migration Note

Legacy wrapper/shim paths used during reorganization have been removed. Use canonical feature-folder imports only.

## PR Checklist (Frontend Organization)

Before opening a PR, verify:

- [ ] New route pages are created in feature folders under `src/pages/<feature>/`.
- [ ] Page-local components are colocated under `src/pages/<feature>/components/`.
- [ ] Shared components moved to `src/components/` only when reused across features.
- [ ] `App.jsx` imports use canonical feature-folder page paths.
- [ ] Any temporary top-level `src/pages/*.jsx` wrappers are either justified or removed once imports/tests are migrated.
- [ ] `npm run lint` and affected tests pass.

## Pre-Commit Checklist (Frontend Runtime + Tests)

Before committing frontend changes, run this sequence:

```bash
npm install
npm run verify
```

Expected outcome:
- Build completes without unresolved import errors (for example `chart.js` in analytics charts).
- Lint and tests pass for changed areas.
