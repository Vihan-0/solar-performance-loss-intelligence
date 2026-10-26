"""
Dashboard Data and Analytics Helper Module
Project: Adaptive Solar Performance & Loss Intelligence

Provides cached data loaders, dataset preparation, and live simulation functions
for the Streamlit dashboard without duplicating core ML/detection logic.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd

from src.detect import (
    estimate_inverter_capacities,
    compute_cohort_expected_power,
    compute_model_expected_power,
    calculate_residuals,
    calibrate_thresholds,
    apply_persistence_filter,
    IRRADIANCE_BINS,
    IRRADIANCE_LABELS,
)
from src.loss import (
    compute_interval_shortfall,
    aggregate_inverter_loss_summary,
    aggregate_plant_loss_summary,
)
from src.train import (
    create_chronological_splits,
    load_model_artifact,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = REPO_ROOT / "data" / "processed" / "combined_model_ready.parquet"
MERGED_PATH = REPO_ROOT / "data" / "processed" / "combined_merged.parquet"
MODEL_PATH = REPO_ROOT / "models" / "best_solar_model.joblib"
METRICS_PATH = REPO_ROOT / "reports" / "metrics_milestone_5_comparison.json"
ANOMALY_PATH = REPO_ROOT / "reports" / "anomaly_report_milestone_5.json"


def load_reports() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Loads current Milestone 5 metrics and anomaly intelligence reports."""
    metrics_data = {}
    if METRICS_PATH.exists():
        with open(METRICS_PATH, "r", encoding="utf-8") as f:
            metrics_data = json.load(f)

    anomaly_data = {}
    if ANOMALY_PATH.exists():
        with open(ANOMALY_PATH, "r", encoding="utf-8") as f:
            anomaly_data = json.load(f)

    return metrics_data, anomaly_data


def load_pipeline_artifact():
    """Loads trained regression model pipeline and metadata."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model artifact not found: {MODEL_PATH}")
    return load_model_artifact(MODEL_PATH)


def load_processed_data() -> pd.DataFrame:
    """Loads the clean combined daylight dataset."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Data file not found: {DATA_PATH}")
    return pd.read_parquet(DATA_PATH)


def prepare_evaluation_datasets() -> Dict[str, Any]:
    """
    Prepares train, validation, and test partitions with baseline predictions,
    residuals, calibrated thresholds, and persistent anomaly flags in kW/kWh.
    """
    df = load_processed_data()
    pipeline, meta = load_pipeline_artifact()
    features = meta.get("features", meta.get("numerical_features", []) + meta.get("categorical_features", []))

    train_df, val_df, test_df, split_meta = create_chronological_splits(df)

    # 1. Capacities from train in kW
    capacities = estimate_inverter_capacities(train_df, power_col="AC_POWER_KW", quantile=0.995)

    # 2. Validation baselines & thresholds in kW
    val_eval = val_df.copy()
    val_eval["expected_model"] = compute_model_expected_power(pipeline, val_eval, features)
    val_eval["expected_cohort"] = compute_cohort_expected_power(val_eval, capacities, power_col="AC_POWER_KW")
    val_eval["res_model"], _ = calculate_residuals(val_eval["AC_POWER_KW"], val_eval["expected_model"], min_expected_power=0.050)
    val_eval["res_cohort"], _ = calculate_residuals(val_eval["AC_POWER_KW"], val_eval["expected_cohort"], min_expected_power=0.050)

    val_thresholds_model = calibrate_thresholds(
        val_eval, residual_col="res_model", quantile=0.95, min_threshold_kw=0.030, exclude_calibration_dropouts=True
    )
    val_thresholds_cohort = calibrate_thresholds(
        val_eval, residual_col="res_cohort", quantile=0.95, min_threshold_kw=0.030, exclude_calibration_dropouts=True
    )

    # 3. Test evaluation in kW
    test_eval = test_df.copy()
    test_eval["expected_model"] = compute_model_expected_power(pipeline, test_eval, features)
    test_eval["expected_cohort"] = compute_cohort_expected_power(test_eval, capacities, power_col="AC_POWER_KW")

    test_eval["res_model"], test_eval["rel_model"] = calculate_residuals(
        test_eval["AC_POWER_KW"], test_eval["expected_model"], min_expected_power=0.050
    )
    test_eval["res_cohort"], test_eval["rel_cohort"] = calculate_residuals(
        test_eval["AC_POWER_KW"], test_eval["expected_cohort"], min_expected_power=0.050
    )

    test_eval["irr_bin"] = pd.cut(test_eval["IRRADIATION"], bins=IRRADIANCE_BINS, labels=IRRADIANCE_LABELS)
    lookup_pairs = list(zip(test_eval["PLANT_ID"].astype(int), test_eval["irr_bin"].astype(str)))
    test_eval["thresh_model"] = [val_thresholds_model.get(p, 0.050) for p in lookup_pairs]
    test_eval["thresh_cohort"] = [val_thresholds_cohort.get(p, 0.050) for p in lookup_pairs]

    test_eval["cand_combined"] = (test_eval["res_model"] > test_eval["thresh_model"]) | (test_eval["res_cohort"] > test_eval["thresh_cohort"])
    test_eval["is_persistent_anomaly"] = apply_persistence_filter(test_eval, "cand_combined", min_consecutive=3)

    test_eval["shortfall_kwh"] = compute_interval_shortfall(
        test_eval["AC_POWER_KW"], test_eval["expected_model"], is_daylight=test_eval["is_daylight"]
    )

    inverter_summary = aggregate_inverter_loss_summary(
        test_eval, expected_col="expected_model", actual_col="AC_POWER_KW", persistent_flag_col="is_persistent_anomaly"
    )
    plant_summary = aggregate_plant_loss_summary(
        test_eval, expected_col="expected_model", actual_col="AC_POWER_KW", persistent_flag_col="is_persistent_anomaly"
    )

    return {
        "train_df": train_df,
        "val_df": val_eval,
        "test_df": test_eval,
        "split_meta": split_meta,
        "capacities": capacities,
        "val_thresholds_model": val_thresholds_model,
        "val_thresholds_cohort": val_thresholds_cohort,
        "inverter_summary": inverter_summary,
        "plant_summary": plant_summary,
        "pipeline": pipeline,
        "features": features,
    }


def simulate_synthetic_event(
    test_df: pd.DataFrame,
    plant_id: int,
    source_key: str,
    start_time: pd.Timestamp,
    duration_intervals: int,
    reduction_pct: float,
    val_thresholds_model: Dict,
    val_thresholds_cohort: Dict,
    capacities: Dict,
    pipeline: Any,
    features: List[str],
) -> Dict[str, Any]:
    """
    Simulates a synthetic underperformance event and runs detection on the isolated copy.

    Returns comparison timeline and detection verification.
    """
    sim_df = test_df.copy()

    # Find target inverter intervals
    inv_mask = (sim_df["PLANT_ID"] == plant_id) & (sim_df["SOURCE_KEY"] == source_key)
    inv_data = sim_df[inv_mask].sort_values("TIMESTAMP")

    # Pick consecutive intervals starting from start_time
    after_start = inv_data[inv_data["TIMESTAMP"] >= start_time]
    if len(after_start) < duration_intervals:
        target_timestamps = after_start["TIMESTAMP"].values
    else:
        target_timestamps = after_start["TIMESTAMP"].iloc[:duration_intervals].values

    # Apply reduction to canonical AC_POWER_KW
    inj_mask = inv_mask & (sim_df["TIMESTAMP"].isin(target_timestamps))
    sim_df.loc[inj_mask, "AC_POWER_KW"] = sim_df.loc[inj_mask, "AC_POWER_KW"] * (1.0 - (reduction_pct / 100.0))
    if "AC_POWER" in sim_df.columns:
        sim_df.loc[inj_mask, "AC_POWER"] = sim_df.loc[inj_mask, "AC_POWER_KW"] * 1000.0

    # Re-compute baselines and detection in kW
    sim_df["expected_model"] = compute_model_expected_power(pipeline, sim_df, features)
    sim_df["expected_cohort"] = compute_cohort_expected_power(sim_df, capacities, power_col="AC_POWER_KW")
    sim_df["res_model"], _ = calculate_residuals(sim_df["AC_POWER_KW"], sim_df["expected_model"], min_expected_power=0.050)
    sim_df["res_cohort"], _ = calculate_residuals(sim_df["AC_POWER_KW"], sim_df["expected_cohort"], min_expected_power=0.050)

    sim_df["irr_bin"] = pd.cut(sim_df["IRRADIATION"], bins=IRRADIANCE_BINS, labels=IRRADIANCE_LABELS)
    lookup_pairs = list(zip(sim_df["PLANT_ID"].astype(int), sim_df["irr_bin"].astype(str)))
    sim_df["thresh_model"] = [val_thresholds_model.get(p, 0.050) for p in lookup_pairs]
    sim_df["thresh_cohort"] = [val_thresholds_cohort.get(p, 0.050) for p in lookup_pairs]

    sim_df["cand_combined"] = (sim_df["res_model"] > sim_df["thresh_model"]) | (sim_df["res_cohort"] > sim_df["thresh_cohort"])
    sim_df["is_persistent_anomaly"] = apply_persistence_filter(sim_df, "cand_combined", min_consecutive=3)

    # Injected slice timeline
    injected_timeline = sim_df[inv_mask].sort_values("TIMESTAMP")
    injected_slice = injected_timeline[injected_timeline["TIMESTAMP"].isin(target_timestamps)]

    event_detected = bool(injected_slice["is_persistent_anomaly"].any())
    all_intervals_flagged = bool(injected_slice["is_persistent_anomaly"].all())
    expected_to_trigger = duration_intervals >= 3 and reduction_pct >= 30.0

    return {
        "timeline": injected_timeline,
        "target_timestamps": target_timestamps,
        "event_detected": event_detected,
        "all_intervals_flagged": all_intervals_flagged,
        "expected_to_trigger": expected_to_trigger,
        "duration_minutes": len(target_timestamps) * 15,
        "reduction_pct": reduction_pct,
    }
