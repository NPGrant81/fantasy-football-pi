from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SplitPolicy:
    train_end_season: int
    val_season: int
    test_season: int


def time_split(df: pd.DataFrame, split: SplitPolicy) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if "season_year" not in df.columns:
        raise ValueError("Expected column 'season_year' for time-based split.")

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


def compute_drift_signals(
    champion_metrics: dict[str, float],
    challenger_metrics: dict[str, float],
) -> dict[str, float]:
    def pct_delta(metric: str) -> float:
        base = champion_metrics.get(metric, 0.0)
        nxt = challenger_metrics.get(metric, 0.0)
        if base == 0:
            return 0.0
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
) -> dict[str, object]:
    train_df, val_df, test_df = time_split(df, split)
    if train_df.empty or val_df.empty or test_df.empty:
        raise ValueError(
            "Split produced empty partition(s). Ensure train/val/test seasons exist in the dataset."
        )

    y_train = train_df[target_col].astype(float)
    y_test = test_df[target_col].astype(float)

    baseline_preds = baseline_predictor(y_train, len(test_df))
    challenger_preds = challenger_predictor(train_df, test_df, feature_cols, target_col)

    champion_reg = evaluate_regression(y_test, baseline_preds)
    challenger_reg = evaluate_regression(y_test, challenger_preds)

    champion_rank = evaluate_ranking(y_test, baseline_preds)
    challenger_rank = evaluate_ranking(y_test, challenger_preds)

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
        "champion": {
            "name": "baseline_mean",
            "regression_metrics": champion_reg,
            "ranking_metrics": champion_rank,
        },
        "challenger": {
            "name": "linear_feature_weighted",
            "regression_metrics": challenger_reg,
            "ranking_metrics": challenger_rank,
        },
        "drift_signals": compute_drift_signals(champion_reg, challenger_reg),
    }


def write_report(report: dict[str, object], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "model_eval_report.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    return output_path
