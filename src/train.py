"""
Model Training, Chronological Splitting, and Evaluation Module
Project: Adaptive Solar Performance & Loss Intelligence

This module enforces:
1. Chronological splitting by unique timestamps (60% Train, 20% Validation, 20% Test).
2. Group integrity: observations from the same timestamp are never separated.
3. Strict isolation of training data for fitting pipelines (transformers + estimators).
4. Robust categorical encoding with unseen category protection (handle_unknown='ignore').
5. Diagnostic slicing: evaluation across plants, irradiance regimes, and inverters.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Default feature configuration
BASELINE_NUMERICAL_FEATURES = [
    "IRRADIATION",
    "AMBIENT_TEMPERATURE",
    "MODULE_TEMPERATURE",
    "TEMP_DIFF",
    "sin_time_of_day",
    "cos_time_of_day",
    "sin_day_of_year",
    "cos_day_of_year",
]

WEATHER_ENRICHED_NUMERICAL_FEATURES = BASELINE_NUMERICAL_FEATURES + [
    "ext_temp_c",
    "ext_rh_pct",
    "ext_precip_mm",
    "ext_cloud_cover_pct",
    "ext_wind_speed_kmh",
    "ext_radiation_kw_m2",
]

NUMERICAL_FEATURES = BASELINE_NUMERICAL_FEATURES

CATEGORICAL_FEATURES = [
    "PLANT_ID",
    "SOURCE_KEY",
]

TARGET_COLUMN = "AC_POWER_KW"

IRRADIANCE_BINS = [0.0, 0.2, 0.6, float("inf")]
IRRADIANCE_BIN_LABELS = ["Low (0-0.2 kW/m²)", "Medium (0.2-0.6 kW/m²)", "High (>0.6 kW/m²)"]


def create_chronological_splits(
    df: pd.DataFrame,
    timestamp_col: str = "TIMESTAMP",
    train_ratio: float = 0.60,
    val_ratio: float = 0.20,
    test_ratio: float = 0.20,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Partitions the dataset chronologically based on unique timestamp values.

    Guarantees:
    - Splitting is performed on sorted unique timestamps, NOT random rows.
    - All multi-inverter records at timestamp t remain in the same partition.
    - No temporal leakage: max(Train_t) < min(Val_t) <= max(Val_t) < min(Test_t).

    Parameters
    ----------
    df : pd.DataFrame
        Dataset containing timestamp_col.
    timestamp_col : str, default='TIMESTAMP'
        Datetime column name.
    train_ratio : float, default=0.60
    val_ratio : float, default=0.20
    test_ratio : float, default=0.20

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]]
        (train_df, val_df, test_df, split_metadata)
    """
    if not np.isclose(train_ratio + val_ratio + test_ratio, 1.0):
        raise ValueError("Train, validation, and test ratios must sum to 1.0")

    if timestamp_col not in df.columns:
        raise ValueError(f"Timestamp column '{timestamp_col}' not found in dataframe.")

    # Extract and sort unique timestamps
    unique_timestamps = np.sort(df[timestamp_col].unique())
    total_timestamps = len(unique_timestamps)

    n_train = int(np.floor(train_ratio * total_timestamps))
    n_val = int(np.floor(val_ratio * total_timestamps))
    n_test = total_timestamps - n_train - n_val

    train_ts = unique_timestamps[:n_train]
    val_ts = unique_timestamps[n_train : n_train + n_val]
    test_ts = unique_timestamps[n_train + n_val :]

    train_df = df[df[timestamp_col].isin(train_ts)].copy()
    val_df = df[df[timestamp_col].isin(val_ts)].copy()
    test_df = df[df[timestamp_col].isin(test_ts)].copy()

    split_metadata = {
        "total_rows": len(df),
        "total_unique_timestamps": int(total_timestamps),
        "train": {
            "timestamps_count": int(len(train_ts)),
            "start": str(train_ts[0]),
            "end": str(train_ts[-1]),
            "rows": int(len(train_df)),
        },
        "val": {
            "timestamps_count": int(len(val_ts)),
            "start": str(val_ts[0]),
            "end": str(val_ts[-1]),
            "rows": int(len(val_df)),
        },
        "test": {
            "timestamps_count": int(len(test_ts)),
            "start": str(test_ts[0]),
            "end": str(test_ts[-1]),
            "rows": int(len(test_df)),
        },
    }

    return train_df, val_df, test_df, split_metadata


def build_model_pipeline(
    model_type: str,
    numerical_cols: Optional[List[str]] = None,
    categorical_cols: Optional[List[str]] = None,
    random_state: int = 42,
    **model_kwargs: Any,
) -> Pipeline:
    """
    Constructs an end-to-end scikit-learn Pipeline with integrated preprocessing.

    Parameters
    ----------
    model_type : str
        One of 'dummy', 'ridge', 'hist_gbr', 'random_forest'.
    numerical_cols : List[str], optional
    categorical_cols : List[str], optional
    random_state : int, default=42
    **model_kwargs : Any
        Hyperparameters passed to the underlying estimator.

    Returns
    -------
    Pipeline
        Configured scikit-learn pipeline.
    """
    num_cols = numerical_cols or NUMERICAL_FEATURES
    cat_cols = categorical_cols or CATEGORICAL_FEATURES

    # Safe categorical encoder: handle_unknown='ignore' ensures robustness to unseen entities
    cat_encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)

    if model_type == "dummy":
        strategy = model_kwargs.get("strategy", "mean")
        return Pipeline([("model", DummyRegressor(strategy=strategy))])

    elif model_type == "ridge":
        alpha = model_kwargs.get("alpha", 10.0)
        preprocessor = ColumnTransformer(
            transformers=[
                ("num", StandardScaler(), num_cols),
                ("cat", cat_encoder, cat_cols),
            ]
        )
        return Pipeline(
            [
                ("prep", preprocessor),
                ("model", Ridge(alpha=alpha, random_state=random_state)),
            ]
        )

    elif model_type == "hist_gbr":
        max_iter = model_kwargs.get("max_iter", 150)
        max_depth = model_kwargs.get("max_depth", 8)
        preprocessor = ColumnTransformer(
            transformers=[
                ("num", "passthrough", num_cols),
                ("cat", cat_encoder, cat_cols),
            ]
        )
        return Pipeline(
            [
                ("prep", preprocessor),
                (
                    "model",
                    HistGradientBoostingRegressor(
                        max_iter=max_iter,
                        max_depth=max_depth,
                        random_state=random_state,
                    ),
                ),
            ]
        )

    elif model_type == "random_forest":
        n_estimators = model_kwargs.get("n_estimators", 100)
        max_depth = model_kwargs.get("max_depth", 16)
        preprocessor = ColumnTransformer(
            transformers=[
                ("num", "passthrough", num_cols),
                ("cat", cat_encoder, cat_cols),
            ]
        )
        return Pipeline(
            [
                ("prep", preprocessor),
                (
                    "model",
                    RandomForestRegressor(
                        n_estimators=n_estimators,
                        max_depth=max_depth,
                        random_state=random_state,
                        n_jobs=-1,
                    ),
                ),
            ]
        )

    else:
        raise ValueError(f"Unknown model_type '{model_type}'. Choose from 'dummy', 'ridge', 'hist_gbr', 'random_forest'.")


def evaluate_predictions(y_true: pd.Series, y_pred: np.ndarray) -> Dict[str, float]:
    """
    Computes standard regression metrics and residual statistics.
    """
    residuals = y_pred - y_true
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(root_mean_squared_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    mean_residual = float(np.mean(residuals))
    median_abs_err = float(np.median(np.abs(residuals)))

    # Weighted Absolute Percentage Error (WAPE)
    y_sum = float(np.sum(y_true))
    wape = float(np.sum(np.abs(residuals)) / y_sum * 100.0) if y_sum > 0 else float("nan")

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "wape_pct": round(wape, 4),
        "mean_residual": round(mean_residual, 4),
        "median_abs_error": round(median_abs_err, 4),
        "sample_size": int(len(y_true)),
    }


def evaluate_by_slices(
    pipeline: Pipeline,
    df: pd.DataFrame,
    features: List[str],
    target: str = TARGET_COLUMN,
) -> Dict[str, Any]:
    """
    Performs sliced performance evaluations:
    - By Plant ID
    - By Irradiance Regime (Low, Medium, High)
    - By Inverter (SOURCE_KEY)

    Returns nested dictionary of evaluation metrics.
    """
    out_df = df.copy()
    y_true = out_df[target]
    y_pred = pipeline.predict(out_df[features])
    out_df["pred"] = y_pred
    out_df["residual"] = y_pred - y_true  # positive: predicted > actual (underperformance candidate)

    # 1. Overall
    overall_metrics = evaluate_predictions(y_true, y_pred)

    # 2. Plant breakdown
    plant_metrics = {}
    for plant_id, grp in out_df.groupby("PLANT_ID", observed=True):
        plant_metrics[str(plant_id)] = evaluate_predictions(grp[target], grp["pred"].values)

    # 3. Irradiance regime breakdown
    out_df["irr_bin"] = pd.cut(
        out_df["IRRADIATION"],
        bins=IRRADIANCE_BINS,
        labels=IRRADIANCE_BIN_LABELS,
    )
    irradiance_metrics = {}
    for bin_label, grp in out_df.groupby("irr_bin", observed=True):
        if len(grp) > 0:
            irradiance_metrics[str(bin_label)] = evaluate_predictions(grp[target], grp["pred"].values)

    # 4. Inverter breakdown
    inverter_metrics = []
    for (plant_id, source_key), grp in out_df.groupby(["PLANT_ID", "SOURCE_KEY"], observed=True):
        inv_eval = evaluate_predictions(grp[target], grp["pred"].values)
        inv_eval["PLANT_ID"] = str(plant_id)
        inv_eval["SOURCE_KEY"] = str(source_key)
        inverter_metrics.append(inv_eval)

    return {
        "overall": overall_metrics,
        "by_plant": plant_metrics,
        "by_irradiance": irradiance_metrics,
        "by_inverter": inverter_metrics,
    }


def save_model_artifact(
    pipeline: Pipeline,
    filepath: Path | str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Persists trained pipeline and metadata using joblib.
    """
    save_path = Path(filepath)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pipeline": pipeline,
        "metadata": metadata or {},
    }
    joblib.dump(payload, save_path)


def load_model_artifact(filepath: Path | str) -> Tuple[Pipeline, Dict[str, Any]]:
    """
    Loads saved pipeline and associated metadata.
    """
    load_path = Path(filepath)
    if not load_path.exists():
        raise FileNotFoundError(f"Model artifact not found at {load_path}")
    payload = joblib.load(load_path)
    return payload["pipeline"], payload.get("metadata", {})
