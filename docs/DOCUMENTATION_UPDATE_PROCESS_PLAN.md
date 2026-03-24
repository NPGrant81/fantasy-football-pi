# Documentation Update Process Plan

## Problem Statement

Documentation has grown quickly and now includes overlapping guidance across root docs, docs/ references, runbooks, and generated status notes. This creates stale or conflicting instructions during future updates.

## Goal

Create a repeatable process that keeps documentation current, deconflicted, and traceable to implementation changes.

## Scope

- Doc ownership and review cadence
- Conflict detection between canonical and mirrored docs
- Explicit deprecation workflow for stale docs
- PR-level checks for doc conflicts and outdated references

## Proposed Workstreams

### 1. Canonical Source Mapping

- Define one canonical file per topic area (architecture, deployment, testing, issue status, UI standards).
- Mark mirror files as derived or read-only with a short header.
- Add canonical path metadata to docs/governance/doc_review_registry.json entries.

### 2. Staleness and Conflict Detection

- Extend scripts/docs_review_sweep.py to detect:
  - duplicate topic files with divergent content blocks
  - references to archived/deprecated files
  - contradictory status markers (for example OPEN vs CLOSED for same issue/topic)
- Fail scheduled governance sweep for confirmed conflicts.

### 3. Deprecation Workflow

- Add a standard "Deprecated" header block template.
- Move retired docs under docs/archive/ with redirect links from originals.
- Keep deprecation date and replacement doc path in each retired file.

### 4. PR Gate Enhancements

- Add CI check that requires docs updates when code touches mapped domains.
- Require explicit "doc impact" section in PR template for backend/frontend/system changes.
- Add optional auto-comment summarizing stale/conflicting doc findings.

### 5. Operating Cadence

- Weekly scheduled sweep (already implemented).
- Monthly docs hygiene triage review.
- Quarterly deep cleanup sprint for archives and canonical map updates.

## Milestones

1. M1: Canonical map and deprecation template approved.
2. M2: Conflict detection implemented in scripts/docs_review_sweep.py.
3. M3: CI gate for doc impact enabled.
4. M4: Archive cleanup and redirect coverage complete.

## Definition of Done

- Canonical map exists for all high-change docs.
- Stale/conflicting docs are automatically flagged in CI/scheduled sweep.
- Deprecated docs consistently point to replacements.
- PR flow enforces doc impact review on code changes.
