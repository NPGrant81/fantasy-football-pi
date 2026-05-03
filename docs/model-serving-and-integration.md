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
- `current` resolves to `historical-rankings-v1` in the current implementation.
- Response always echoes both requested and resolved versions.

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
