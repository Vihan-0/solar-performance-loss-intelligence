"""
Milestone 5 Tests: Dashboard Data and Simulation Verification
Validates dashboard data bundles, report loading, and live synthetic simulation logic.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.dashboard_data import (
    load_reports,
    load_pipeline_artifact,
    load_processed_data,
    prepare_evaluation_datasets,
    simulate_synthetic_event,
)


def test_load_reports():
    metrics_data, anomaly_data = load_reports()
    assert isinstance(metrics_data, dict)
    assert isinstance(anomaly_data, dict)
    assert "test_metrics" in metrics_data
    assert "fleet_totals_kwh" in anomaly_data or "test_energy_summary" in anomaly_data


def test_load_pipeline_artifact():
    pipe, meta = load_pipeline_artifact()
    assert hasattr(pipe, "predict")
    assert "model_name" in meta
    assert any(m in meta["model_name"] for m in ["RandomForest", "HistGradientBoosting", "Ridge"])


def test_load_processed_data():
    df = load_processed_data()
    assert len(df) == 77098
    assert "TIMESTAMP" in df.columns
    assert "AC_POWER" in df.columns


def test_prepare_evaluation_datasets():
    bundle = prepare_evaluation_datasets()
    assert "train_df" in bundle
    assert "val_df" in bundle
    assert "test_df" in bundle
    assert "inverter_summary" in bundle
    assert "plant_summary" in bundle

    test_df = bundle["test_df"]
    required_cols = [
        "expected_model",
        "expected_cohort",
        "res_model",
        "res_cohort",
        "is_persistent_anomaly",
        "shortfall_kwh",
    ]
    for col in required_cols:
        assert col in test_df.columns, f"Missing {col} in prepared test_df"

    inv_sum = bundle["inverter_summary"]
    assert len(inv_sum) == 44  # 44 inverters
    assert "urgency_rank" in inv_sum.columns
    assert "persistent_shortfall_kwh" in inv_sum.columns


def test_simulate_synthetic_event():
    bundle = prepare_evaluation_datasets()
    test_df = bundle["test_df"]
    pipeline = bundle["pipeline"]
    features = bundle["features"]
    capacities = bundle["capacities"]
    val_thresh_model = bundle["val_thresholds_model"]
    val_thresh_cohort = bundle["val_thresholds_cohort"]

    # Target inverter in Plant 1
    plant_id = 4135001
    source_key = "1BY6WEcLGh8j5v7"
    start_time = pd.Timestamp("2020-06-12 11:00:00")

    # 1. Test persistent 4-interval trip (100% reduction) -> Must trigger
    res_persistent = simulate_synthetic_event(
        test_df=test_df,
        plant_id=plant_id,
        source_key=source_key,
        start_time=start_time,
        duration_intervals=4,
        reduction_pct=100.0,
        val_thresholds_model=val_thresh_model,
        val_thresholds_cohort=val_thresh_cohort,
        capacities=capacities,
        pipeline=pipeline,
        features=features,
    )
    assert res_persistent["event_detected"] is True
    assert res_persistent["duration_minutes"] == 60

    # 2. Test transient 1-interval dip (80% reduction) -> Must be rejected by persistence filter
    res_transient = simulate_synthetic_event(
        test_df=test_df,
        plant_id=plant_id,
        source_key=source_key,
        start_time=start_time,
        duration_intervals=1,
        reduction_pct=80.0,
        val_thresholds_model=val_thresh_model,
        val_thresholds_cohort=val_thresh_cohort,
        capacities=capacities,
        pipeline=pipeline,
        features=features,
    )
    assert res_transient["event_detected"] is False
    assert res_transient["duration_minutes"] == 15
