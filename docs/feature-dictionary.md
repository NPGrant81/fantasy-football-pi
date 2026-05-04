# Feature Dictionary Standards (Issue #113)

## Purpose

This document defines the repository-wide standards for machine-learning and analytics
feature definitions. It complements the canonical feature registry in
`etl/feature_registry.yml` and the detailed ML feature reference in
`docs/ml-feature-specification.md`.

Use this file to enforce naming, ownership, and versioning rules when adding or
changing features used by:

- ETL training datasets
- online recommendation serving
- simulation and post-draft analysis outputs

## Canonical Sources

- Registry of record: `etl/feature_registry.yml`
- Computation modules: `etl/transform/ml_features.py` and related ETL transforms
- Human-readable specification: `docs/ml-feature-specification.md`

If this file conflicts with `etl/feature_registry.yml`, the registry is
authoritative and this document must be updated in the same PR.

## Required Metadata for Every Feature

Each new feature entry must include:

- `name`: snake_case unique identifier
- `level`: one of `player_season`, `owner_season`, or `draft_season`
- `description`: plain language purpose
- `formula`: deterministic computation definition
- `inputs`: upstream columns/tables used
- `offline`: whether feature is available in ETL/training pipelines
- `online`: whether feature is safe for request-time serving
- `temporal_leakage_guard`: rule preventing future-data leakage
- `null_threshold_pct`: expected upper bound for null rates
- `owner`: responsible team/persona for maintenance

## Naming and Schema Rules

- Use `snake_case` for feature names and derived columns.
- Avoid overloaded names; one name must map to one formula.
- Use explicit suffixes when units matter:
  - `_pct` for percentages in 0.0-1.0 form
  - `_rate` for rates
  - `_count` for integer counts
  - `_score` for normalized/composite model inputs
- Boolean features must use `is_` or `has_` prefixes.

## Temporal and Leakage Rules

- Features using finalized season outcomes are `online: false`.
- Features served in APIs must be computable without future weeks or post-draft
  totals that are unavailable at request time.
- Historical aggregates must support `reference_season` filtering or an
  equivalent deterministic cutoff.

## Compatibility and Change Policy

Feature changes must be categorized as:

1. Patch: no schema/name change, bug fix only.
2. Minor: additive feature with backward-compatible outputs.
3. Major: rename/removal/formula change that breaks comparability.

For major changes:

- Add migration notes in PR description.
- Update downstream consumers (model serving, analytics routers, simulation).
- Add or update tests that cover both old and new behavior where transition is
  needed.

## Pull Request Checklist

- Updated `etl/feature_registry.yml`.
- Updated `docs/ml-feature-specification.md` if formulas or semantics changed.
- Added or updated feature tests under ETL/backend test suites.
- Confirmed `online` and `offline` flags still reflect runtime behavior.
- Documented version impact in `docs/model-versioning.md` if model inputs changed.
