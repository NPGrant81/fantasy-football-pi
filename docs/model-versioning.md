# Model Versioning and Promotion Policy (Issue #113)

## Purpose

This document standardizes model lifecycle controls for Draft Day recommendations
and post-draft outlook workflows.

It builds on the detailed MLOps process in `docs/model-serving-and-integration.md`
and the evaluation template in `docs/model-training-eval.md`.

## Version Format

Use semantic model versions:

- `major.minor.patch` (example: `2.3.1`)

Interpretation:

- Major: breaking input/output or objective changes.
- Minor: additive capability or materially new feature set with compatible API.
- Patch: bug fix or calibration update with same feature contract.

## Required Artifacts Per Version

Each promoted version must have:

- dataset version identifier and feature registry hash
- training configuration (seed, split, hyperparameters)
- offline evaluation report (global + required slices)
- simulation impact comparison versus champion
- promotion decision record (approve/reject + rationale)
- rollback target (previous stable champion)

## Promotion Gates

Promotion is allowed only when all gates pass:

- No primary metric regression beyond allowed threshold.
- No required-slice degradation beyond threshold.
- Reproducible rerun within tolerance band.
- Simulation impact neutral or positive for required owner slices.
- Data-contract validation passes for serving payload schema.

See `docs/model-serving-and-integration.md` for baseline thresholds and drift policy.

## Serving Resolution Rules

- Serving must resolve to one explicit champion version.
- Challenger versions must not be default without gate approval.
- API responses should expose resolved model version for traceability.
- Any model default change must include release notes in the PR.

## Deprecation Policy

A model version can be deprecated when:

- superseded by a promoted champion
- drift or reliability incidents exceed defined tolerance
- required data contract can no longer be satisfied safely

Deprecation requires:

- status update in release notes/PR
- rollback confirmation path
- retention of artifacts for auditability

## Incident and Rollback Protocol

On critical drift or production degradation:

1. Freeze automatic promotion.
2. Roll back serving resolution to last stable champion.
3. Log incident summary with impacted slices and metrics.
4. Schedule challenger retraining with corrected data/features.

## Pull Request Checklist

- Version bump rationale included.
- Artifact links included in PR body.
- Promotion gate evidence included.
- Rollback target and validation steps included.
- Consumer docs updated if API behavior changed.
