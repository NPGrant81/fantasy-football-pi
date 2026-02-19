# Frontend (Fantasy Football PI)

Vite + React frontend for the Fantasy Football PI app.

## Quick Start

- Install: `npm ci --legacy-peer-deps`
- Run dev server: `npm run dev`
- Run tests: `npm test -- --run`
- Run lint: `npm run lint`

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
