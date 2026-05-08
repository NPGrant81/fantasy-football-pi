# Markdown Governance Sweep Report

> Historical snapshot: this report reflects governance status as of 2026-05-05.
> Current governance status is tracked through `docs/governance/doc_review_registry.json` and `docs/PATTERN_COMPLIANCE_MATRIX.md`.

Updated: 2026-05-05
Tracker: #156

## Scope
Pass 3 focused on command freshness, deployment/milestone governance linkage, and status-note hygiene updates across operational docs.

## Files Reviewed
- `docs/API_PAGE_MATRIX.md`
- `docs/DEPLOYMENT_WORKFLOWS.md`
- `docs/DEPENDENCY_MAINTENANCE.md`
- `docs/DOCUMENTATION_UPDATE_PROCESS_PLAN.md`
- `docs/CLI_CHECKIN_LESSONS_LEARNED.md`
- `docs/TESTING_SESSION_SUMMARY.md`
- `docs/DOC_ISSUE_CORRELATION_MAP.md`
- `docs/ISSUE_STATUS.md`
- `ISSUE_STATUS.md`

## Findings
1. Internal API matrix still documented legacy backend port (`8000`) instead of current default dev behavior (`8010`).
2. Several operational docs lacked explicit governance tracking back to issue `#156`, which increased drift risk.
3. Historical testing summary needed an explicit current review date to reduce stale-status misreads.
4. Doc-to-issue map was missing some actively used governance-linked docs.

## Changes Applied
1. Updated internal API base URL guidance in `docs/API_PAGE_MATRIX.md` to default `http://127.0.0.1:8010` with `BACKEND_PORT` override note.
2. Added Issue `#156` tracker references in:
   - `docs/DEPLOYMENT_WORKFLOWS.md`
   - `docs/DEPENDENCY_MAINTENANCE.md`
   - `docs/DOCUMENTATION_UPDATE_PROCESS_PLAN.md`
   - `docs/CLI_CHECKIN_LESSONS_LEARNED.md`
3. Updated `docs/TESTING_SESSION_SUMMARY.md` metadata with `Last Reviewed: May 5, 2026` and explicit historical-snapshot status line.
4. Expanded `docs/DOC_ISSUE_CORRELATION_MAP.md` entries to include:
   - `docs/DEPENDENCY_MAINTENANCE.md` -> `#156, #113`
   - `docs/DOCUMENTATION_UPDATE_PROCESS_PLAN.md` -> `#156`
   - `docs/DEPLOYMENT_WORKFLOWS.md` -> `#156`
5. Added pass-3 sweep note entries in `docs/ISSUE_STATUS.md` and `ISSUE_STATUS.md` for governance traceability.

## Direction/Command Validation Notes
- Local dev startup defaults continue to use backend port `8010` (for example via `start-dev.sh`).
- Production/cloudflared/systemd docs continue to use `8000` in deployment contexts; this pass treated that as environment-specific and focused on clarifying dev-facing docs.

## Architecture and Regression Guardrail
- This pass is documentation/governance only and introduces no backend, frontend, schema, API contract, or infrastructure architecture changes.
- March 2026 implementation direction remains intact; this sweep updates references and traceability to reduce drift, not to revert behavior.

## Remaining Work (Next Pass)
1. Sweep milestone docs for state/checklist consistency with issue close-out evidence (especially milestone-level completion criteria).
2. Decide whether to keep or remove in-repo nested workspace copies (for example `fantasy-football-pi-issue-114/`) from a governance and drift perspective.
3. Add an automated lint/check step for mandatory `Tracker:` metadata in designated governance/process docs.
