from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SplitPolicy:
    train_end_season: int
    val_season: int
    test_season: int


SimulationEvaluator = Callable[[pd.DataFrame, pd.Series, pd.Series, int | None], dict[str, object]]


def time_split(df: pd.DataFrame, split: SplitPolicy) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if "season_year" not in df.columns:
        raise ValueError("Expected column 'season_year' for time-based split.")
    if not (split.train_end_season < split.val_season < split.test_season):
        raise ValueError(
            "Expected strict season ordering train_end_season < val_season < test_season."
        )

    train_df = df[df["season_year"] <= split.train_end_season].copy()
    val_df = df[df["season_year"] == split.val_season].copy()
    test_df = df[df["season_year"] == split.test_season].copy()

    return train_df, val_df, test_df


def _mae(y_true: pd.Series, y_pred: pd.Series) -> float:
    return float(np.mean(np.abs(y_true.to_numpy() - y_pred.to_numpy())))


def _rmse(y_true: pd.Series, y_pred: pd.Series) -> float:
    return float(np.sqrt(np.mean((y_true.to_numpy() - y_pred.to_numpy()) ** 2)))


def _median_ae(y_true: pd.Series, y_pred: pd.Series) -> float:
    return float(np.median(np.abs(y_true.to_numpy() - y_pred.to_numpy())))


def _ndcg_at_k(y_true: pd.Series, y_score: pd.Series, k: int = 25) -> float:
    if len(y_true) == 0:
        return 0.0

    order = np.argsort(-y_score.to_numpy())[:k]
    ideal = np.argsort(-y_true.to_numpy())[:k]
    gains = y_true.to_numpy()[order]
    ideal_gains = y_true.to_numpy()[ideal]

    discounts = 1.0 / np.log2(np.arange(2, len(gains) + 2))
    dcg = float(np.sum(gains * discounts))
    idcg = float(np.sum(ideal_gains * discounts))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_regression(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float]:
    return {
        "mae": _mae(y_true, y_pred),
        "rmse": _rmse(y_true, y_pred),
        "median_ae": _median_ae(y_true, y_pred),
    }


def evaluate_ranking(y_true: pd.Series, y_score: pd.Series) -> dict[str, float]:
    return {
        "ndcg_at_25": _ndcg_at_k(y_true, y_score, k=25),
    }


def baseline_predictor(train_target: pd.Series, n_rows: int) -> pd.Series:
    # Mean-value baseline used as a stable benchmark for first-pass Issue #108 runs.
    mean_value = float(train_target.mean()) if len(train_target) else 0.0
    return pd.Series([mean_value] * n_rows)


def challenger_predictor(
    train_df: pd.DataFrame,
    score_df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
) -> pd.Series:
    if not feature_cols:
        return baseline_predictor(train_df[target_col], len(score_df))

    train_x = train_df[feature_cols].fillna(0.0).to_numpy(dtype=float)
    score_x = score_df[feature_cols].fillna(0.0).to_numpy(dtype=float)
    train_y = train_df[target_col].to_numpy(dtype=float)

    if len(train_x) == 0:
        return baseline_predictor(train_df[target_col], len(score_df))

    x_mean = train_x.mean(axis=0)
    y_mean = float(train_y.mean())
    centered_x = train_x - x_mean
    centered_y = train_y - y_mean
    denom = np.sum(centered_x**2, axis=0)
    num = np.sum(centered_x * centered_y[:, None], axis=0)
    weights = np.divide(num, denom, out=np.zeros_like(num), where=denom != 0)

    preds = y_mean + (score_x - x_mean) @ weights
    preds = np.clip(preds, a_min=1.0, a_max=None)
    return pd.Series(preds)


def _optional_model_predictor(
    model_name: str,
    train_df: pd.DataFrame,
    score_df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
) -> tuple[pd.Series | None, str]:
    train_x = train_df[feature_cols].fillna(0.0).to_numpy(dtype=float)
    score_x = score_df[feature_cols].fillna(0.0).to_numpy(dtype=float)
    train_y = train_df[target_col].to_numpy(dtype=float)

    if model_name == "lightgbm":
        if importlib.util.find_spec("lightgbm") is None:
            return None, "unavailable"
        try:
            import lightgbm as lgb  # type: ignore[import]

            model = lgb.LGBMRegressor(random_state=42, n_estimators=150, learning_rate=0.05)
            model.fit(train_x, train_y)
            preds = np.clip(model.predict(score_x), a_min=1.0, a_max=None)
            return pd.Series(preds), "available"
        except Exception as exc:  # pragma: no cover
            return None, f"error:{type(exc).__name__}"

    if model_name == "catboost":
        if importlib.util.find_spec("catboost") is None:
            return None, "unavailable"
        try:
            from catboost import CatBoostRegressor  # type: ignore[import]

            model = CatBoostRegressor(iterations=200, depth=6, learning_rate=0.05, loss_function="RMSE", verbose=False)
            model.fit(train_x, train_y)
            preds = np.clip(model.predict(score_x), a_min=1.0, a_max=None)
            return pd.Series(preds), "available"
        except Exception as exc:  # pragma: no cover
            return None, f"error:{type(exc).__name__}"

    return None, "unsupported"


def _slice_metrics(
    test_df: pd.DataFrame,
    y_true: pd.Series,
    y_pred: pd.Series,
    owner_id_col: str,
    focal_owner_id: int | None,
    position_col: str,
) -> dict[str, object]:
    aligned_df = test_df.reset_index(drop=True)
    aligned_true = y_true.reset_index(drop=True)
    aligned_pred = y_pred.reset_index(drop=True)

    metrics: dict[str, object] = {
        "focal_owner": None,
        "position": {},
    }

    if focal_owner_id is not None and owner_id_col in aligned_df.columns:
        owner_ids = pd.to_numeric(aligned_df[owner_id_col], errors="coerce")
        mask = owner_ids == int(focal_owner_id)
        if bool(mask.any()):
            metrics["focal_owner"] = {
                "owner_id": int(focal_owner_id),
                "row_count": int(mask.sum()),
                "regression_metrics": evaluate_regression(aligned_true[mask], aligned_pred[mask]),
            }

    if position_col in aligned_df.columns:
        position_metrics: dict[str, object] = {}
        for position in sorted(aligned_df[position_col].dropna().astype(str).unique().tolist()):
            mask = aligned_df[position_col].astype(str) == position
            if not bool(mask.any()):
                continue
            position_metrics[position] = {
                "row_count": int(mask.sum()),
                "regression_metrics": evaluate_regression(aligned_true[mask], aligned_pred[mask]),
            }
        metrics["position"] = position_metrics

    return metrics


def compute_drift_signals(
    champion_metrics: dict[str, float],
    challenger_metrics: dict[str, float],
) -> dict[str, float]:
    def pct_delta(metric: str) -> float:
        base = champion_metrics.get(metric, 0.0)
        nxt = challenger_metrics.get(metric, 0.0)
        if base == 0:
            if nxt == 0:
                return 0.0
            # When champion baseline is perfect and challenger regresses,
            # expose degradation instead of silently reporting no change.
            return float("inf") if nxt > 0 else float("-inf")
        return (nxt - base) / base

    return {
        "mae_pct_delta": pct_delta("mae"),
        "rmse_pct_delta": pct_delta("rmse"),
        "median_ae_pct_delta": pct_delta("median_ae"),
    }


def evaluate_candidates(
    df: pd.DataFrame,
    split: SplitPolicy,
    target_col: str,
    feature_cols: list[str],
    champion_model: str = "baseline_mean",
    candidate_models: list[str] | None = None,
    focal_owner_id: int | None = None,
    owner_id_col: str = "owner_id",
    position_col: str = "position",
    simulation_evaluator: SimulationEvaluator | None = None,
) -> dict[str, object]:
    train_df, val_df, test_df = time_split(df, split)
    if train_df.empty or val_df.empty or test_df.empty:
        raise ValueError(
            "Split produced empty partition(s). Ensure train/val/test seasons exist in the dataset."
        )

    y_train = train_df[target_col].astype(float)
    y_val = val_df[target_col].astype(float)
    y_test = test_df[target_col].astype(float)

    def _predict_for_model(model_name: str, score_df: pd.DataFrame) -> tuple[pd.Series | None, str]:
        if model_name == "baseline_mean":
            return baseline_predictor(y_train, len(score_df)), "available"
        if model_name == "linear_feature_weighted":
            return challenger_predictor(train_df, score_df, feature_cols, target_col), "available"
        return _optional_model_predictor(model_name, train_df, score_df, feature_cols, target_col)

    requested_candidates = [
        token.strip().lower()
        for token in (candidate_models or ["lightgbm", "catboost"])
        if token and token.strip()
    ]
    requested_models = []
    for name in [champion_model.strip().lower(), "linear_feature_weighted", *requested_candidates]:
        if name not in requested_models:
            requested_models.append(name)

    candidate_model_status: dict[str, str] = {}
    model_preds_val: dict[str, pd.Series] = {}
    model_preds_test: dict[str, pd.Series] = {}

    for model_name in requested_models:
        val_preds, val_status = _predict_for_model(model_name, val_df)
        candidate_model_status[model_name] = val_status
        if val_preds is None:
            continue

        test_preds, test_status = _predict_for_model(model_name, test_df)
        candidate_model_status[model_name] = test_status
        if test_preds is None:
            continue

        model_preds_val[model_name] = val_preds
        model_preds_test[model_name] = test_preds

    champion_name = champion_model.strip().lower()
    if champion_name not in model_preds_val:
        champion_name = "baseline_mean"
    if champion_name not in model_preds_val:
        raise ValueError("Unable to produce champion predictions for selected split and model set.")

    champion_val_preds = model_preds_val[champion_name]
    champion_preds = model_preds_test[champion_name]

    challenger_pool = [name for name in model_preds_val.keys() if name != champion_name]
    if not challenger_pool:
        raise ValueError("No challenger candidates available after dependency and split checks.")

    baseline_val_reg = evaluate_regression(y_val, champion_val_preds)
    baseline_val_rank = evaluate_ranking(y_val, champion_val_preds)
    challenger_gate_results: dict[str, dict[str, object]] = {}

    for name in challenger_pool:
        val_reg = evaluate_regression(y_val, model_preds_val[name])
        val_rank = evaluate_ranking(y_val, model_preds_val[name])

        error_gate = (
            val_reg["mae"] <= baseline_val_reg["mae"] * 1.10
            and val_reg["rmse"] <= baseline_val_reg["rmse"] * 1.10
            and val_reg["median_ae"] <= baseline_val_reg["median_ae"] * 1.10
        )
        ranking_gate = val_rank["ndcg_at_25"] >= baseline_val_rank["ndcg_at_25"] * 0.95

        slice_gate = True
        champion_slice = _slice_metrics(
            test_df=val_df,
            y_true=y_val,
            y_pred=champion_val_preds,
            owner_id_col=owner_id_col,
            focal_owner_id=focal_owner_id,
            position_col=position_col,
        )
        challenger_slice = _slice_metrics(
            test_df=val_df,
            y_true=y_val,
            y_pred=model_preds_val[name],
            owner_id_col=owner_id_col,
            focal_owner_id=focal_owner_id,
            position_col=position_col,
        )
        champ_owner = champion_slice.get("focal_owner")
        chall_owner = challenger_slice.get("focal_owner")
        if isinstance(champ_owner, dict) and isinstance(chall_owner, dict):
            champ_owner_mae = float(champ_owner["regression_metrics"]["mae"])
            chall_owner_mae = float(chall_owner["regression_metrics"]["mae"])
            if champ_owner_mae > 0 and chall_owner_mae > champ_owner_mae * 1.10:
                slice_gate = False

        simulation_gate = True
        sim_result: dict[str, object] | None = None
        if simulation_evaluator is not None:
            sim_result = simulation_evaluator(test_df, champion_preds, model_preds_test[name], focal_owner_id)
            sim_delta = sim_result.get("delta") if isinstance(sim_result, dict) else None
            if isinstance(sim_delta, dict):
                points_delta = float(sim_delta.get("expected_total_points", 0.0))
                value_delta = float(sim_delta.get("expected_value_captured", 0.0))
                simulation_gate = points_delta >= 0.0 and value_delta >= 0.0

        all_gates = error_gate and ranking_gate and slice_gate and simulation_gate
        challenger_gate_results[name] = {
            "all_gates_pass": all_gates,
            "error_gate_pass": error_gate,
            "ranking_gate_pass": ranking_gate,
            "slice_gate_pass": slice_gate,
            "simulation_gate_pass": simulation_gate,
            "val_regression_metrics": val_reg,
            "val_ranking_metrics": val_rank,
            "simulation_preview": sim_result,
        }

    eligible = [name for name in challenger_pool if challenger_gate_results[name]["all_gates_pass"]]
    ranking_floor = baseline_val_rank["ndcg_at_25"] * 0.95
    if eligible:
        selected_challenger = min(
            eligible,
            key=lambda name: (
                evaluate_regression(y_val, model_preds_val[name])["mae"],
                -evaluate_ranking(y_val, model_preds_val[name])["ndcg_at_25"],
            ),
        )
    else:
        # Fall back to the least-worst challenger, still preserving gate outcomes in report.
        selected_challenger = min(
            challenger_pool,
            key=lambda name: (
                evaluate_regression(y_val, model_preds_val[name])["mae"],
                0.0 if evaluate_ranking(y_val, model_preds_val[name])["ndcg_at_25"] >= ranking_floor else 1.0,
            ),
        )

    challenger_preds = model_preds_test[selected_challenger]

    champion_reg = evaluate_regression(y_test, champion_preds)
    challenger_reg = evaluate_regression(y_test, challenger_preds)

    champion_rank = evaluate_ranking(y_test, champion_preds)
    challenger_rank = evaluate_ranking(y_test, challenger_preds)

    slice_metrics = {
        "champion": _slice_metrics(
            test_df=test_df,
            y_true=y_test,
            y_pred=champion_preds,
            owner_id_col=owner_id_col,
            focal_owner_id=focal_owner_id,
            position_col=position_col,
        ),
        "challenger": _slice_metrics(
            test_df=test_df,
            y_true=y_test,
            y_pred=challenger_preds,
            owner_id_col=owner_id_col,
            focal_owner_id=focal_owner_id,
            position_col=position_col,
        ),
    }

    simulation_impact: dict[str, object] | None = None
    if simulation_evaluator is not None:
        simulation_impact = simulation_evaluator(test_df, champion_preds, challenger_preds, focal_owner_id)

    return {
        "split": {
            "train_end_season": split.train_end_season,
            "val_season": split.val_season,
            "test_season": split.test_season,
            "train_rows": int(len(train_df)),
            "val_rows": int(len(val_df)),
            "test_rows": int(len(test_df)),
        },
        "target_col": target_col,
        "feature_cols": feature_cols,
        "focal_owner_id": focal_owner_id,
        "champion_model": champion_name,
        "selected_challenger": selected_challenger,
        "candidate_model_status": candidate_model_status,
        "challenger_gate_results": challenger_gate_results,
        "selected_challenger_gates": challenger_gate_results.get(selected_challenger, {}),
        "champion": {
            "name": champion_name,
            "regression_metrics": champion_reg,
            "ranking_metrics": champion_rank,
        },
        "challenger": {
            "name": selected_challenger,
            "regression_metrics": challenger_reg,
            "ranking_metrics": challenger_rank,
        },
        "drift_signals": compute_drift_signals(champion_reg, challenger_reg),
        "slice_metrics": slice_metrics,
        "simulation_impact": simulation_impact,
    }


def write_report(report: dict[str, object], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "model_eval_report.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    return output_path
