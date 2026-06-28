# Deployment Workflow Improvements (Staging + Production)

This project now uses dedicated GitHub Actions workflows for deployment operations.

Governance Tracker: [Issue #156](https://github.com/NPGrant81/fantasy-football-pi/issues/156)

## Workflow separation

- PR validation: `.github/workflows/ci.yml` and `.github/workflows/ci-contributor.yml`
- Staging deployment: `.github/workflows/deploy-staging.yml`
- Production deployment: `.github/workflows/deploy-production.yml`
- Deployment secret drift precheck: `.github/workflows/deployment-secrets-precheck.yml`

Deployment workflows are manual (`workflow_dispatch`) and isolated from PR validation.

## Required repository secrets

Staging:

- `STAGING_DEPLOY_HOST`
- `STAGING_DEPLOY_USER`
- `STAGING_DEPLOY_SSH_KEY`
- `STAGING_DEPLOY_APP_DIR`
- `STAGING_DEPLOY_KNOWN_HOST` (single `known_hosts` line for the staging host)

Production:

- `PROD_DEPLOY_HOST`
- `PROD_DEPLOY_USER`
- `PROD_DEPLOY_SSH_KEY`
- `PROD_DEPLOY_APP_DIR`
- `PROD_DEPLOY_KNOWN_HOST` (single `known_hosts` line for the production host)

Roster sync workflow (`.github/workflows/sync-rosters.yml`) uses the production deploy secrets above,
including `PROD_DEPLOY_KNOWN_HOST`.

Optional notifications:

- `SLACK_WEBHOOK_URL`
- `TEAMS_WEBHOOK_URL`

Weekly source precheck workflow (`.github/workflows/source-prechecks.yml`):

- `FANTASYNERDS_API_KEY`
- `YAHOO_CLIENT_ID`
- `YAHOO_CLIENT_SECRET`
- `YAHOO_ACCESS_TOKEN`
- `YAHOO_REFRESH_TOKEN`

Deployment secrets precheck workflow (`.github/workflows/deployment-secrets-precheck.yml`):

- Runs daily on a schedule and on manual dispatch
- Verifies required staging and production deploy secrets exist
- Fails fast with a summary listing missing secret names per environment

## Deploy action

1. Open the desired workflow in GitHub Actions.
2. Click `Run workflow`.
3. Select `action=deploy`.
4. Provide `release_ref` (branch, tag, or SHA).
5. Run the workflow.

Deployment behavior:

- Validates all required environment variables/secrets before executing.
- Fetches refs on target host.
- Resolves and deploys the requested ref.
- Rebuilds backend/frontend and restarts services.
- Records deployed ref under `.deploy/current_<env>.ref`.

## Rollback action (single action)

1. Open the desired workflow in GitHub Actions.
2. Click `Run workflow`.
3. Select `action=rollback`.
4. Optional: provide `rollback_ref`.
   - If omitted, workflow uses `.deploy/last_success_<env>.ref`.
5. Run the workflow.

Rollback behavior:

- Uses explicit `rollback_ref` when provided.
- Falls back to last successful deployment ref when available.
- Rebuilds backend/frontend and restarts services.

## Logging and notifications

Each run publishes a deployment summary in `GITHUB_STEP_SUMMARY` including:

- Requested action
- Requested release ref
- Outcome (`success` or `failure`)
- Direct run URL

If webhook secrets are configured, Slack and Teams notifications are sent for every run.

## SSH security hardening (host key pinning)

Deployment and roster-sync workflows use pinned host keys and strict host validation.

- `ssh-keyscan` trust-on-first-use is not used during workflow runs.
- Workflows require `*_DEPLOY_KNOWN_HOST` to be present.
- SSH connections enforce strict host key checking.

Generate each host secret value from a trusted machine:

```bash
ssh-keyscan -H YOUR_HOSTNAME 2>/dev/null | head -n 1
```

Store the full output line as the matching GitHub environment secret:

- staging host line -> `STAGING_DEPLOY_KNOWN_HOST`
- production host line -> `PROD_DEPLOY_KNOWN_HOST`

Rotation guidance:

1. Rotate server SSH host keys on target host.
2. Re-capture host key line with `ssh-keyscan -H`.
3. Update corresponding `*_DEPLOY_KNOWN_HOST` secret.
4. Trigger a manual workflow_dispatch deploy to validate connectivity.

## Reproducibility notes

- Deploy and rollback operate on explicit Git refs.
- Same workflow logic is used in both staging and production.
- Environment-specific secrets keep host targets separated.
