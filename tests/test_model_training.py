"""
Milestone 3 Tests: Model Training, Splitting, and Evaluation Verification
Validates chronological splitting, group integrity, leakage avoidance,
unseen category handling, and artifact reproducibility.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.train import (
    create_chronological_splits,
    build_model_pipeline,
    evaluate_predictions,
    evaluate_by_slices,
    load_model_artifact,
    NUMERICAL_FEATURES,
    CATEGORICAL_FEATURES,
    TARGET_COLUMN,
)
from src.features import FORBIDDEN_LEAKAGE_COLUMNS

PROCESSED_FILE = Path(__file__).resolve().parent.parent / "data" / "processed" / "combined_model_ready.parquet"
MODEL_ARTIFACT = Path(__file__).resolve().parent.parent / "models" / "best_solar_model.joblib"


@pytest.fixture(scope="module")
def model_ready_data():
    assert PROCESSED_FILE.exists(), f"Processed data {PROCESSED_FILE} missing."
    return pd.read_parquet(PROCESSED_FILE)


def test_chronological_split_strict_ordering(model_ready_data):
    train_df, val_df, test_df, meta = create_chronological_splits(
        model_ready_data,
        timestamp_col="TIMESTAMP",
        train_ratio=0.60,
        val_ratio=0.20,
        test_ratio=0.20,
    )

    # Row count preservation
    assert len(train_df) + len(val_df) + len(test_df) == len(model_ready_data)

    # Unique timestamps
    train_ts = set(train_df["TIMESTAMP"].unique())
    val_ts = set(val_df["TIMESTAMP"].unique())
    test_ts = set(test_df["TIMESTAMP"].unique())

    # Zero overlap across sets
    assert len(train_ts.intersection(val_ts)) == 0, "Train and Val share timestamps!"
    assert len(val_ts.intersection(test_ts)) == 0, "Val and Test share timestamps!"
    assert len(train_ts.intersection(test_ts)) == 0, "Train and Test share timestamps!"

    # Strict temporal ordering: max(train) < min(val) and max(val) < min(test)
    assert train_df["TIMESTAMP"].max() < val_df["TIMESTAMP"].min()
    assert val_df["TIMESTAMP"].max() < test_df["TIMESTAMP"].min()


def test_group_integrity_same_timestamp_cohesion(model_ready_data):
    train_df, val_df, test_df, _ = create_chronological_splits(model_ready_data)

    # For any timestamp in train_df, ALL rows in model_ready_data with that timestamp must be in train_df
    sample_ts = train_df["TIMESTAMP"].iloc[0]
    expected_count = (model_ready_data["TIMESTAMP"] == sample_ts).sum()
    train_count = (train_df["TIMESTAMP"] == sample_ts).sum()
    assert expected_count == train_count, "Observations from the same timestamp were split across folds!"


def test_prohibited_leakage_features():
    # Assert that no forbidden column appears in feature lists
    all_features = NUMERICAL_FEATURES + CATEGORICAL_FEATURES
    for forbidden in FORBIDDEN_LEAKAGE_COLUMNS:
        assert forbidden not in all_features, f"Forbidden leakage column '{forbidden}' in features!"


def test_unseen_categorical_safety(model_ready_data):
    # Train pipeline on tiny sample
    train_df, _, _, _ = create_chronological_splits(model_ready_data)
    sample_train = train_df.head(200).copy()

    features = NUMERICAL_FEATURES + CATEGORICAL_FEATURES
    pipe = build_model_pipeline(
        "ridge",
        numerical_cols=NUMERICAL_FEATURES,
        categorical_cols=CATEGORICAL_FEATURES,
    )
    pipe.fit(sample_train[features], sample_train[TARGET_COLUMN])

    # Construct test sample with completely unseen SOURCE_KEY and PLANT_ID
    unseen_df = sample_train.head(5).copy()
    unseen_df["SOURCE_KEY"] = "BRAND_NEW_INVERTER_9999"
    unseen_df["PLANT_ID"] = 9999999

    # Must NOT raise exception; handle_unknown='ignore' should safely zeros-out one-hot
    preds = pipe.predict(unseen_df[features])
    assert len(preds) == 5
    assert not np.isnan(preds).any()


def test_model_artifact_load_and_predict(model_ready_data):
    assert MODEL_ARTIFACT.exists(), f"Model artifact {MODEL_ARTIFACT} missing."
    pipe, meta = load_model_artifact(MODEL_ARTIFACT)

    assert "model_name" in meta
    assert "validation_metrics" in meta
    assert "test_metrics" in meta

    features = NUMERICAL_FEATURES + CATEGORICAL_FEATURES
    sample_x = model_ready_data[features].head(20)
    preds = pipe.predict(sample_x)
    assert len(preds) == 20
    assert not np.isnan(preds).any()


def test_evaluation_metric_properties():
    # Sanity checks on evaluate_predictions
    y_true = pd.Series([100.0, 200.0, 300.0])
    y_pred = np.array([110.0, 190.0, 300.0])

    metrics = evaluate_predictions(y_true, y_pred)
    assert np.isclose(metrics["mae"], 6.6667, atol=1e-3)
    assert np.isclose(metrics["rmse"], 8.1650, atol=1e-3)
    assert metrics["r2"] > 0.98
    assert np.isclose(metrics["mean_residual"], 0.0, atol=1e-3)
