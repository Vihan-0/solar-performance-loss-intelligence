"""
Energy-Loss Intelligence & Shortfall Quantification Module
Project: Adaptive Solar Performance & Loss Intelligence

This module quantifies potential energy shortfall (kWh) attributable to
candidate underperformance events, enforcing:
1. Non-negative interval shortfall: max(0, expected - actual) * dt_hours.
2. Nighttime exclusion: zero shortfall when irradiance <= 0.
3. Data gap guards: no shortfall fabrication across missing telemetry intervals.
4. Distinguishing raw deviation shortfall from persistent, actionable candidate shortfall.
5. Inverter loss prioritization ranking.
"""

from typing import Dict, Optional
import numpy as np
import pandas as pd


def compute_interval_shortfall(
    actual: pd.Series,
    expected: pd.Series,
    is_daylight: Optional[pd.Series] = None,
    interval_hours: float = 0.25,
) -> pd.Series:
    """
    Computes positive energy shortfall (kWh) for individual telemetry intervals.

    Shortfall_t = max(0, Expected_t - Actual_t) * dt_hours

    Parameters
    ----------
    actual : pd.Series
        Actual observed AC power (kW).
    expected : pd.Series
        Expected baseline AC power (kW).
    is_daylight : pd.Series, optional
        Boolean series indicating whether the interval occurred during daylight.
        If provided, nighttime intervals have their shortfall strictly forced to 0.0.
    interval_hours : float, default=0.25
        Interval duration in hours (0.25 for 15-minute telemetry).

    Returns
    -------
    pd.Series
        Energy shortfall in kWh.
    """
    residual_kw = expected - actual
    shortfall = np.maximum(0.0, residual_kw) * interval_hours

    # Mask missing values
    invalid_mask = actual.isna() | expected.isna()
    shortfall[invalid_mask] = np.nan

    # Zero-out nighttime intervals
    if is_daylight is not None:
        shortfall[~is_daylight] = 0.0

    return shortfall


def aggregate_inverter_loss_summary(
    df: pd.DataFrame,
    expected_col: str,
    actual_col: str = "AC_POWER_KW",
    persistent_flag_col: str = "is_persistent_anomaly",
    interval_hours: float = 0.25,
) -> pd.DataFrame:
    """
    Aggregates accumulated generation and potential energy shortfalls by inverter.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset containing 'PLANT_ID', 'SOURCE_KEY', expected_col, actual_col, persistent_flag_col.
    expected_col : str
        Column name for expected baseline power in kW.
    actual_col : str, default='AC_POWER_KW'
        Column name for actual power generation in kW.
    persistent_flag_col : str, default='is_persistent_anomaly'
        Column name for persistent anomaly flag.
    interval_hours : float, default=0.25

    Returns
    -------
    pd.DataFrame
        Inverter loss summary and investigation priority ranking.
    """
    col = actual_col if actual_col in df.columns else "AC_POWER"
    scale = 0.001 if col == "AC_POWER" else 1.0

    records = []
    grouped = df.groupby(["PLANT_ID", "SOURCE_KEY"], observed=True)

    for (plant_id, source_key), grp in grouped:
        actual_kwh = float(((grp[col] * scale) * interval_hours).sum())
        expected_kwh = float((grp[expected_col] * interval_hours).sum())

        # Total potential shortfall (all positive residuals)
        pos_residual = np.maximum(0.0, grp[expected_col] - (grp[col] * scale))
        total_shortfall_kwh = float((pos_residual * interval_hours).sum())

        # Actionable persistent shortfall
        is_pers = grp[persistent_flag_col].fillna(False).astype(bool)
        persistent_intervals = int(is_pers.sum())
        persistent_hours = persistent_intervals * interval_hours
        persistent_shortfall_kwh = float((pos_residual[is_pers] * interval_hours).sum())

        loss_pct = (persistent_shortfall_kwh / expected_kwh * 100.0) if expected_kwh > 0 else 0.0

        records.append(
            {
                "PLANT_ID": str(plant_id),
                "SOURCE_KEY": str(source_key),
                "actual_generation_kwh": round(actual_kwh, 2),
                "expected_generation_kwh": round(expected_kwh, 2),
                "total_potential_shortfall_kwh": round(total_shortfall_kwh, 2),
                "persistent_shortfall_kwh": round(persistent_shortfall_kwh, 2),
                "persistent_anomaly_intervals": persistent_intervals,
                "persistent_anomaly_hours": round(persistent_hours, 2),
                "loss_percentage": round(loss_pct, 2),
                "total_intervals": len(grp),
            }
        )

    summary_df = pd.DataFrame(records)
    summary_df = summary_df.sort_values("persistent_shortfall_kwh", ascending=False).reset_index(drop=True)
    summary_df["urgency_rank"] = summary_df.index + 1

    return summary_df


def aggregate_plant_loss_summary(
    df: pd.DataFrame,
    expected_col: str,
    actual_col: str = "AC_POWER_KW",
    persistent_flag_col: str = "is_persistent_anomaly",
    interval_hours: float = 0.25,
) -> pd.DataFrame:
    """
    Aggregates loss metrics by solar plant.
    """
    col = actual_col if actual_col in df.columns else "AC_POWER"
    scale = 0.001 if col == "AC_POWER" else 1.0

    records = []
    for plant_id, grp in df.groupby("PLANT_ID", observed=True):
        actual_kwh = float(((grp[col] * scale) * interval_hours).sum())
        expected_kwh = float((grp[expected_col] * interval_hours).sum())

        pos_residual = np.maximum(0.0, grp[expected_col] - (grp[col] * scale))
        total_shortfall_kwh = float((pos_residual * interval_hours).sum())

        is_pers = grp[persistent_flag_col].fillna(False).astype(bool)
        persistent_shortfall_kwh = float((pos_residual[is_pers] * interval_hours).sum())
        persistent_intervals = int(is_pers.sum())

        loss_pct = (persistent_shortfall_kwh / expected_kwh * 100.0) if expected_kwh > 0 else 0.0

        records.append(
            {
                "PLANT_ID": str(plant_id),
                "actual_generation_kwh": round(actual_kwh, 2),
                "expected_generation_kwh": round(expected_kwh, 2),
                "total_potential_shortfall_kwh": round(total_shortfall_kwh, 2),
                "persistent_shortfall_kwh": round(persistent_shortfall_kwh, 2),
                "persistent_anomaly_intervals": persistent_intervals,
                "persistent_anomaly_hours": round(persistent_intervals * interval_hours, 2),
                "loss_percentage": round(loss_pct, 2),
            }
        )

    return pd.DataFrame(records)
