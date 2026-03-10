# CI/CD Observability and Reporting

This project ships a built-in CI observability report in `.github/workflows/ci.yml`.

## What is reported

Each CI run publishes a dashboard to the GitHub Actions Step Summary with:

- Per-area status:
  - `Backend` (Python tests and coverage)
  - `Frontend` (lint, responsive audit, unit coverage)
  - `API / E2E` (Cypress workflow)
  - `Deployment` (marked as `deployment_not_in_scope` for this workflow)
- Per-area build time (seconds)
- Total tracked build time (sum of backend, frontend, API/E2E)
- Failure categories (`backend`, `frontend`, `api`, or `none`)

## Where to view the dashboard

1. Open any CI run in GitHub Actions.
2. Open the `CI Observability Report` job.
3. Read the `Build CI dashboard summary` step summary.

## Optional failure notifications

The workflow sends failure alerts only when webhook secrets are present.

Supported secrets:

- `SLACK_WEBHOOK_URL`
- `TEAMS_WEBHOOK_URL`

Notification behavior:

- Alerts trigger when any of `test`, `frontend-test`, or `e2e` is not `success`.
- Payload includes branch, area results, and direct run URL.
- If a secret is missing, that notifier is skipped automatically.

## Notes

- `Deployment` is intentionally categorized as not in scope for this CI pipeline.
- If deployment validation is added later, update the observability table and category mapping in `.github/workflows/ci.yml`.
