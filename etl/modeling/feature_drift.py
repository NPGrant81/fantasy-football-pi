"""
feature_drift.py — Feature distribution drift detection for Fantasy Football PI.

Implements Population Stability Index (PSI) and basic summary-level drift checks
for all features defined in etl/feature_registry.yml.

Usage:
    from etl.modeling.feature_drift import check_feature_drift, DriftReport

    report = check_feature_drift(
        reference_df=features_2024,
        current_df=features_2025,
        registry_path="etl/feature_registry.yml",
    )
    if report.has_critical_drift:
        raise RuntimeError(report.summary())

Intended use points:
    1. Post-ETL validation — run after building feature artifacts each season.
    2. Pre-promotion gate — run before promoting a challenger model (see
       docs/model-versioning.md §4).
    3. CI data-quality job — run on the latest ETL outputs.

PSI interpretation (standard thresholds):
    PSI < 0.10  — no significant drift; distribution is stable
    PSI 0.10–0.25 — moderate drift; investigate before promoting
    PSI > 0.25  — significant drift; block model promotion; investigate ETL
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

try:
    import yaml  # type: ignore
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

logger = logging.getLogger(__name__)

# PSI threshold constants (industry-standard)
PSI_STABLE = 0.10
PSI_MODERATE = 0.25
PSI_BINS = 10
_EPSILON = 1e-6  # prevent log(0)


@dataclass
class FeatureDriftResult:
    """Drift assessment for a single feature."""
    name: str
    tier: str  # critical | standard | optional
    online: bool
    psi: Optional[float]  # None if feature is missing from one or both datasets
    status: str  # "stable" | "moderate" | "high" | "missing" | "skipped"
    ref_null_rate: float
    cur_null_rate: float
    null_rate_delta: float  # current - reference
    ref_count: int
    cur_count: int

    @property
    def is_alert(self) -> bool:
        """True if this feature warrants a warning or block."""
        return self.status in {"moderate", "high", "missing"}

    @property
    def is_block(self) -> bool:
        """True if this feature should block model promotion."""
        if self.tier == "critical" and self.status in {"high", "missing"}:
            return True
        if self.tier == "standard" and self.status == "high":
            return True
        return False


@dataclass
class DriftReport:
    """Aggregated drift results across all features."""
    results: list[FeatureDriftResult] = field(default_factory=list)
    reference_season: Optional[int] = None
    current_season: Optional[int] = None

    @property
    def has_critical_drift(self) -> bool:
        """True if any feature should block model promotion."""
        return any(r.is_block for r in self.results)

    @property
    def has_any_drift(self) -> bool:
        """True if any feature shows moderate or high drift."""
        return any(r.is_alert for r in self.results)

    def summary(self) -> str:
        """Return a plain-text summary suitable for logging or CI output."""
        lines = ["=== Feature Drift Report ==="]
        if self.reference_season and self.current_season:
            lines.append(f"Reference season: {self.reference_season}  →  Current season: {self.current_season}")
        lines.append("")

        blocked = [r for r in self.results if r.is_block]
        moderate = [r for r in self.results if r.status == "moderate" and not r.is_block]
        stable = [r for r in self.results if r.status == "stable"]
        missing = [r for r in self.results if r.status == "missing"]

        if blocked:
            lines.append(f"BLOCKED ({len(blocked)} features — model promotion blocked):")
            for r in blocked:
                lines.append(f"  {r.name:40s}  PSI={_fmt(r.psi)}  tier={r.tier}  null_delta={r.null_rate_delta:+.3f}")

        if missing:
            lines.append(f"MISSING ({len(missing)} features — not found in one dataset):")
            for r in missing:
                lines.append(f"  {r.name:40s}  tier={r.tier}")

        if moderate:
            lines.append(f"MODERATE drift ({len(moderate)} features — investigate):")
            for r in moderate:
                lines.append(f"  {r.name:40s}  PSI={_fmt(r.psi)}  tier={r.tier}")

        lines.append(f"STABLE: {len(stable)} features")
        lines.append("")
        lines.append(f"Overall: {'BLOCK' if self.has_critical_drift else 'WARN' if self.has_any_drift else 'OK'}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialisable representation for CI artefacts."""
        return {
            "reference_season": self.reference_season,
            "current_season": self.current_season,
            "has_critical_drift": self.has_critical_drift,
            "has_any_drift": self.has_any_drift,
            "features": [
                {
                    "name": r.name,
                    "tier": r.tier,
                    "online": r.online,
                    "psi": _json_number(r.psi),
                    "status": r.status,
                    "ref_null_rate": _json_number(r.ref_null_rate),
                    "cur_null_rate": _json_number(r.cur_null_rate),
                    "null_rate_delta": _json_number(r.null_rate_delta),
                }
                for r in self.results
            ],
        }


def _fmt(v: Optional[float]) -> str:
    return f"{v:.4f}" if v is not None else "n/a"


def _json_number(v: Optional[float]) -> Optional[float]:
    """Convert non-finite floats to None for strict JSON compatibility."""
    if v is None:
        return None
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return float(v)


def _compute_psi(ref_series: pd.Series, cur_series: pd.Series, bins: int = PSI_BINS) -> float:
    """
    Compute Population Stability Index between two numeric series.

    Bins are determined from the reference distribution. Both series are
    clipped to the reference range to avoid empty bins for out-of-range values.
    """
    ref_vals = ref_series.dropna().to_numpy(dtype=float)
    cur_vals = cur_series.dropna().to_numpy(dtype=float)

    if len(ref_vals) < 2 or len(cur_vals) < 2:
        return float("nan")

    # Determine bin edges from reference distribution
    min_val = float(np.min(ref_vals))
    max_val = float(np.max(ref_vals))

    if math.isclose(min_val, max_val, rel_tol=1e-9):
        # Zero-variance feature — PSI is 0 if cur matches, else very high
        cur_unique = float(np.unique(cur_vals[~np.isnan(cur_vals)]).size)
        return 0.0 if cur_unique <= 1 else PSI_MODERATE

    ref_vals = np.clip(ref_vals, min_val, max_val)
    cur_vals = np.clip(cur_vals, min_val, max_val)

    bin_edges = np.linspace(min_val, max_val, bins + 1)
    bin_edges[0] -= _EPSILON
    bin_edges[-1] += _EPSILON

    ref_counts, _ = np.histogram(ref_vals, bins=bin_edges)
    cur_counts, _ = np.histogram(cur_vals, bins=bin_edges)

    ref_pct = (ref_counts + _EPSILON) / float(len(ref_vals))
    cur_pct = (cur_counts + _EPSILON) / float(len(cur_vals))

    psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    return psi


def _psi_status(psi: Optional[float]) -> str:
    if psi is None or math.isnan(psi):
        return "skipped"
    if psi < PSI_STABLE:
        return "stable"
    if psi < PSI_MODERATE:
        return "moderate"
    return "high"


def _load_registry(registry_path: Path) -> list[dict]:
    """Load feature entries from the YAML registry. Returns [] if yaml unavailable."""
    if not _YAML_AVAILABLE:
        logger.warning("PyYAML not available; loading registry skipped. Install pyyaml.")
        return []
    with open(registry_path) as f:
        data = yaml.safe_load(f)
    return data.get("features", []) if data else []


def check_feature_drift(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    *,
    registry_path: Optional[Path] = None,
    feature_names: Optional[list[str]] = None,
    reference_season: Optional[int] = None,
    current_season: Optional[int] = None,
) -> DriftReport:
    """
    Compute PSI and null-rate drift for every numeric feature in the registry
    (or the explicit ``feature_names`` list).

    Parameters
    ----------
    reference_df:
        Baseline feature DataFrame (e.g., prior season ETL output).
    current_df:
        Current feature DataFrame to compare against the baseline.
    registry_path:
        Path to ``etl/feature_registry.yml``. If None and ``feature_names`` is also
        None, all shared numeric columns are checked.
    feature_names:
        Explicit list of feature names to check. Overrides registry if provided.
    reference_season, current_season:
        Optional season labels used in the report summary only.

    Returns
    -------
    DriftReport
        Aggregated drift results. Check ``report.has_critical_drift`` before
        promoting a model.
    """
    report = DriftReport(reference_season=reference_season, current_season=current_season)

    # Determine feature list
    registry_entries: dict[str, dict] = {}
    loaded_registry_entries: list[dict] = []

    if registry_path is not None and Path(registry_path).exists():
        loaded_registry_entries = _load_registry(Path(registry_path))

    if feature_names is not None:
        wanted = {name for name in feature_names}
        for entry in loaded_registry_entries:
            entry_name = entry.get("name")
            if entry_name in wanted:
                registry_entries[entry_name] = entry
        for name in feature_names:
            registry_entries.setdefault(name, {"name": name, "tier": "standard", "online": True})
    elif registry_path is not None and Path(registry_path).exists():
        if not loaded_registry_entries:
            raise ValueError(
                f"No feature entries loaded from registry: {registry_path}. "
                "Refusing to produce an empty drift report."
            )
        for entry in loaded_registry_entries:
            registry_entries[entry["name"]] = entry
    else:
        # Fall back: all shared numeric columns
        shared = set(reference_df.select_dtypes(include="number").columns) & \
                 set(current_df.select_dtypes(include="number").columns)
        for name in sorted(shared):
            registry_entries[name] = {"name": name, "tier": "standard", "online": True}

    for name, entry in registry_entries.items():
        tier = entry.get("tier", "standard")
        online = bool(entry.get("online", True))

        ref_in_df = name in reference_df.columns
        cur_in_df = name in current_df.columns

        if not ref_in_df or not cur_in_df:
            report.results.append(FeatureDriftResult(
                name=name,
                tier=tier,
                online=online,
                psi=None,
                status="missing",
                ref_null_rate=float("nan") if not ref_in_df else float(reference_df[name].isna().mean()),
                cur_null_rate=float("nan") if not cur_in_df else float(current_df[name].isna().mean()),
                null_rate_delta=float("nan"),
                ref_count=len(reference_df) if ref_in_df else 0,
                cur_count=len(current_df) if cur_in_df else 0,
            ))
            continue

        ref_col = reference_df[name]
        cur_col = current_df[name]

        ref_null_rate = float(ref_col.isna().mean())
        cur_null_rate = float(cur_col.isna().mean())
        null_rate_delta = cur_null_rate - ref_null_rate

        # Skip non-numeric columns (dict/list features stored as objects)
        if not pd.api.types.is_numeric_dtype(ref_col) or not pd.api.types.is_numeric_dtype(cur_col):
            report.results.append(FeatureDriftResult(
                name=name,
                tier=tier,
                online=online,
                psi=None,
                status="skipped",
                ref_null_rate=ref_null_rate,
                cur_null_rate=cur_null_rate,
                null_rate_delta=null_rate_delta,
                ref_count=len(reference_df),
                cur_count=len(current_df),
            ))
            continue

        psi = _compute_psi(ref_col, cur_col)
        status = _psi_status(psi)

        # Respect per-feature null thresholds from registry when available.
        configured_null_threshold = entry.get("null_rate_threshold")
        try:
            null_threshold = float(configured_null_threshold)
        except (TypeError, ValueError):
            null_threshold = 0.20 if tier == "critical" else 0.30

        if cur_null_rate >= null_threshold:
            if tier == "critical":
                status = "high"
            elif status == "stable":
                status = "moderate"
        elif null_rate_delta >= (0.20 if tier == "critical" else 0.30) and status == "stable":
            status = "moderate"

        report.results.append(FeatureDriftResult(
            name=name,
            tier=tier,
            online=online,
            psi=psi,
            status=status,
            ref_null_rate=ref_null_rate,
            cur_null_rate=cur_null_rate,
            null_rate_delta=null_rate_delta,
            ref_count=len(reference_df),
            cur_count=len(current_df),
        ))
        logger.debug("feature=%s  psi=%.4f  status=%s  null_delta=%+.3f", name, psi or 0, status, null_rate_delta)

    return report
