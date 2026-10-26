"""
Milestone 2 Tests: Data Pipeline & Feature Engineering Verification
Validates timestamp parsing, join integrity, weather tracking, leakage prevention,
and determinism.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.data import (
    load_raw_generation_data,
    load_raw_weather_data,
    merge_plant_data,
    inspect_data_quality,
)
from src.features import (
    engineer_features,
    prepare_model_ready_dataset,
    FORBIDDEN_LEAKAGE_COLUMNS,
    APPROVED_FEATURE_COLUMNS,
    TARGET_COLUMN,
)


@pytest.fixture(scope="module")
def p1_gen():
    return load_raw_generation_data(plant_id=1)


@pytest.fixture(scope="module")
def p1_weather():
    return load_raw_weather_data(plant_id=1)


@pytest.fixture(scope="module")
def p2_gen():
    return load_raw_generation_data(plant_id=2)


@pytest.fixture(scope="module")
def p2_weather():
    return load_raw_weather_data(plant_id=2)


@pytest.fixture(scope="module")
def p1_merged(p1_gen, p1_weather):
    return merge_plant_data(p1_gen, p1_weather)


@pytest.fixture(scope="module")
def p2_merged(p2_gen, p2_weather):
    return merge_plant_data(p2_gen, p2_weather)


def test_timestamp_parsing_and_types(p1_gen, p1_weather, p2_gen, p2_weather):
    # Standardized TIMESTAMP column must be datetime64
    for df in [p1_gen, p1_weather, p2_gen, p2_weather]:
        assert "TIMESTAMP" in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df["TIMESTAMP"])

    # Plant 1 day-first verification: First timestamp should be May 15, 2020 at 00:00
    assert p1_gen["TIMESTAMP"].min() == pd.Timestamp("2020-05-15 00:00:00")
    assert p1_weather["TIMESTAMP"].min() == pd.Timestamp("2020-05-15 00:00:00")
    assert p2_gen["TIMESTAMP"].min() == pd.Timestamp("2020-05-15 00:00:00")
    assert p2_weather["TIMESTAMP"].min() == pd.Timestamp("2020-05-15 00:00:00")


def test_row_count_preservation_and_no_multiplication(p1_gen, p1_merged, p2_gen, p2_merged):
    # Left join must strictly preserve every generation record
    assert len(p1_merged) == len(p1_gen) == 68778
    assert len(p2_merged) == len(p2_gen) == 67698

    # No duplicate keys created
    assert not p1_merged.duplicated(subset=["TIMESTAMP", "SOURCE_KEY"]).any()
    assert not p2_merged.duplicated(subset=["TIMESTAMP", "SOURCE_KEY"]).any()


def test_weather_sensor_key_no_collision(p1_merged, p2_merged):
    # Ensure weather sensor key was renamed to avoid masking inverter SOURCE_KEY
    assert "WEATHER_SENSOR_KEY" in p1_merged.columns
    assert "WEATHER_SENSOR_KEY" in p2_merged.columns
    assert p1_merged["SOURCE_KEY"].nunique() == 22
    assert p2_merged["SOURCE_KEY"].nunique() == 22


def test_missing_weather_tracking(p1_merged, p2_merged):
    # Plant 1 has exactly 4 generation records lacking weather data
    missing_p1 = p1_merged[~p1_merged["has_weather"]]
    assert len(missing_p1) == 4
    # Verify they all belong to the June 3, 2020 14:00:00 outage
    assert (missing_p1["TIMESTAMP"] == pd.Timestamp("2020-06-03 14:00:00")).all()

    # Plant 2 has 0 missing weather records
    missing_p2 = p2_merged[~p2_merged["has_weather"]]
    assert len(missing_p2) == 0


def test_feature_engineering_integrity(p1_merged):
    featured = engineer_features(p1_merged)

    # Check cyclical ranges [-1.0, 1.0]
    for col in ["sin_time_of_day", "cos_time_of_day", "sin_day_of_year", "cos_day_of_year"]:
        assert col in featured.columns
        assert (featured[col] >= -1.0 - 1e-6).all()
        assert (featured[col] <= 1.0 + 1e-6).all()

    # Verify temp diff logic
    valid_mask = featured["has_weather"]
    diff = featured.loc[valid_mask, "MODULE_TEMPERATURE"] - featured.loc[valid_mask, "AMBIENT_TEMPERATURE"]
    np.testing.assert_allclose(featured.loc[valid_mask, "TEMP_DIFF"], diff)


def test_target_leakage_prevention(p1_merged):
    featured = engineer_features(p1_merged)
    model_df, feature_cols, target_col = prepare_model_ready_dataset(
        featured, daylight_only=True, drop_missing_weather=True
    )

    # Canonical Target is AC_POWER_KW
    assert target_col == TARGET_COLUMN == "AC_POWER_KW"

    # Absolute prohibition: No leakage features in feature set X
    for forbidden in FORBIDDEN_LEAKAGE_COLUMNS:
        assert forbidden not in feature_cols, f"Forbidden leakage column '{forbidden}' found in feature_cols!"

    # Verify that the 4 missing-weather records in Plant 1 were dropped from model-ready data
    assert (model_df["TIMESTAMP"] == pd.Timestamp("2020-06-03 14:00:00")).sum() == 0

    # Verify daylight condition: all irradiance > 0
    assert (model_df["IRRADIATION"] > 0).all()
    assert (model_df["is_daylight"]).all()


def test_pipeline_determinism(p1_merged):
    featured_1 = engineer_features(p1_merged)
    featured_2 = engineer_features(p1_merged)

    pd.testing.assert_frame_equal(featured_1, featured_2)


def test_processed_artifacts_exist_and_load():
    processed_dir = Path(__file__).resolve().parent.parent / "data" / "processed"
    expected_files = [
        "plant_1_merged.parquet",
        "plant_2_merged.parquet",
        "combined_merged.parquet",
        "plant_1_model_ready.parquet",
        "plant_2_model_ready.parquet",
        "combined_model_ready.parquet",
    ]
    for f in expected_files:
        p = processed_dir / f
        assert p.exists(), f"Processed artifact {f} is missing"
        df = pd.read_parquet(p)
        assert len(df) > 0, f"Processed artifact {f} is empty"
