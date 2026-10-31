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
- Resolves and deploys the requested ref. Prefer a reviewed immutable tag or
  commit SHA over a moving branch name.
- Rebuilds backend/frontend and restarts services.
- The supplied systemd service applies migrations through `ExecStartPre` before
  starting the backend. A successful restart alone is not proof of readiness.
- The workflow does not create a database backup. Before deploying a ref with
  pending migrations, verify a fresh backup and a recovery path using
  [restore.md](./restore.md).
- Polls `http://127.0.0.1:8000/health` (30 attempts, two-second request timeout
  and retry delay). Success requires `status`, `database`, and `schema` all
  equal to `ok`.
- Only after readiness succeeds, records the previous current ref under
  `.deploy/last_success_<env>.ref` and the target under `.deploy/current_<env>.ref`.
  An unhealthy deployment fails without advancing either ref. It does not
  automatically roll back the running application.

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
- Uses the same readiness gate and post-health metadata updates as deploy.
- Rolls back application code only; it does not downgrade the database. The
  systemd pre-start migration runner still executes. Confirm the selected
  application ref can run against the current schema; if not, use the
  documented database recovery procedure instead of treating code rollback as
  a database rollback.

Readiness is a local backend/database/schema check, not an external Nginx,
Cloudflare, provider, or browser check. Verify public JSON/SSE endpoints and
React page reloads separately. Immutable, CI-verified release eligibility is
tracked in [#520](https://github.com/NPGrant81/fantasy-football-pi/issues/520);
this health gate does not implement that eligibility policy.

## Backup recovery drill

`scripts/validate_backup_recovery.sh` creates a backup, checks freshness, runs
the existing restore preflight, then calls `scripts/verify_backup_restore.py`
to actually restore the archive. A dry-run alone is not recovery evidence.

- Set `DB_URL` (or `DATABASE_URL`) and `BACKUP_DIR`. Use a quiescent source or
  pause application writes while taking the backup and collecting its manifest.
- SQLite restores into a temporary directory and opens the existing source
  read-only. PostgreSQL creates a uniquely named `ffpi_recovery_<uuid>` database,
  restores there, and drops only the database this invocation created.
- PostgreSQL requires compatible `createdb`, `pg_dump`, `pg_restore`, and
  `dropdb` tools plus permission to create/drop the disposable database. Do not
  grant broader production privileges solely to run this script; use an
  appropriately controlled recovery host/role.
- Compares table/column names, row counts, and the first five primary-key-ordered
  rows per table. Tables without a primary key have schema/count checks only.
  This is a sampled integrity check, not a byte-for-byte data audit.
- Failure is explicit and nonzero. The script never accepts an existing
  database as a restore destination. Test archives and the source are retained.
- PostgreSQL round-trip coverage runs against an owned source database in the
  GitHub Actions service; local SQLite coverage runs without PostgreSQL.

To check an existing archive directly:

```bash
python scripts/verify_backup_restore.py --archive /path/to/backup.dump.gz
```

Successful source tests do not establish that the Pi's backup schedule,
permissions, retention, or operator recovery procedure have been verified.

## UI automation evidence

The UI workflow owns one Vite process, waits for an HTTP-ready page with bounded
retries, and runs accessibility and screenshot checks against that same server.
It records actual step outcomes and retains startup diagnostics even on failure.
Screenshot capture uses mocked responses and is not end-to-end provider or
database integration proof. The existing git-status baseline check has no
tracked screenshots to compare, so it is not pixel-diff evidence; a real
baseline strategy is tracked separately in
[#538](https://github.com/NPGrant81/fantasy-football-pi/issues/538).

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
