# Model Serving and Integration

## Summary

This document defines the callable model-serving contract used by the PPL Draft Analyzer and notebook clients.

Current serving implementation:

- Endpoint: `POST /draft/model/predict`
- Router: `backend/routers/draft.py`
- Ranking backbone: `backend/services/draft_rankings_service.py`
- API version: `v1`

The endpoint supports all owners and enforces league-safe access control. Non-commissioners can only request recommendations for themselves.

## Request Contract (v1)

```json
{
  "owner_id": 1,
  "season": 2026,
  "league_id": 1,
  "player_ids": [1068, 1173, 1235],
  "limit": 75,
  "model_version": "current",
  "league_config": {
    "teams_count": 12,
    "roster_size": 16,
    "salary_cap": 200,
    "position_weights": {
      "RB": 1.15,
      "WR": 1.05
    }
  },
  "draft_state": {
    "drafted_player_ids": [1114, 1224],
    "remaining_budget_by_owner": {
      "1": 143
    },
    "remaining_slots_by_owner": {
      "1": 10
    }
  }
}
```

### Field Notes

- `owner_id` and `season` are required.
- `player_ids` is optional; when provided, recommendations are filtered to this candidate pool.
- `model_version` accepts `current` (default) or explicit version identifiers.
- `draft_state` is optional and enables budget-aware bid capping.

## Response Contract (v1)

```json
{
  "api_version": "v1",
  "model_version_requested": "current",
  "model_version_resolved": "historical-rankings-v1",
  "generated_at": "2026-03-02T19:45:00.000000",
  "owner_id": 1,
  "season": 2026,
  "league_id": 1,
  "recommendation_count": 3,
  "recommendations": [
    {
      "player_id": 1068,
      "player_name": "Christian McCaffrey",
      "position": "RB",
      "value_score": 49.88,
      "recommended_bid": 74.0,
      "predicted_value": 77.54,
      "tier": "S",
      "risk_score": 18.2,
      "within_owner_budget": true,
      "flags": ["scarcity-boost"]
    }
  ]
}
```

### Recommendation Semantics

- `value_score`: model-derived ranking score.
- `predicted_value`: estimated auction value.
- `recommended_bid`: budget-aware recommendation (capped if draft state budgets/slots are provided).
- `tier`: consensus tier.
- `risk_score`: normalized risk indicator based on consistency and volatility factors.
- `flags`: explanatory tags such as `high-risk`, `scarcity-boost`, `budget-capped`.

## Model Versioning

- Request-level `model_version` is accepted for future explicit routing.
- `current` resolves to `historical-rankings-v1` in the current implementation.
- Response always echoes both requested and resolved versions.

## Error Handling

- `400`: invalid request context (for example, user not in a league)
- `403`: cross-owner or cross-league access violation
- `404`: target owner not found in league

Errors are returned as standard FastAPI HTTP errors with `detail`.

## Logging

The serving endpoint logs basic request/response metadata:

- owner, season, league, resolved model version, limit
- recommendation count

This supports debugging and lightweight monitoring without exposing private payload details.

## Analyzer Integration Flow

1. Analyzer assembles draft context:
   - owner id
   - season/league
   - candidate pool (optional)
   - current draft-state budgets and drafted players (optional)
2. Analyzer calls `POST /draft/model/predict`.
3. Analyzer maps output to UI concepts:
   - `recommended_bid` -> bid suggestion
   - `value_score` -> ranking confidence
   - `tier`/`risk_score`/`flags` -> explainability badges
4. Analyzer enforces final local safeguards before drafting.

## Notebook Integration

Notebook clients can call the same endpoint to retrieve consistent recommendation outputs for analysis, scenario testing, and dashboard materialization.

## Latency and Fallback

- v1 is synchronous and optimized for low-latency API calls.
- If advanced model artifacts are unavailable, recommendation generation still functions through the ranking backbone and returns a stable schema.

## ML Ops Pipeline Process and Methodology (Issue #108 Alignment)

This section defines the standard process for training, evaluating, promoting, and monitoring model versions used by the Draft Analyzer.

### Pipeline Stages

1. Define targets and labels
  - Primary targets can include winning bid regression, surplus value regression, and ranking quality.
  - Labels must be generated from historical finalized draft outcomes only.
  - Train, validation, and test splits must be time-based to prevent leakage.
2. Build feature matrix
  - Use the feature contracts from Issue #106 outputs.
  - Persist feature schema hash and dataset version with every run.
3. Train champion and challenger candidates
  - Train baseline and advanced candidates under the same split policy.
  - Record hyperparameters and random seed in run metadata.
4. Evaluate offline quality
  - Regression metrics: MAE, RMSE, median AE.
  - Ranking metrics: NDCG at K, MAP at K.
  - Calibration metrics for bid confidence buckets when probabilities or intervals are emitted.
5. Evaluate decision impact in simulation
  - Run Monte Carlo with candidate outputs via the ML bridge path.
  - Compare owner-specific outcome deltas (including OwnerID=1) against current champion.
6. Promote or reject
  - Promote only if all quality gates pass and no required slice regresses beyond threshold.
  - Store a decision record with rationale, metrics, and artifact references.
7. Serve and observe
  - Update the model alias for current only after promotion gates pass.
  - Monitor post-promotion drift and degradation signals.

### Required Run Artifacts

Every training run should publish:

- model artifact URI
- dataset version and feature schema hash
- training configuration (params, seed, split definition)
- evaluation report (global and slice metrics)
- simulation impact report
- model card (scope, assumptions, limitations, monitoring plan)
- champion or challenger decision record

### Candidate Model Ladder

Use a consistent progression when searching for a better outcome:

1. Baseline: seasonal and positional historical averages with inflation adjustments.
2. Interpretable benchmark: Elastic Net.
3. Tree ensembles for tabular features: Random Forest, LightGBM, CatBoost.
4. Ranking-focused objective (if ranking quality is primary): pairwise ranking or LambdaMART.
5. Optional uncertainty-aware candidate: quantile regression for bid ranges.

Selection should be based on a composite score that includes both predictive error and simulation outcome uplift.

### Accuracy and Promotion Gates

Define and enforce minimum gates before any promotion:

- no regression greater than 10 percent on primary error metrics versus champion
- no regression greater than 5 percent on ranking quality metrics
- no significant degradation on required slices (OwnerID=1 and key positions)
- reproducible rerun within accepted tolerance band
- simulation impact must be neutral or positive for required owner slices

### Drift Detection Policy

Monitor both data drift and performance drift:

- data drift
  - PSI on key numeric features (warn above 0.2, critical above 0.3)
  - distribution checks by position and owner slice
- concept and performance drift
  - rolling MAE and RMSE against champion baseline
  - rolling ranking metric deltas
  - calibration drift for predicted value buckets
- decision-impact drift
  - rolling simulation delta vs champion in projected team outcomes

Critical drift or sustained degradation should trigger challenger retraining and gate re-evaluation.

### Evaluation and Tuning Cadence

- on every data refresh: run data-contract validation and drift checks
- weekly in active draft-prep windows: run score-only evaluation against champion
- monthly: run full challenger training and evaluation cycle
- mandatory preseason refresh: full retrain, gate evaluation, model card update
- trigger-based retrain: immediate cycle on critical drift or persistent quality degradation

### Integration Contract with the Simulation Bridge

Candidates must output fields that can be translated by the existing bridge and serving contracts:

- predicted auction value
- model score or ranking signal
- consistency or reliability proxy

The bridge and serving schemas remain stable so model internals can evolve without breaking downstream consumers.
