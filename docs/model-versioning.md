# Model Versioning and Promotion Rules — Fantasy Football PI

**Version:** 1.0
**Effective date:** 2026-05-04
**Issue:** #113
**Milestone:** M8 — ML Draft Analyzer and In-Season Intelligence
**Owner:** ml-ops

---

## 1. Purpose

This document defines:

- The versioning scheme for all ML models in the platform
- The promotion criteria that a challenger model must satisfy before replacing the champion
- The artifact storage layout and retention policy
- The rollback procedure if a promoted model regresses

These rules apply to all models that are served via `POST /draft/model/predict`
and any future prediction endpoints.

---

## 2. Versioning Scheme

Models use a **semantic slug** of the form:

```
{family}-v{major}
```

Examples: `historical-rankings-v1`, `historical-rankings-v2`, `gradient-boost-v1`

### Rules

| Component | Rule |
|---|---|
| `family` | Short kebab-case descriptor matching the training approach (e.g. `historical-rankings`, `gradient-boost`, `rf-regressor`) |
| `major` | Increment on any breaking change: new feature set, new target definition, architecture change |
| No minor/patch | Minor improvements do not change the slug; document in run log only |

### "current" alias

The string `"current"` (and synonyms `"latest"`, `"default"`) always resolves
to the promoted champion via `_resolve_model_version()` in
`backend/routers/draft.py`. At time of writing this resolves to
`historical-rankings-v1`.

To change the champion, update the return value of `_resolve_model_version()`
**after** all promotion gates pass (see §4).

---

## 3. Artifact Storage

All trained model artifacts are stored under:

```
backend/data/models/{family}-v{major}/
  model.pkl              # serialized estimator (joblib or pickle)
  feature_schema.yml     # list of input features at training time
  metrics.json           # offline evaluation metrics from training run
  model_card.md          # human-readable summary (see §6)
  run_log.md             # link to completed training-eval template
```

### Retention policy

| Status | Artifact kept? | Duration |
|---|---|---|
| Champion | Yes | Until 2 seasons after demotion |
| Demoted | Yes | 1 full season after demotion, then archive |
| Rejected challenger | Yes (metrics only) | 1 season |
| Experimental / scratch | No | Delete after run review |

Archive path: `backend/data/models/archive/{family}-v{major}/`

---

## 4. Promotion Gates

A challenger must pass **all** gates before it can replace the champion.

### 4.1 Offline metric gates

Run metrics are computed on the held-out test split (latest N seasons held
out; see `docs/model-training-eval.md` for split policy).

| Metric | Gate |
|---|---|
| MAE vs champion | Challenger MAE ≤ champion MAE + 0.5 |
| RMSE vs champion | Challenger RMSE ≤ champion RMSE + 1.0 |
| NDCG@10 vs champion | Challenger NDCG@10 ≥ champion NDCG@10 − 0.01 |
| Calibration bucket error | ≤ 10 % worst-bucket error |

### 4.2 Slice gates

No position slice (QB / RB / WR / TE / DEF / K) may degrade by more than
**5 % MAE** vs the champion on the same slice.

### 4.3 Reproducibility gate

Two independent training runs on the same data version and seed must produce
MAE within **0.2** of each other.

### 4.4 Simulation impact gate

Run the Monte Carlo simulation (Issue #107 bridge path) with:
- Champion model → record average simulated finish distribution
- Challenger model → record average simulated finish distribution

Challenger passes if the simulated outcome distribution does not degrade the
**top-6 finish rate** by more than **2 percentage points** vs champion.

### 4.5 Schema compatibility gate

The challenger's `feature_schema.yml` must be a **superset** of the champion's.
All features the champion consumed must be present and identically typed.
New features in the challenger are allowed.

---

## 5. Promotion Workflow

1. Complete a training run using `docs/model-training-eval.md` template.
2. Fill in all promotion gate results in the template's "Promotion Gates" section.
3. Open a PR with the following changes:
   - New artifact directory `backend/data/models/{family}-v{major}/`
   - Updated `_resolve_model_version()` return value in `backend/routers/draft.py`
   - Completed run log linked in `model_card.md`
4. PR requires approval from at least one reviewer who has reviewed the gate results.
5. Merge to `main` triggers CI; CI must include `test_model_serving_endpoint.py`.
6. After merge, tag the commit: `model/{family}-v{major}-promoted`.

---

## 6. Model Card Template

Every promoted model must include `backend/data/models/{family}-v{major}/model_card.md`:

```markdown
# Model Card: {family}-v{major}

**Promoted:** {date}
**Training commit:** {SHA}
**Feature schema hash:** {hash}
**Champion as of:** {date}
**Demoted:** {date or "active"}

## Intended Use
{description of what the model predicts and what it is used for}

## Training Data
- Season range: {min}–{max}
- Holdout: {last N seasons}
- Row count: {N players × seasons}

## Offline Metrics (test split)
| Metric | Value |
|---|---|
| MAE | |
| RMSE | |
| NDCG@10 | |

## Known Limitations
{list any edge cases or known failure modes}

## Promotion Gate Summary
| Gate | Result |
|---|---|
| MAE | pass/fail |
| RMSE | pass/fail |
| Slice degradation | pass/fail |
| Reproducibility | pass/fail |
| Simulation impact | pass/fail |
| Schema compatibility | pass/fail |
```

---

## 7. Rollback Procedure

If a promoted model produces degraded results in production:

1. Revert `_resolve_model_version()` to the prior version string.
2. Open an emergency PR; single reviewer approval is sufficient.
3. File a post-mortem issue documenting what was missed in promotion gates.
4. Do not delete the regressed artifact — keep for post-mortem analysis.

---

## 8. Naming Conventions

| Entity | Convention | Example |
|---|---|---|
| Model family slug | `kebab-case`, describes training approach | `historical-rankings` |
| Version tag | `v{integer}`, no leading zeros | `v2` |
| Full slug | `{family}-v{major}` | `historical-rankings-v2` |
| Git tag | `model/{slug}-promoted` | `model/historical-rankings-v2-promoted` |
| Artifact directory | matches full slug | `backend/data/models/historical-rankings-v2/` |

---

## 9. Related Documents

- [Model Training and Evaluation](model-training-eval.md) — per-run template
- [Model Serving and Integration](model-serving-and-integration.md) — API contract
- [ML Feature Specification](ml-feature-specification.md) — feature contracts
- [Feature Dictionary](feature-dictionary.md) — authoritative feature definitions
