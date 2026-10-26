"""
Feature Engineering Module
Project: Adaptive Solar Performance & Loss Intelligence

This module generates leak-free, physically justified features for predicting
expected solar AC power from ambient weather and operational metadata.

Rules Enforced:
1. No contemporaneous DC_POWER, DAILY_YIELD, or TOTAL_YIELD in feature set X.
2. Target is strictly AC_POWER.
3. Exclude records lacking weather measurements from model-ready partitions.
4. Cyclical encoding for diurnal (hour, time-of-day) and seasonal (day-of-year) cycles.
5. All operations are strictly deterministic and reproducible.
"""

from typing import List, Tuple
import numpy as np
import pandas as pd

# Columns that MUST NEVER appear in feature matrix X due to target leakage
FORBIDDEN_LEAKAGE_COLUMNS = [
    "AC_POWER",     # Raw target in Watts
    "AC_POWER_KW",  # Canonical target in kW
    "DC_POWER",     # Direct upstream power conversion (masks DC-side underperformance)
    "DAILY_YIELD",  # Same-day cumulative generation integral
    "TOTAL_YIELD",  # Non-stationary lifetime counter
]

# Baseline engineered feature definitions (onsite sensors + timing + entity)
BASELINE_FEATURE_COLUMNS = [
    # Meteorological inputs (onsite sensors)
    "IRRADIATION",
    "AMBIENT_TEMPERATURE",
    "MODULE_TEMPERATURE",
    "TEMP_DIFF",  # Thermal stress / panel heating proxy (MODULE_TEMP - AMBIENT_TEMP)
    # Cyclical Diurnal Timing
    "sin_time_of_day",
    "cos_time_of_day",
    # Cyclical Annual Timing
    "sin_day_of_year",
    "cos_day_of_year",
    # Entity metadata
    "PLANT_ID",
    "SOURCE_KEY",
]

# External historical weather candidate features (Open-Meteo reanalysis)
WEATHER_ENRICHED_CANDIDATE_COLUMNS = [
    "ext_temp_c",
    "ext_rh_pct",
    "ext_precip_mm",
    "ext_cloud_cover_pct",
    "ext_wind_speed_kmh",
    "ext_radiation_kw_m2",
]

APPROVED_FEATURE_COLUMNS = BASELINE_FEATURE_COLUMNS
TARGET_COLUMN = "AC_POWER_KW"


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Constructs deterministic, leak-free features from standardized solar records.

    Parameters
    ----------
    df : pd.DataFrame
        Merged generation and weather dataframe containing 'TIMESTAMP',
        'IRRADIATION', 'AMBIENT_TEMPERATURE', 'MODULE_TEMPERATURE'.

    Returns
    -------
    pd.DataFrame
        Dataframe augmented with engineered feature columns.
    """
    out = df.copy()

    # Verify required base columns exist
    required_base = ["TIMESTAMP", "IRRADIATION", "AMBIENT_TEMPERATURE", "MODULE_TEMPERATURE"]
    missing = [c for c in required_base if c not in out.columns]
    if missing:
        raise ValueError(f"Cannot engineer features; missing columns: {missing}")

    # Thermal differential (solar heating of cell above ambient air)
    out["TEMP_DIFF"] = out["MODULE_TEMPERATURE"] - out["AMBIENT_TEMPERATURE"]

    # Diurnal cyclic features (continuous time-of-day in fractional hours: 0.0 to 23.75)
    time_of_day = out["TIMESTAMP"].dt.hour + (out["TIMESTAMP"].dt.minute / 60.0)
    out["sin_time_of_day"] = np.sin(2.0 * np.pi * time_of_day / 24.0)
    out["cos_time_of_day"] = np.cos(2.0 * np.pi * time_of_day / 24.0)

    # Annual / seasonal cyclic features
    day_of_year = (
        out["TIMESTAMP"].dt.day_of_year
        if hasattr(out["TIMESTAMP"].dt, "day_of_year")
        else out["TIMESTAMP"].dt.dayofyear
    )
    out["sin_day_of_year"] = np.sin(2.0 * np.pi * day_of_year / 365.25)
    out["cos_day_of_year"] = np.cos(2.0 * np.pi * day_of_year / 365.25)

    # Operational daylight indicator (threshold at strictly positive irradiance)
    out["is_daylight"] = out["IRRADIATION"] > 0.0

    # Ensure SOURCE_KEY is categorical for model handling
    out["SOURCE_KEY"] = out["SOURCE_KEY"].astype("category")
    out["PLANT_ID"] = out["PLANT_ID"].astype("category")

    return out


def prepare_model_ready_dataset(
    df: pd.DataFrame,
    daylight_only: bool = True,
    drop_missing_weather: bool = True,
    feature_mode: str = "baseline",
    target_col: str = TARGET_COLUMN,
) -> Tuple[pd.DataFrame, List[str], str]:
    """
    Prepares a clean, leak-free dataset ready for model training and evaluation.

    Parameters
    ----------
    df : pd.DataFrame
        Dataframe with engineered features.
    daylight_only : bool, default=True
        Whether to filter for daylight intervals (IRRADIATION > 0). Nighttime
        solar generation is trivially 0 kW and biases evaluation metrics.
    drop_missing_weather : bool, default=True
        Whether to exclude records lacking weather measurements.
    feature_mode : str, default='baseline'
        One of 'baseline' (onsite sensors only) or 'weather_enriched' (onsite + external).
    target_col : str, default=TARGET_COLUMN ('AC_POWER_KW')
        Target column name.

    Returns
    -------
    Tuple[pd.DataFrame, List[str], str]
        - Clean model-ready dataframe.
        - List of approved feature column names (X).
        - Name of target column (y).
    """
    model_df = df.copy()

    # Drop missing weather observations (e.g. Plant 1 2020-06-03 14:00 records)
    if drop_missing_weather and "has_weather" in model_df.columns:
        model_df = model_df[model_df["has_weather"]].copy()

    # Filter for operational daylight if requested
    if daylight_only and "is_daylight" in model_df.columns:
        model_df = model_df[model_df["is_daylight"]].copy()

    # Determine feature columns based on mode
    if feature_mode == "baseline":
        candidate_features = BASELINE_FEATURE_COLUMNS
    elif feature_mode == "weather_enriched":
        candidate_features = BASELINE_FEATURE_COLUMNS + WEATHER_ENRICHED_CANDIDATE_COLUMNS
    else:
        raise ValueError(f"Unknown feature_mode '{feature_mode}'. Expected 'baseline' or 'weather_enriched'.")

    feature_cols = [c for c in candidate_features if c in model_df.columns]

    # Strict target leakage assertion
    leaked_cols = set(feature_cols).intersection(set(FORBIDDEN_LEAKAGE_COLUMNS))
    if leaked_cols:
        raise AssertionError(f"CRITICAL LEAKAGE ERROR: Prohibited columns found in features: {leaked_cols}")

    if target_col not in model_df.columns:
        raise ValueError(f"Target column '{target_col}' not found in dataset.")

    # Drop any leftover NaNs in feature columns or target
    required_cols = feature_cols + [target_col]
    model_df = model_df.dropna(subset=required_cols).copy()

    return model_df, feature_cols, target_col
