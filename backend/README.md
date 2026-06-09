# API Integration Test Pipeline

This runbook documents the CI API integration pipeline introduced for issue #196.

## Scope

The CI workflow now includes a dedicated `api-integration` job in `.github/workflows/ci.yml`.

It runs on every pull request to `main` and includes:

- integration tests with database-backed app behavior
- API contract tests for response shape and required OpenAPI paths
- smoke tests against a locally started backend service
- API smoke log artifact upload (`api-smoke-logs`)

## Tests executed

`backend/tests/test_api_integration_pipeline.py` validates:

- `GET /health` contract shape (`status`, `service`, `database`)
- `POST /auth/token` contract shape (`access_token`, `token_type`, `owner_id`)
- `GET /openapi.json` includes required paths (`/auth/token`, `/health`)

## CI compatibility reporting

`CI Observability Report` now includes a dedicated row:

- `API Contract & Smoke`

This row is used to quickly diagnose API compatibility failures separate from frontend E2E failures.

## Deployment smoke step behavior

The API integration job starts a local backend service (`uvicorn`) and verifies:

- `/health` endpoint responds
- `/openapi.json` can be fetched
- contract-required paths exist in OpenAPI payload

## Failure categorization

When this job fails, the observability report marks failure category as:

- `api_contract`

This category is also included in Slack/Teams failure notifications (when webhooks are configured).
