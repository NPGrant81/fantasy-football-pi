# UI UX Automation Pipeline

This pipeline provides automated UI/UX validation for pull requests.

Workflow file:

- `.github/workflows/ui-ux-automation.yml`

## What runs automatically

On every PR to `main`, the workflow performs:

- UI component/page linting:
  - `eslint src/components src/pages`
- Accessibility smoke checks:
  - Cypress spec: `frontend/cypress/e2e/accessibility_smoke.spec.js`
- Visual regression guard:
  - Cypress screenshot capture: `frontend/cypress/e2e/uat_capture_pages.spec.js`
  - Baseline diff check: `frontend/scripts/assert-visual-regression-clean.mjs`
- Build preview artifact:
  - `frontend/dist` uploaded as `frontend-preview-dist`

## Visual regression strategy (free-tier compatible)

- Baseline screenshots are versioned in `frontend/cypress/screenshots/uat_capture_pages.spec.js`.
- CI re-runs screenshot capture.
- If generated files differ from tracked baseline, the workflow fails before merge.

## PR preview artifact

`frontend-preview-dist` is uploaded for each PR run and can be downloaded from the Actions run artifacts.

## Notes

- This workflow is intentionally isolated from backend/API CI jobs.
- Keep baseline screenshots updated when intentional UI changes are introduced.
