# Model Training and Evaluation

## Purpose

This document is the execution template for Issue #108 model training cycles.
Use it for every champion or challenger run so model decisions are auditable and comparable.

## Run Metadata

- Run ID:
- Date:
- Owner:
- Data version:
- Feature schema hash:
- Code commit SHA:
- Random seed:
- Split policy (time-based):

## Targets and Labels

- Primary target(s):
- Label generation logic:
- Exclusions and assumptions:

## Candidate Models

- Baseline:
- Interpretable benchmark:
- Advanced candidate(s):
- Ranking objective candidate (if used):

## Offline Metrics

### Regression

- MAE:
- RMSE:
- Median AE:

### Ranking

- NDCG@K:
- MAP@K:

### Calibration

- Bucket error summary:
- Calibration drift vs champion:

## Slice Metrics

- OwnerID=1 metrics:
- Position slices (QB/RB/WR/TE/DEF/K):
- High-value player slice:

## Simulation Impact (Issue #107 Bridge Path)

- Monte Carlo config used:
- Champion outcome:
- Challenger outcome:
- Delta summary:
- Decision-impact notes:

## Promotion Gates

- Error gate pass/fail:
- Ranking gate pass/fail:
- Slice degradation gate pass/fail:
- Reproducibility gate pass/fail:
- Simulation impact gate pass/fail:

## Drift Checks

- PSI summary:
- Performance drift summary:
- Decision-impact drift summary:

## Decision Record

- Decision: promote or reject
- Reason:
- Rollback artifact (if applicable):
- Follow-up actions:

## Model Card Link

- Model card URI:
