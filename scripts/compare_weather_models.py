"""
Model Comparison Script: Baseline Onsite vs Weather-Enriched Models
Adaptive Solar Performance & Loss Intelligence
Milestone 5 - Phase 4

Performs a fair, leak-free comparison between:
A. Baseline Model: Onsite sensors + cyclical timing + plant/inverter categoricals (10 features)
B. Weather-Enriched Model: Baseline features + Open-Meteo external weather (16 features)

Evaluates on identical chronological 60/20/20 splits:
- Sliced by plant (Plant 1 vs Plant 2)
- Sliced by irradiance regime (Low, Medium, High)
- Residual distributions
Saves:
- reports/metrics_milestone_5_comparison.json
- models/best_solar_model.joblib
"""

import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.train import (
    create_chronological_splits,
    build_model_pipeline,
    evaluate_predictions,
    evaluate_by_slices,
    save_model_artifact,
    BASELINE_NUMERICAL_FEATURES,
    WEATHER_ENRICHED_NUMERICAL_FEATURES,
    CATEGORICAL_FEATURES,
    TARGET_COLUMN,
)

DATA_PATH = REPO_ROOT / "data" / "processed" / "combined_model_ready_enriched.parquet"
MODELS_DIR = REPO_ROOT / "models"
REPORTS_DIR = REPO_ROOT / "reports"


def run_model_comparison():
    print("=" * 80)
    print("MILESTONE 5: BASELINE VS WEATHER-ENRICHED MODEL COMPARISON")
    print("=" * 80)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n[1/6] Loading combined dataset from {DATA_PATH}...")
    df = pd.read_parquet(DATA_PATH)
    print(f"  Loaded {len(df):,} daylight records across {df['TIMESTAMP'].nunique():,} unique timestamps.")

    # Chronological Split (60% Train, 20% Val, 20% Test)
    print("\n[2/6] Generating identical chronological splits...")
    train_df, val_df, test_df, split_meta = create_chronological_splits(
        df, timestamp_col="TIMESTAMP", train_ratio=0.60, val_ratio=0.20, test_ratio=0.20
    )

    print(f"  Train: {len(train_df):,} rows | {split_meta['train']['start']} to {split_meta['train']['end']}")
    print(f"  Val:   {len(val_df):,} rows | {split_meta['val']['start']} to {split_meta['val']['end']}")
    print(f"  Test:  {len(test_df):,} rows | {split_meta['test']['start']} to {split_meta['test']['end']}")

    # Feature configurations
    baseline_features = BASELINE_NUMERICAL_FEATURES + CATEGORICAL_FEATURES
    enriched_features = WEATHER_ENRICHED_NUMERICAL_FEATURES + CATEGORICAL_FEATURES

    y_train = train_df[TARGET_COLUMN]
    y_val = val_df[TARGET_COLUMN]
    y_test = test_df[TARGET_COLUMN]

    # Models to test
    models_to_run = {
        "Baseline (Ridge)": {
            "type": "ridge",
            "num_cols": BASELINE_NUMERICAL_FEATURES,
            "cat_cols": CATEGORICAL_FEATURES,
            "features": baseline_features,
            "kwargs": {"alpha": 10.0},
        },
        "Enriched (Ridge)": {
            "type": "ridge",
            "num_cols": WEATHER_ENRICHED_NUMERICAL_FEATURES,
            "cat_cols": CATEGORICAL_FEATURES,
            "features": enriched_features,
            "kwargs": {"alpha": 10.0},
        },
        "Baseline (HistGBR)": {
            "type": "hist_gbr",
            "num_cols": BASELINE_NUMERICAL_FEATURES,
            "cat_cols": CATEGORICAL_FEATURES,
            "features": baseline_features,
            "kwargs": {"max_iter": 150, "max_depth": 8},
        },
        "Enriched (HistGBR)": {
            "type": "hist_gbr",
            "num_cols": WEATHER_ENRICHED_NUMERICAL_FEATURES,
            "cat_cols": CATEGORICAL_FEATURES,
            "features": enriched_features,
            "kwargs": {"max_iter": 150, "max_depth": 8},
        },
        "Baseline (RandomForest)": {
            "type": "random_forest",
            "num_cols": BASELINE_NUMERICAL_FEATURES,
            "cat_cols": CATEGORICAL_FEATURES,
            "features": baseline_features,
            "kwargs": {"n_estimators": 100, "max_depth": 16},
        },
        "Enriched (RandomForest)": {
            "type": "random_forest",
            "num_cols": WEATHER_ENRICHED_NUMERICAL_FEATURES,
            "cat_cols": CATEGORICAL_FEATURES,
            "features": enriched_features,
            "kwargs": {"n_estimators": 100, "max_depth": 16},
        },
    }

    trained_pipelines = {}
    train_metrics = {}
    val_metrics = {}
    test_metrics = {}

    print("\n[3/6] Fitting candidate models on training partition...")
    for name, spec in models_to_run.items():
        print(f"  Fitting {name}...")
        pipe = build_model_pipeline(
            model_type=spec["type"],
            numerical_cols=spec["num_cols"],
            categorical_cols=spec["cat_cols"],
            random_state=42,
            **spec["kwargs"],
        )
        X_tr = train_df[spec["features"]]
        pipe.fit(X_tr, y_train)
        trained_pipelines[name] = pipe

        # Evaluate train
        train_metrics[name] = evaluate_predictions(y_train, pipe.predict(X_tr))

        # Evaluate validation
        X_v = val_df[spec["features"]]
        val_metrics[name] = evaluate_predictions(y_val, pipe.predict(X_v))

        # Evaluate test
        X_te = test_df[spec["features"]]
        test_metrics[name] = evaluate_predictions(y_test, pipe.predict(X_te))

    # Print Validation Table
    print("\n" + "=" * 90)
    print(f"{'Model Variant':<28} | {'Val MAE (kW)':<13} | {'Val RMSE (kW)':<13} | {'Val R²':<8} | {'Val WAPE (%)':<12}")
    print("=" * 90)
    for name in models_to_run:
        m = val_metrics[name]
        print(f"{name:<28} | {m['mae']:<13.4f} | {m['rmse']:<13.4f} | {m['r2']:<8.4f} | {m['wape_pct']:<12.2f}")
    print("=" * 90)

    # Print Test Table
    print("\n" + "=" * 90)
    print(f"{'Model Variant (Test)':<28} | {'Test MAE (kW)':<13} | {'Test RMSE (kW)':<13} | {'Test R²':<8} | {'Test WAPE (%)':<12}")
    print("=" * 90)
    for name in models_to_run:
        m = test_metrics[name]
        print(f"{name:<28} | {m['mae']:<13.4f} | {m['rmse']:<13.4f} | {m['r2']:<8.4f} | {m['wape_pct']:<12.2f}")
    print("=" * 90)

    # Compare Baseline vs Enriched for the leading architecture
    base_rf_val_mae = val_metrics["Baseline (RandomForest)"]["mae"]
    enr_rf_val_mae = val_metrics["Enriched (RandomForest)"]["mae"]
    delta_val_mae = enr_rf_val_mae - base_rf_val_mae

    print(f"\n[4/6] Validation Delta (Enriched - Baseline): {delta_val_mae:+.4f} kW ({delta_val_mae / base_rf_val_mae * 100:+.2f}%)")

    # Select best model based strictly on validation MAE
    best_name = min(val_metrics.keys(), key=lambda k: val_metrics[k]["mae"])
    print(f"  Selected Model based on Validation: {best_name} (Val MAE: {val_metrics[best_name]['mae']:.4f} kW)")

    # Diagnostic performance slices
    print(f"\n[5/6] Computing diagnostic performance slices for {best_name} and Baseline (RandomForest)...")
    base_pipe = trained_pipelines["Baseline (RandomForest)"]
    enr_pipe = trained_pipelines["Enriched (RandomForest)"]

    base_slices = evaluate_by_slices(base_pipe, test_df, baseline_features, target=TARGET_COLUMN)
    enr_slices = evaluate_by_slices(enr_pipe, test_df, enriched_features, target=TARGET_COLUMN)

    print("\n--- Out-of-Time Test Set Slices Comparison ---")
    print("\nBy Plant:")
    for pid in ["4135001", "4136001"]:
        b_p = base_slices["by_plant"].get(pid, {})
        e_p = enr_slices["by_plant"].get(pid, {})
        print(f"  Plant {pid}:")
        print(f"    Baseline: MAE={b_p.get('mae', 0):.4f} kW, RMSE={b_p.get('rmse', 0):.4f} kW, R²={b_p.get('r2', 0):.4f}")
        print(f"    Enriched: MAE={e_p.get('mae', 0):.4f} kW, RMSE={e_p.get('rmse', 0):.4f} kW, R²={e_p.get('r2', 0):.4f}")

    print("\nBy Irradiance Regime:")
    for reg in base_slices["by_irradiance"]:
        b_r = base_slices["by_irradiance"].get(reg, {})
        e_r = enr_slices["by_irradiance"].get(reg, {})
        print(f"  {reg}:")
        print(f"    Baseline: MAE={b_r.get('mae', 0):.4f} kW, RMSE={b_r.get('rmse', 0):.4f} kW, R²={b_r.get('r2', 0):.4f}")
        print(f"    Enriched: MAE={e_r.get('mae', 0):.4f} kW, RMSE={e_r.get('rmse', 0):.4f} kW, R²={e_r.get('r2', 0):.4f}")

    # Residual distributions
    test_df_eval = test_df.copy()
    test_df_eval["pred_base"] = base_pipe.predict(test_df[baseline_features])
    test_df_eval["pred_enr"] = enr_pipe.predict(test_df[enriched_features])
    test_df_eval["res_base"] = test_df_eval["pred_base"] - test_df_eval[TARGET_COLUMN]
    test_df_eval["res_enr"] = test_df_eval["pred_enr"] - test_df_eval[TARGET_COLUMN]

    residual_stats = {
        "baseline": {
            "mean": float(test_df_eval["res_base"].mean()),
            "std": float(test_df_eval["res_base"].std()),
            "median": float(test_df_eval["res_base"].median()),
            "q95": float(test_df_eval["res_base"].quantile(0.95)),
            "q99": float(test_df_eval["res_base"].quantile(0.99)),
        },
        "enriched": {
            "mean": float(test_df_eval["res_enr"].mean()),
            "std": float(test_df_eval["res_enr"].std()),
            "median": float(test_df_eval["res_enr"].median()),
            "q95": float(test_df_eval["res_enr"].quantile(0.95)),
            "q99": float(test_df_eval["res_enr"].quantile(0.99)),
        },
    }

    print("\nResidual Distribution Comparison (Expected - Actual kW):")
    print(f"  Baseline: Mean={residual_stats['baseline']['mean']:+.4f} kW, Std={residual_stats['baseline']['std']:.4f} kW, 95th={residual_stats['baseline']['q95']:.4f} kW")
    print(f"  Enriched: Mean={residual_stats['enriched']['mean']:+.4f} kW, Std={residual_stats['enriched']['std']:.4f} kW, 95th={residual_stats['enriched']['q95']:.4f} kW")

    # Persist the chosen model artifact (prefer simpler baseline if enrichment does not provide decisive improvement)
    # Check if enriched provides meaningful improvement (e.g. > 1% reduction in Val MAE)
    improvement_pct = (base_rf_val_mae - enr_rf_val_mae) / base_rf_val_mae * 100.0
    if improvement_pct > 1.0:
        winning_model_name = "Enriched (RandomForest)"
        winning_pipeline = enr_pipe
        winning_features = enriched_features
        decision_reason = f"Enriched model achieved {improvement_pct:.2f}% MAE improvement on validation."
    else:
        winning_model_name = "Baseline (RandomForest)"
        winning_pipeline = base_pipe
        winning_features = baseline_features
        decision_reason = (
            f"External weather enrichment yielded marginal delta ({improvement_pct:+.2f}% on Val MAE). "
            "In accordance with Occam's razor and engineering constraints, simpler onsite baseline model is retained."
        )

    print(f"\n[6/6] Final Architectural Decision: {winning_model_name}")
    print(f"  Rationale: {decision_reason}")

    artifact_path = MODELS_DIR / "best_solar_model.joblib"
    meta = {
        "model_name": winning_model_name,
        "features": winning_features,
        "target": TARGET_COLUMN,
        "decision_reason": decision_reason,
        "validation_metrics": val_metrics[winning_model_name],
        "test_metrics": test_metrics[winning_model_name],
        "split_metadata": split_meta,
    }
    save_model_artifact(winning_pipeline, artifact_path, metadata=meta)
    print(f"  Persisted winning model pipeline to {artifact_path}")

    # Save metrics JSON
    metrics_report = {
        "split_metadata": split_meta,
        "models_evaluated": list(models_to_run.keys()),
        "validation_metrics": val_metrics,
        "test_metrics": test_metrics,
        "baseline_slices": base_slices,
        "enriched_slices": enr_slices,
        "residual_stats": residual_stats,
        "winning_model": winning_model_name,
        "decision_rationale": decision_reason,
    }
    out_json = REPORTS_DIR / "metrics_milestone_5_comparison.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(metrics_report, f, indent=2)
    print(f"  Saved comparison metrics to {out_json}")

    return metrics_report


if __name__ == "__main__":
    run_model_comparison()
