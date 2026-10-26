"""
Verification of Model Artifact and Metrics Consistency
Recomputes test metrics from saved artifact and compares with reports.
"""
from pathlib import Path
import json
import sys
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.train import (
    create_chronological_splits,
    evaluate_predictions,
    load_model_artifact,
)

def verify():
    artifact_path = Path("models/best_solar_model.joblib")
    metrics_path = Path("reports/metrics_milestone_5_comparison.json")
    data_path = Path("data/processed/combined_model_ready.parquet")

    print(f"Loading artifact from {artifact_path}...")
    pipeline, meta = load_model_artifact(artifact_path)
    print(f"Model Name: {meta.get('model_name')}")
    print(f"Features: {meta.get('features')}")
    print(f"Feature count: {len(meta.get('features', []))}")

    # Verify no leakage features
    prohibited = ["DC_POWER", "DAILY_YIELD", "TOTAL_YIELD", "AC_POWER", "AC_POWER_KW"]
    for p in prohibited:
        assert p not in meta.get("features", []), f"Leakage feature {p} found in model features!"

    print("Leakage verification passed: No target or cumulative output columns in features.")

    print(f"Loading data from {data_path}...")
    df = pd.read_parquet(data_path)
    train_df, val_df, test_df, split_meta = create_chronological_splits(df)

    print(f"Chronological split timestamps:")
    print(f"Train: {split_meta['train']['start']} to {split_meta['train']['end']} ({len(train_df)} rows)")
    print(f"Val:   {split_meta['val']['start']} to {split_meta['val']['end']} ({len(val_df)} rows)")
    print(f"Test:  {split_meta['test']['start']} to {split_meta['test']['end']} ({len(test_df)} rows)")

    # Predict on test
    features = meta["features"]
    target = meta.get("target", "AC_POWER_KW")
    X_test = test_df[features]
    y_test = test_df[target]

    y_pred = pipeline.predict(X_test)
    y_pred_clipped = np.maximum(0.0, y_pred)

    mae = float(mean_absolute_error(y_test, y_pred_clipped))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred_clipped)))
    r2 = float(r2_score(y_test, y_pred_clipped))
    denom = float(np.sum(np.abs(y_test)))
    wape_pct = float(np.sum(np.abs(y_test - y_pred_clipped)) / denom * 100.0) if denom > 0 else 0.0

    print("\n--- RECOMPUTED TEST METRICS ---")
    print(f"MAE:  {mae:.4f} kW ({mae*1000:.1f} W)")
    print(f"RMSE: {rmse:.4f} kW ({rmse*1000:.1f} W)")
    print(f"R²:   {r2:.4f}")
    print(f"WAPE: {wape_pct:.2f}%")

    with open(metrics_path, "r", encoding="utf-8") as f:
        saved_metrics = json.load(f)

    baseline_metrics = saved_metrics.get("test_metrics", {}).get("Baseline (RandomForest)", {})
    print("\n--- SAVED METRICS IN REPORT ---")
    print(baseline_metrics)

    assert abs(mae - baseline_metrics["mae"]) < 1e-4, f"MAE mismatch: recomputed={mae}, saved={baseline_metrics['mae']}"
    assert abs(rmse - baseline_metrics["rmse"]) < 1e-4, f"RMSE mismatch: recomputed={rmse}, saved={baseline_metrics['rmse']}"
    assert abs(r2 - baseline_metrics["r2"]) < 1e-4, f"R² mismatch: recomputed={r2}, saved={baseline_metrics['r2']}"
    assert abs(wape_pct - baseline_metrics["wape_pct"]) < 1e-2, f"WAPE mismatch: recomputed={wape_pct}, saved={baseline_metrics['wape_pct']}"

    print("\nSUCCESS: Recomputed metrics match saved Milestone 5 report exactly!")

if __name__ == "__main__":
    verify()
