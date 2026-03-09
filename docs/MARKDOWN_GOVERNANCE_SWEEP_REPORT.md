# Markdown Governance Sweep Report

Updated: 2026-03-08
Tracker: #156

## Scope
Pass 2 focused on stale status claims, direction freshness, and doc-to-issue traceability for core management/testing docs.

## Files Reviewed
- `docs/TESTING_SESSION_SUMMARY.md`
- `docs/PROJECT_MANAGEMENT.md`
- `docs/ISSUE_STATUS.md`
- `PROJECT_MANAGEMENT.md`
- `ISSUE_STATUS.md`
- `docs/INDEX.md`

## Findings
1. Story-state drift existed in multiple docs (`6.2`, `6.4`, `7.3` statuses not consistently aligned).
2. Some docs contained static historical counts that could be interpreted as live status.
3. Backlog sections still listed completed scope (`7.3`) without clarifying it as optional polish only.
4. No explicit mapping artifact existed to correlate key docs with owning issues.

## Changes Applied
1. Marked Story `6.4` as completed where stale and retained Story `6.2` as partial with follow-up issue `#154`.
2. Updated root/doc issue status metadata and recommendations to avoid stale directional guidance.
3. Added historical-context disclaimer to `docs/TESTING_SESSION_SUMMARY.md` and pointed readers to current source-of-truth docs.
4. Clarified backlog references for Story `7.3` as enhancement-only (core delivered).
5. Added `docs/DOC_ISSUE_CORRELATION_MAP.md` to tie key docs to issue ownership.

## Direction/Command Validation Notes
- Current test command convention remains aligned with workspace practice: `python3.13.exe -m pytest ...`.
- Active issue-board guidance remains: use dynamic query (`gh issue list --state open`) rather than fixed counts in docs.

## Remaining Work (Next Pass)
1. Broader sweep of milestone/legacy docs for old branch/date metadata and outdated assumptions.
2. Cross-check doc instructions against current scripts for deploy/security/backup workflows.
3. Add missing issue references to docs that describe active workstreams without direct tracker links.
