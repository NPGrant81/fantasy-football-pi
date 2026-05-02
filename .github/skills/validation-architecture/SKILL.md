---
name: validation-architecture
description: 'Multi-library validation architecture for Fantasy Football PI (Pydantic, Cerberus, Marshmallow, Pandera, Great Expectations), including boundaries, fallback behavior, CI gates, and failure triage. Use when: designing validation, adding data pipelines, hardening ingestion, or reviewing data-quality robustness.'
argument-hint: 'Optional: focus area (boundary | dynamic-rules | dataframe | expectations | ci | triage)'
---

# Validation Architecture

## Why This Exists
Issue #76 introduced a multi-library validation strategy. This skill prevents drift by defining where each validator belongs, how failures surface, and how CI enforces coverage.

## Library Responsibilities

| Library | Primary Role | Layer |
|--------|---------------|-------|
| Pydantic | strict boundary/type validation | API + backend service boundaries |
| Cerberus | dynamic business rule validation | backend service dynamic rules |
| Marshmallow | serialization/deserialization normalization | backend serialization outputs |
| Pandera | DataFrame schema contracts | ETL transform/load |
| Great Expectations | dataset expectation checks and quality reporting | ETL quality gate |

## Source of Truth
- Strategy doc: `docs/DATA_VALIDATION_STRATEGY.md`
- Backend validators: `backend/services/validation_service.py`
- ETL validators: `etl/validation/dataframe_validation.py`, `etl/validation/great_expectations_runner.py`

## Boundary Rules
1. API and command inputs must pass Pydantic boundary checks before mutation.
2. Dynamic domain constraints must run through Cerberus checks (or deterministic fallback if library unavailable).
3. Tabular ETL loads must pass Pandera schema checks (or deterministic fallback) before DB writes.
4. Great Expectations checks run after schema validation and before final load commit.
5. Validation failures are explicit and fail fast; do not silently coerce invalid data.

## Fallback Contract
If optional engines are unavailable, fallback validators must:
1. Return explicit engine in report payload (for example `engine=fallback`).
2. Return deterministic errors for the same input.
3. Produce CI-visible failure messages that include failing fields and rule context.

## CI Requirements
1. CI must install `backend/requirements-validation.txt` in validation-capable jobs.
2. CI must run `backend/tests/test_validation_service.py` and `etl/test_validation_framework.py` as explicit checks.
3. Failure output must show whether failure came from full engine or fallback engine.

## Always Do
- Add validation tests whenever adding/modifying schemas or rule sets.
- Document new validation boundaries in `docs/DATA_VALIDATION_STRATEGY.md`.
- Keep rule changes backward-compatible unless migration notes are provided.

## Never Do
- Never bypass validation in production ingestion paths.
- Never hide validation failures behind generic 500 errors.
- Never introduce a new validator library without updating this skill and strategy doc.

## Related Skills
- [API Patterns](../api-patterns/SKILL.md)
- [Testing](../testing/SKILL.md)
- [ML Ops](../ml-ops/SKILL.md)
- [Maintenance](../maintenance/SKILL.md)
