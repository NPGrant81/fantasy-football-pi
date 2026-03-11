# Frontend CI Pipeline Optimization

This runbook documents frontend CI optimizations implemented for issue #195.

## Frontend pipeline improvements

The `frontend-test` job in `.github/workflows/ci.yml` now includes:

- npm dependency cache through `actions/setup-node` (`cache: npm`)
- Vite/Vitest build artifact cache (`frontend/node_modules/.vite`, `frontend/.vitest`)
- lint check (`npm run lint`)
- type check (`npm run typecheck`)
- responsive breakpoint audit
- unit tests with coverage
- snapshot tests (`npm run test:snapshots`)
- frontend build with log capture (`frontend-build.log`)
- failure diagnostics that print actionable step references and log tail

## Optional visual regression

An optional visual regression validation step is included for manual workflow runs (`workflow_dispatch`) using:

- `npm run test:visual-optional`

This keeps free-tier compatibility while avoiding heavy screenshot diff work on every PR run.

## CI summary visibility

`frontend-test` publishes a dedicated step summary that reports outcomes for:

- lint
- typecheck
- responsive audit
- unit tests
- snapshot tests
- build
- optional visual regression

The global `CI Observability Report` also includes a frontend check summary note for quick diagnosis.

## Artifacts

Frontend CI uploads:

- `frontend-coverage`
- `frontend-build-log`

Use these artifacts when diagnosing PR failures.
