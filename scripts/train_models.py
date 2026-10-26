"""
Milestone 3: Model Training and Evaluation Script
Project: Adaptive Solar Performance & Loss Intelligence

Entry point for chronological training, validation selection, and out-of-time
test evaluation of baseline, regularized linear, and nonlinear regression models.
"""

import json
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure root directory is on Python path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.train import (
    create_chronological_splits,
    build_model_pipeline,
    evaluate_predictions,
    evaluate_by_slices,
    save_model_artifact,
    NUMERICAL_FEATURES,
    CATEGORICAL_FEATURES,
    TARGET_COLUMN,
)

DATA_PATH = REPO_ROOT / "data" / "processed" / "combined_model_ready.parquet"
MODELS_DIR = REPO_ROOT / "models"
REPORTS_DIR = REPO_ROOT / "reports"


def run_training_and_evaluation():
    print("=" * 80)
    print("MILESTONE 3: SOLAR AC POWER REGRESSION MODEL EVALUATION")
    print("=" * 80)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load data
    print(f"\n[1/5] Loading model-ready daylight dataset from {DATA_PATH}...")
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Model-ready dataset not found: {DATA_PATH}. Run scripts/build_dataset.py first.")

    df = pd.read_parquet(DATA_PATH)
    print(f"  Loaded {len(df):,} daylight records across {df['TIMESTAMP'].nunique():,} unique timestamps.")

    # 2. Chronological Splitting (60% Train, 20% Val, 20% Test)
    print("\n[2/5] Creating chronological splits based on unique sorted timestamps...")
    train_df, val_df, test_df, split_meta = create_chronological_splits(
        df,
        timestamp_col="TIMESTAMP",
        train_ratio=0.60,
        val_ratio=0.20,
        test_ratio=0.20,
    )

    print(f"  Total Rows: {len(df):,} | Unique Timestamps: {split_meta['total_unique_timestamps']:,}")
    print(f"  TRAIN: {split_meta['train']['rows']:,} rows | {split_meta['train']['timestamps_count']} ts | {split_meta['train']['start']} to {split_meta['train']['end']}")
    print(f"  VAL:   {split_meta['val']['rows']:,} rows | {split_meta['val']['timestamps_count']} ts | {split_meta['val']['start']} to {split_meta['val']['end']}")
    print(f"  TEST:  {split_meta['test']['rows']:,} rows | {split_meta['test']['timestamps_count']} ts | {split_meta['test']['start']} to {split_meta['test']['end']}")

    features = NUMERICAL_FEATURES + CATEGORICAL_FEATURES
    X_train, y_train = train_df[features], train_df[TARGET_COLUMN]
    X_val, y_val = val_df[features], val_df[TARGET_COLUMN]
    X_test, y_test = test_df[features], test_df[TARGET_COLUMN]

    # 3. Model Training & Validation Selection
    print("\n[3/5] Training candidate models strictly on training partition...")
    candidate_configs = {
        "Dummy (Mean Baseline)": {"model_type": "dummy", "strategy": "mean"},
        "Ridge (Regularized Linear)": {"model_type": "ridge", "alpha": 10.0},
        "HistGradientBoosting": {"model_type": "hist_gbr", "max_iter": 150, "max_depth": 8},
        "RandomForest": {"model_type": "random_forest", "n_estimators": 100, "max_depth": 16},
    }

    trained_pipelines = {}
    validation_results = {}
    train_results = {}

    for name, cfg in candidate_configs.items():
        print(f"  Fitting {name}...")
        m_type = cfg.pop("model_type")
        pipe = build_model_pipeline(
            model_type=m_type,
            numerical_cols=NUMERICAL_FEATURES,
            categorical_cols=CATEGORICAL_FEATURES,
            random_state=42,
            **cfg,
        )
        pipe.fit(X_train, y_train)
        trained_pipelines[name] = pipe

        # Evaluate on Train
        y_train_pred = pipe.predict(X_train)
        train_results[name] = evaluate_predictions(y_train, y_train_pred)

        # Evaluate on Validation
        y_val_pred = pipe.predict(X_val)
        val_eval = evaluate_predictions(y_val, y_val_pred)
        validation_results[name] = val_eval

    # Print Validation Comparison
    print("\n" + "-" * 75)
    print(f"{'Model':<30} | {'Val MAE (kW)':<12} | {'Val RMSE (kW)':<13} | {'Val R²':<8} | {'Val WAPE (%)':<10}")
    print("-" * 75)
    for name, m in validation_results.items():
        print(f"{name:<30} | {m['mae']:<12.2f} | {m['rmse']:<13.2f} | {m['r2']:<8.4f} | {m['wape_pct']:<10.2f}")
    print("-" * 75)

    # 4. Model Selection based strictly on Validation performance
    # Selection criterion: lowest Val MAE
    best_model_name = min(validation_results.keys(), key=lambda k: validation_results[k]["mae"])
    print(f"\n[4/5] Selected Best Model: {best_model_name} (Lowest Val MAE: {validation_results[best_model_name]['mae']:.2f} kW)")
    selected_pipeline = trained_pipelines[best_model_name]

    # 5. Out-of-Time Test Evaluation
    print("\n[5/5] Evaluating models on held-out test set (unseen future timestamps)...")
    test_results = {}
    for name, pipe in trained_pipelines.items():
        y_test_pred = pipe.predict(X_test)
        test_results[name] = evaluate_predictions(y_test, y_test_pred)

    print("\n" + "-" * 75)
    print(f"{'Model (Out-of-Time Test)':<30} | {'Test MAE (kW)':<13} | {'Test RMSE (kW)':<14} | {'Test R²':<8} | {'Test WAPE (%)':<10}")
    print("-" * 75)
    for name, m in test_results.items():
        print(f"{name:<30} | {m['mae']:<13.2f} | {m['rmse']:<14.2f} | {m['r2']:<8.4f} | {m['wape_pct']:<10.2f}")
    print("-" * 75)

    # Detailed Slices for Selected Model on Test Set
    test_slices = evaluate_by_slices(selected_pipeline, test_df, features, target=TARGET_COLUMN)

    print(f"\n--- Diagnostic Performance Slices for Selected Model ({best_model_name}) on Test Set ---")
    print("\nBy Plant:")
    for plant_id, pm in test_slices["by_plant"].items():
        print(f"  Plant {plant_id}: MAE={pm['mae']:.2f} kW | RMSE={pm['rmse']:.2f} kW | R²={pm['r2']:.4f} | WAPE={pm['wape_pct']:.2f}% (n={pm['sample_size']:,})")

    print("\nBy Irradiance Regime:")
    for regime, rm in test_slices["by_irradiance"].items():
        print(f"  {regime:<25}: MAE={rm['mae']:.2f} kW | RMSE={rm['rmse']:.2f} kW | R²={rm['r2']:.4f} | WAPE={rm['wape_pct']:.2f}% (n={rm['sample_size']:,})")

    # Inverter ranking by MAE
    inv_df = pd.DataFrame(test_slices["by_inverter"])
    inv_df = inv_df.sort_values("mae", ascending=False)
    print("\nTop 5 Highest Error Inverters in Test Set (Candidates for Deep Investigation):")
    for _, row in inv_df.head(5).iterrows():
        print(f"  Plant {row['PLANT_ID']} - Inverter {row['SOURCE_KEY']}: MAE={row['mae']:.2f} kW, Mean Residual={row['mean_residual']:+.2f} kW (n={row['sample_size']})")

    print("\nTop 5 Lowest Error Inverters in Test Set (Baseline Consistency):")
    for _, row in inv_df.tail(5).iterrows():
        print(f"  Plant {row['PLANT_ID']} - Inverter {row['SOURCE_KEY']}: MAE={row['mae']:.2f} kW, Mean Residual={row['mean_residual']:+.2f} kW (n={row['sample_size']})")

    # Save Model Artifact
    artifact_path = MODELS_DIR / "best_solar_model.joblib"
    artifact_metadata = {
        "model_name": best_model_name,
        "selected_on": "validation_mae",
        "split_metadata": split_meta,
        "numerical_features": NUMERICAL_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "target": TARGET_COLUMN,
        "validation_metrics": validation_results[best_model_name],
        "test_metrics": test_results[best_model_name],
    }
    save_model_artifact(selected_pipeline, artifact_path, metadata=artifact_metadata)
    print(f"\nPersisted winning model pipeline and metadata to {artifact_path}")

    # Save Machine-Readable Metrics JSON (archived Milestone 3 baseline run)
    archive_dir = REPORTS_DIR / "archive" / "superseded_pre_unit_audit"
    archive_dir.mkdir(parents=True, exist_ok=True)
    metrics_json_path = archive_dir / "metrics_milestone_3.json"
    full_metrics = {
        "split_metadata": split_meta,
        "train_metrics": train_results,
        "validation_metrics": validation_results,
        "test_metrics": test_results,
        "selected_model": best_model_name,
        "selected_model_test_slices": test_slices,
    }
    with open(metrics_json_path, "w", encoding="utf-8") as f:
        json.dump(full_metrics, f, indent=2)
    print(f"Saved machine-readable metrics to {metrics_json_path}")

    print("\n" + "=" * 80)
    print("MILESTONE 3 EXECUTION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    run_training_and_evaluation()
