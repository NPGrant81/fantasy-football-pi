---
name: pr-preflight
description: "Preflight workflow for long-lived branches and PR readiness. Use when: preventing merge conflicts, syncing with main, avoiding coverage artifact churn, validating required check context mapping, or enabling git rerere."
argument-hint: "Optional: mode (status | run-local-checks)"
---

# PR Preflight

## Why This Exists
Long-lived branches frequently fail late in CI due to branch drift, stale required-check context names, and noisy generated artifacts. This skill standardizes a quick preflight routine before opening or updating a PR.

## Policy Guardrails
- Sync from `main` daily on active feature branches.
- Keep generated coverage artifacts out of tracked PR changes.
- Run a deterministic preflight before push/PR updates.
- Keep required-check contexts versioned and aligned with workflow job names.
- Enable `git rerere` to auto-apply known conflict resolutions.

## Commands

From repo root:

```bash
python scripts/pr_preflight.py
```

Optional local smoke commands (if desired):

```bash
python scripts/pr_preflight.py --run-local-checks
```

## What The Script Validates
1. Working tree cleanliness (`git status --porcelain`)
2. Fresh `origin/main` fetch
3. Branch drift from `origin/main`
4. Merge-risk simulation (`git merge-tree` conflict markers)
5. Coverage artifact churn in current changes
6. Required check mapping file and CI workflow alignment
7. `git rerere` status and remediation guidance

## Required Context Mapping
The canonical required-check mapping is versioned in:
- `.github/required-check-contexts.json`

Keep this file in sync whenever required checks or workflow job names change.
