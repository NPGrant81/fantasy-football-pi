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

- `season` is required.
- `owner_id` is optional. When omitted, the endpoint defaults to the authenticated request owner.
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
  "requested_owner_id": 1,
  "owner_id": 1,
  "season": 2026,
  "league_id": 1,
  "recommendation_count": 3,
  "provenance": {
    "model_source": "historical-rankings-service",
    "model_version_alias_requested": "current",
    "model_version_alias_resolved": "historical-rankings-v1",
    "model_route_strategy": "current-alias",
    "canary_applied": false,
    "feature_contract_version": "issue-106-v1",
    "request_owner_source": "payload",
    "fallback_invoked": false,
    "fallback_reason": null
  },
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

### Owner Context Resolution

- If `owner_id` is provided, that owner is used (commissioner or superuser may request other owners).
- If `owner_id` is omitted, the authenticated user id is used automatically.
- Non-commissioners cannot request another owner explicitly.

This supports app-personalized responses for whoever is logged in while preserving commissioner workflows.

### Recommendation Semantics

- `value_score`: model-derived ranking score.
- `predicted_value`: estimated auction value.
- `recommended_bid`: budget-aware recommendation (capped if draft state budgets/slots are provided).
- `tier`: consensus tier.
- `risk_score`: normalized risk indicator based on consistency and volatility factors.
- `flags`: explanatory tags such as `high-risk`, `scarcity-boost`, `budget-capped`.

## Model Versioning

- Request-level `model_version` is accepted for future explicit routing.
- `current` resolves via `MODEL_SERVING_CURRENT_ALIAS` (defaults to `historical-rankings-v1`).
- Response always echoes both requested and resolved versions.

Routing hooks:

- `MODEL_SERVING_CURRENT_ALIAS` controls the alias behind `current`.
- `MODEL_SERVING_CANARY_ALIAS` sets the canary alias target.
- `MODEL_SERVING_CANARY_PERCENT` controls canary traffic when `model_version=canary`.

The response `provenance` block indicates whether canary routing was applied.

## Error Handling

- `400`: invalid request context (for example, user not in a league)
- `403`: cross-owner or cross-league access violation
- `404`: target owner not found in league

Errors are returned as typed `detail` payloads:

```json
{
  "code": "OWNER_SCOPE_FORBIDDEN",
  "message": "Owners can only request model recommendations for themselves",
  "retryable": false
}
```

Current error codes:

- `MODEL_CONTEXT_INVALID`
- `OWNER_NOT_FOUND`
- `OWNER_SCOPE_FORBIDDEN`
- `CROSS_LEAGUE_FORBIDDEN`

## Logging

The serving endpoint logs request and response metadata with live observability counters:

- owner, season, league, resolved model version, limit
- recommendation count
- `request_latency_p95`
- `prediction_error_rate`
- `fallback_invocation_rate`

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

## Dependency Note

- Backend serving observability uses `prometheus_client`.
- Ensure backend environments install dependencies from `backend/requirements.txt` (or locked equivalent) so observability instrumentation is available.

## Model Serving Ops Checklist

Use this checklist before and during model-serving rollout windows.

### Pre-Deployment

1. Confirm dependency parity (`requirements.txt` and lockfile include serving observability deps).
2. Set alias env vars for routing:
  - `MODEL_SERVING_CURRENT_ALIAS`
  - `MODEL_SERVING_CANARY_ALIAS`
  - `MODEL_SERVING_CANARY_PERCENT`
3. Run model-serving contract tests and verify typed error payload compatibility.
4. Confirm fallback behavior is documented for no-candidate and degraded-service paths.

### Deployment

1. Start with `MODEL_SERVING_CANARY_PERCENT=0`.
2. Increase canary gradually (for example 5 -> 10 -> 25 -> 50).
3. Monitor key metrics each step:
  - `request_latency_p95`
  - `prediction_error_rate`
  - `fallback_invocation_rate`
4. Hold or rollback if latency/error/fallback regress beyond accepted thresholds.

### Rollback

1. Set `MODEL_SERVING_CANARY_PERCENT=0` immediately.
2. Point `MODEL_SERVING_CURRENT_ALIAS` to last known-good alias.
3. Re-run contract smoke checks and verify metrics return to baseline.
4. Record incident notes with root-cause and follow-up actions.

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
  - Compare owner-specific outcome deltas for the authenticated request owner against current champion.
6. Promote or reject
  - Promote only if all quality gates pass and no required slice regresses beyond threshold.
  - Store a decision record with rationale, metrics, and artifact references.
7. Serve and observe
  - Update serving resolution only after promotion gates pass.
  - If alias hooks are configured, rotate the current alias. Otherwise, promote via code/config deployment for the champion model selection.
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
- no significant degradation on required slices (authenticated request owner and key positions)
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
