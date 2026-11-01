# Required Checks Contract

This document records the target branch-protection contract for `main`. Repository
settings are enforced separately under issue #520; this file does not claim those
settings are already active.

## Merge-blocking checks

Configure branch protection to require these stable check names:

- `ci-gate`
- `gitleaks`

`ci-gate` is the aggregate application gate. Its upstream jobs own backend tests,
Alembic graph validation, migration application, frontend lint/tests/build, API
integration, end-to-end checks, and repository hygiene. The security and
cross-platform workflows use change-aware jobs, so their individual checks may
be skipped or absent for otherwise valid PRs and must not be required directly.

## Operational checks

The following scheduled/manual workflows report operational health and must not
be configured as PR merge checks:

- `Deployment Secrets Precheck`
- `Source Prechecks`
- `Sync NFL Rosters`
- `Dependency Check`
- `Docs Governance Sweep`

Operational integrations report `PASS`, `FAIL`, or `NOT_CONFIGURED`. A disabled
integration may report `NOT_CONFIGURED`, but skipped work must never be described
as successfully executed.

## Change control

When a required job ID or display name changes, update this file and branch
protection in the same issue. Validate the resulting settings through the GitHub
API and attach non-secret evidence to the issue.