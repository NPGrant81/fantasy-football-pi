# Post-Draft Analysis Pipeline — Fantasy Football PI

**Version:** 1.0
**Effective date:** 2026-05-04
**Issue:** #113
**Milestone:** M8 — ML Draft Analyzer and In-Season Intelligence
**Owner:** analytics

---

## 1. Purpose

This document describes the post-draft analysis pipeline — the system that
evaluates each team's draft outcome and produces owner-facing season outlook
data immediately after the auction closes.

It covers:
- What the pipeline computes and why
- The data flow from draft results to API response
- The confidence and degraded-mode behavior
- How to validate and test the pipeline

---

## 2. Inputs

The post-draft analysis pipeline consumes data that is available immediately after the draft:

| Input | Table / Source | Notes |
|---|---|---|
| Draft picks | `draft_picks` (ORM: `DraftPick`) | One row per player acquired at auction |
| Player projections | `players.projected_points` (ORM: `Player`) | Pre-season projected fantasy points |
| Player positions | `players.position` | QB, RB, WR, TE, DEF, K |
| Owner roster | Joined from `draft_picks` + `users` | All owners in the league |
| League configuration | `leagues` | Used to validate league membership |

> **Note:** The pipeline does **not** require historical scoring data, model predictions,
> or simulation output. It runs on draft results + projections alone, which makes it
> available immediately after the auction ends.

---

## 3. Pipeline Steps

### Step 1 — Load draft picks

Query `draft_picks` joined to `players` for the given `league_id` and `season`.
Historical (excluded) owner records (`hist_%` usernames) are filtered out.

Deduplication: If the same `(owner_id, player_id)` pair appears more than once, only
the first occurrence is counted.

### Step 2 — Compute per-owner metrics

For each owner, compute:

| Metric | Formula |
|---|---|
| `projected_points` | `SUM(player.projected_points)` for all valid draft picks |
| `roster_size` | Count of valid picks (after dedup and exclusion) |
| `positional_balance_score` | Derived from how evenly filled each starter slot is vs expected counts |
| `risk_score` | Fraction of roster with missing or zero projections |
| `strength_score` | Blend of `projected_points` rank and `positional_balance_score` |
| `confidence_score` | 0–1 score based on data completeness (see §4) |
| `confidence_label` | `"high"` / `"moderate"` / `"low"` based on `confidence_score` thresholds |

### Step 3 — Rank teams

All owners are ranked by `projected_points` descending.
Ties are broken by `strength_score`.

### Step 4 — Compute league-relative metrics

For each owner:
- `projected_points_vs_league_avg` = `projected_points - mean(projected_points_all_owners)`

### Step 5 — Build owner focus (optional)

If `owner_id` is supplied, the service additionally builds a `PostDraftOwnerFocus`
object containing:
- The owner's rank and metrics
- `positional_gaps`: positions where the owner has fewer starters than the league average
- `summary`: plain-English sentence summarizing the outlook

### Step 6 — Return diagnostics

The pipeline always returns data quality diagnostics alongside results:
- `total_draft_rows`, `included_rows`, `skipped_rows`
- `duplicate_rows_skipped`, `invalid_projection_rows`, `unknown_position_rows`
- `projection_coverage`: fraction of picks that had a non-null, non-zero projection

---

## 4. Confidence Model

The `confidence_score` is a 0–1 value computed from data completeness.
It reflects how much trust to place in the projected points figures.

| Threshold | Label | Meaning |
|---|---|---|
| ≥ 0.75 | `high` | ≥ 75 % of picks have valid projections; rankings are reliable |
| 0.50–0.74 | `moderate` | Some projection gaps; rankings directionally correct |
| < 0.50 | `low` | Significant missing data; treat rankings as rough estimates |

When `confidence_label` is `"low"` or `"moderate"`, the API response includes a
`diagnostics` block and `meta.confidence_context` explaining what data was missing.

### Degraded mode

If there are **no valid draft rows** for a league/season, the pipeline returns:
- Empty `teams` list
- `confidence_label: "low"`
- `meta.baseline_only: true`
- `meta.model_signal_available: false`

The endpoint does **not** raise a 500 — it returns a valid, empty response with
explanatory diagnostics.

---

## 5. API Endpoint

```
GET /analytics/league/{league_id}/post-draft-outlook
```

### Query parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `season` | int | yes | The draft season year (e.g., `2026`) |
| `owner_id` | int | no | If provided, includes owner-specific focus and positional gap analysis |

### Response shape (abbreviated)

```json
{
  "teams": [
    {
      "owner_id": 1,
      "owner_name": "Alice",
      "team_name": "Alice's Team",
      "rank": 1,
      "roster_size": 16,
      "projected_points": 1842.5,
      "projected_points_vs_league_avg": 112.3,
      "risk_score": 0.06,
      "positional_balance_score": 0.87,
      "strength_score": 0.91,
      "confidence_score": 0.83,
      "confidence_label": "high"
    }
  ],
  "owner_focus": {
    "owner_id": 1,
    "rank": 1,
    "projected_points": 1842.5,
    "projected_points_vs_league_avg": 112.3,
    "risk_score": 0.06,
    "confidence_score": 0.83,
    "confidence_label": "high",
    "positional_gaps": [],
    "summary": "Your team projects as the top roster this season with strong positional balance."
  },
  "diagnostics": {
    "total_draft_rows": 192,
    "included_rows": 192,
    "skipped_rows": 0,
    "duplicate_rows_skipped": 0,
    "invalid_projection_rows": 4,
    "unknown_position_rows": 0,
    "projection_coverage": 0.979
  },
  "meta": {
    "method": "projection_baseline",
    "model_signal_available": false,
    "simulation_signal_available": false,
    "baseline_only": true,
    "confidence_context": { ... }
  }
}
```

---

## 6. Code Locations

| Component | File |
|---|---|
| Service logic | `backend/services/season_outlook_service.py` |
| Response schemas | `backend/schemas/season_outlook.py` |
| Router endpoint | `backend/routers/analytics.py` → `get_post_draft_outlook` |
| Tests | `backend/tests/test_analytics.py` → `test_post_draft_outlook_*` |
| Frontend panel | Planned (not yet implemented). Current owner-facing analytics surface is `frontend/src/pages/team-owner/YourLockerRoom.jsx`. |
| Frontend tests | Planned alongside panel implementation. |

---

## 7. Future Enhancements

When ML model predictions are available (post Issue #108 promotion):
- `meta.model_signal_available` will become `true`
- `projected_points` will be augmented or replaced with model-predicted scores
- Confidence scores will incorporate model calibration quality

When Monte Carlo simulation is integrated (Issue #107):
- `meta.simulation_signal_available` will become `true`
- Team ranking distributions will be available alongside point estimates

---

## 8. Testing

### Backend tests

```bash
python -m pytest backend/tests/test_analytics.py -k "post_draft" -v
```

Covers:
- `test_post_draft_outlook_payload_and_owner_focus` — full happy-path contract
- `test_post_draft_outlook_contract_shape_is_stable` — response schema regression
- `test_post_draft_outlook_degraded_metadata_for_messy_inputs` — partial projections
- `test_post_draft_outlook_degraded_when_no_roster_rows` — empty draft
- `test_post_draft_outlook_rejects_owner_outside_league` — auth guard

### Frontend tests

```bash
npx vitest run src/components/draft/insights/__tests__/PostDraftOutlookPanel.test.jsx
```

---

## 9. Related Documents

- [ML Feature Specification](ml-feature-specification.md) — features that power future model-augmented outlook
- [Model Versioning and Promotion Rules](model-versioning.md) — when model signal becomes available
- [Draft Day Advisor Mode](DRAFT_DAY_ADVISOR_MODE.md) — live draft pipeline (upstream of this)
- [Feature Dictionary](feature-dictionary.md) — feature definitions referenced by this pipeline
