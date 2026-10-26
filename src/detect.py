"""
Residual-Based Anomaly Detection Module
Project: Adaptive Solar Performance & Loss Intelligence

This module implements:
1. Inverter-Specific Model Baseline (ML model expected power).
2. Capacity-Normalized Peer/Cohort Baseline (cross-inverter cohort benchmark).
3. Residual and relative deviation calculations with low-light guards.
4. Validation-set threshold calibration across plant and irradiance regimes.
5. Strict temporal persistence filtering (>= 3 consecutive 15-min intervals,
   zero gap bridging, no synthetic missing data imputation).
"""

from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

IRRADIANCE_BINS = [0.0, 0.2, 0.6, float("inf")]
IRRADIANCE_LABELS = ["Low", "Medium", "High"]


def estimate_inverter_capacities(
    train_df: pd.DataFrame,
    power_col: str = "AC_POWER_KW",
    quantile: float = 0.995,
) -> Dict[Tuple[int, str], float]:
    """
    Estimates effective inverter peak generation capacity from historical training data.

    Parameters
    ----------
    train_df : pd.DataFrame
        Training partition containing 'PLANT_ID', 'SOURCE_KEY', power_col.
    power_col : str, default='AC_POWER_KW'
        Power generation column in kW.
    quantile : float, default=0.995
        Quantile to estimate peak capacity without being skewed by single-interval spikes.

    Returns
    -------
    Dict[Tuple[int, str], float]
        Mapping of (plant_id, source_key) -> capacity in kW.
    """
    col = power_col if power_col in train_df.columns else "AC_POWER"
    scale_factor = 0.001 if col == "AC_POWER" else 1.0

    capacities = {}
    for (plant_id, source_key), grp in train_df.groupby(["PLANT_ID", "SOURCE_KEY"], observed=True):
        cap = float(grp[col].quantile(quantile)) * scale_factor
        # Ensure a reasonable physical minimum (0.050 kW = 50 W)
        capacities[(int(plant_id), str(source_key))] = max(cap, 0.050)
    return capacities


def compute_cohort_expected_power(
    df: pd.DataFrame,
    capacities: Dict[Tuple[int, str], float],
    power_col: str = "AC_POWER_KW",
) -> pd.Series:
    """
    Calculates capacity-normalized peer cohort baseline expected power in kW.

    Algorithm:
    1. Normalizes each inverter's output by its training-derived capacity:
       norm_power = AC_POWER_KW / Capacity
    2. Calculates cohort median normalized power for each (PLANT_ID, TIMESTAMP).
    3. Re-scales cohort normalized power to inverter's capacity:
       Expected_Cohort = Cohort_Median_Norm * Inverter_Capacity

    Parameters
    ----------
    df : pd.DataFrame
        Dataset containing 'TIMESTAMP', 'PLANT_ID', 'SOURCE_KEY', power_col.
    capacities : Dict[Tuple[int, str], float]
        Inverter capacities in kW.
    power_col : str, default='AC_POWER_KW'

    Returns
    -------
    pd.Series
        Cohort expected power in kW.
    """
    col = power_col if power_col in df.columns else ("AC_POWER_KW" if "AC_POWER_KW" in df.columns else "AC_POWER")

    out_df = df[["TIMESTAMP", "PLANT_ID", "SOURCE_KEY"]].copy()
    out_df["power"] = df[col].astype(float)

    # Map capacity
    lookup_keys = list(zip(out_df["PLANT_ID"].astype(int), out_df["SOURCE_KEY"].astype(str)))
    caps = [capacities.get(k, 1.30) for k in lookup_keys]
    out_df["capacity"] = caps

    # Normalized generation
    out_df["norm_power"] = out_df["power"] / out_df["capacity"]

    # Cohort median per plant and timestamp
    cohort_norm = out_df.groupby(["PLANT_ID", "TIMESTAMP"], observed=True)["norm_power"].transform("median")

    # Re-scale to inverter capacity
    cohort_expected = cohort_norm * out_df["capacity"]
    return np.maximum(0.0, cohort_expected)


def compute_model_expected_power(
    pipeline: Pipeline,
    df: pd.DataFrame,
    features: List[str],
) -> pd.Series:
    """
    Computes inverter-specific expected power (kW) using the trained regression pipeline.
    """
    preds = pipeline.predict(df[features])
    return pd.Series(np.maximum(0.0, preds), index=df.index, name="model_expected_power")


def calculate_residuals(
    actual: pd.Series,
    expected: pd.Series,
    min_expected_power: float = 0.050,
) -> Tuple[pd.Series, pd.Series]:
    """
    Calculates positive underperformance residual (kW) and guarded relative deviation.

    Parameters
    ----------
    actual : pd.Series
        Actual observed AC power (kW).
    expected : pd.Series
        Expected baseline AC power (kW).
    min_expected_power : float, default=0.050 kW (50 Watts)
        Minimum expected power threshold below which relative deviation is set to NaN
        to prevent division by near-zero during dawn/dusk transitions.

    Returns
    -------
    Tuple[pd.Series, pd.Series]
        (residual_kw, relative_residual)
        positive residual indicates underperformance (expected > actual).
    """
    residual = expected - actual

    # Guarded relative residual: (expected - actual) / expected
    valid_expected = expected >= min_expected_power
    relative = pd.Series(np.nan, index=actual.index, dtype=float)
    relative.loc[valid_expected] = residual.loc[valid_expected] / expected.loc[valid_expected]

    return residual, relative


def calibrate_thresholds(
    val_df: pd.DataFrame,
    residual_col: str = "residual_model",
    quantile: float = 0.95,
    min_threshold_kw: float = 0.030,
    exclude_calibration_dropouts: bool = True,
) -> Dict[Tuple[int, str], float]:
    """
    Calibrates regime-specific residual thresholds on the validation dataset.

    Parameters
    ----------
    val_df : pd.DataFrame
        Validation partition containing 'PLANT_ID', 'IRRADIATION', and residual_col.
    residual_col : str
        Column name of the residual to calibrate against (in kW).
    quantile : float, default=0.95
        Upper quantile of residuals used to establish candidate anomaly boundary.
    min_threshold_kw : float, default=0.030 kW (30 Watts)
        Minimum allowable threshold to prevent over-flagging in low-irradiance conditions.
    exclude_calibration_dropouts : bool, default=True
        Whether to exclude complete zero-generation dropouts (P <= 50W during high irradiance)
        from the normal baseline quantile calculation, preventing widespread chronic outages
        from contaminating the sensitivity of the baseline threshold.

    Returns
    -------
    Dict[Tuple[int, str], float]
        Mapping of (plant_id, irradiance_regime) -> threshold in kW.
    """
    vdf = val_df.copy()
    if "irr_bin" not in vdf.columns:
        vdf["irr_bin"] = pd.cut(vdf["IRRADIATION"], bins=IRRADIANCE_BINS, labels=IRRADIANCE_LABELS)

    if exclude_calibration_dropouts and "AC_POWER_KW" in vdf.columns:
        # Filter out severe daylight dropouts (P <= 50W when IRRADIATION > 0.5) from normal threshold calibration
        normal_mask = ~((vdf["IRRADIATION"] > 0.5) & (vdf["AC_POWER_KW"] <= 0.050))
        vdf = vdf[normal_mask].copy()

    thresholds = {}
    for (plant_id, regime), grp in vdf.groupby(["PLANT_ID", "irr_bin"], observed=True):
        if len(grp) > 0:
            q_val = float(grp[residual_col].quantile(quantile))
            thresholds[(int(plant_id), str(regime))] = max(q_val, min_threshold_kw)
        else:
            thresholds[(int(plant_id), str(regime))] = min_threshold_kw

    return thresholds


def apply_persistence_filter(
    df: pd.DataFrame,
    candidate_mask_col: str,
    min_consecutive: int = 3,
    max_interval_minutes: float = 15.0,
) -> pd.Series:
    """
    Applies strict temporal persistence filtering to candidate anomalies.

    Rules Enforced:
    1. Evaluated strictly per inverter (grouped by PLANT_ID and SOURCE_KEY).
    2. Consecutive timestamps must satisfy delta_t == max_interval_minutes.
       If delta_t > max_interval_minutes (e.g. data gap), the streak is reset.
    3. Requires at least min_consecutive consecutive intervals (e.g. 3 * 15m = 45m).
    4. When a streak reaches min_consecutive, all intervals in that continuous
       underperformance episode are flagged.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset containing 'TIMESTAMP', 'PLANT_ID', 'SOURCE_KEY', and candidate_mask_col.
    candidate_mask_col : str
        Boolean column indicating whether the interval exceeded the residual threshold.
    min_consecutive : int, default=3
        Minimum consecutive intervals to qualify as persistent candidate anomaly.
    max_interval_minutes : float, default=15.0
        Maximum time delta to be considered consecutive.

    Returns
    -------
    pd.Series
        Boolean Series of persistent candidate anomalies.
    """
    persistent_flags = pd.Series(False, index=df.index)

    # Process each inverter independently
    for _, group_indices in df.groupby(["PLANT_ID", "SOURCE_KEY"], observed=True).groups.items():
        sub = df.loc[group_indices].sort_values("TIMESTAMP")
        timestamps = sub["TIMESTAMP"].values
        candidates = sub[candidate_mask_col].values
        n = len(sub)

        streak_count = 0
        streak_indices = []

        for i in range(n):
            is_cand = candidates[i]

            if i > 0:
                dt_minutes = (timestamps[i] - timestamps[i - 1]) / np.timedelta64(1, "m")
            else:
                dt_minutes = max_interval_minutes

            # If gap exceeded 15 mins, any previous streak was interrupted
            if dt_minutes > max_interval_minutes + 1e-3:
                streak_count = 0
                streak_indices = []

            if is_cand:
                streak_count += 1
                streak_indices.append(sub.index[i])
                if streak_count >= min_consecutive:
                    # Flag all intervals in this ongoing episode
                    persistent_flags.loc[streak_indices] = True
            else:
                streak_count = 0
                streak_indices = []

        # Return series with original index
    return persistent_flags
