# Dead Code Detection And Safe Prune Workflow

Issue reference: #301

## Purpose

This workflow detects stale or dead code candidates without blindly deleting files.
Signals are merged from static analysis, runtime coverage, and local dependency graphing.

## Report Sources

1. Python static analysis
  - `vulture` for unused functions, classes, and symbols.
  - `pyflakes` for unused imports/variables and unreachable-style findings.

2. Frontend static analysis
  - ESLint `no-unused-vars` and `no-unused-private-class-members` rule output.

3. Runtime coverage hotspots
  - Backend from `backend-coverage.xml`.
  - Frontend from `coverage-final.json`.

4. Dependency graph orphan scan
  - Python local import graph over `backend/`, `etl/`, and `scripts/`.
  - Frontend import graph over `frontend/src`.

## CI Behavior

The CI pipeline generates a dead-code report on pull requests by running:
- `.github/workflows/ci.yml` job: `dead-code-report`
- Script: `scripts/dead_code_report.py`

Artifacts produced:
- `dead-code-report.json`
- `dead-code-report.md`

## Safe Prune Checklist

Use this checklist before deleting any candidate:

1. Confirm reference safety
  - Search for dynamic imports (`importlib`, `__import__`, `import()`), reflection, plugin registration, or string-based dispatch.
  - Confirm route registration, background schedulers, and startup hooks do not reference the candidate.

2. Confirm runtime/config safety
  - Confirm no Docker, systemd, Nginx, shell scripts, or deployment docs depend on the candidate path.
  - Confirm no ETL job or cron workflow references the candidate.

3. Validate behavior safety
  - Add/update regression tests that exercise nearby behavior.
  - Run backend tests, frontend tests, and smoke flows relevant to the candidate.

4. Execute safe deletion
  - Prefer small, isolated PRs for removals.
  - Link each removal to report evidence and reviewer confirmation.

5. Post-removal verification
  - Re-run CI and verify no new import/runtime errors.
  - Confirm dead-code report no longer flags removed paths.

## Notes On False Positives

Expected false-positive classes include:
- Dynamically imported modules
- Files discovered by naming convention
- Router modules loaded indirectly
- Optional feature flags and staged migration code

Treat the report as a triage queue, not an automated deletion command.
