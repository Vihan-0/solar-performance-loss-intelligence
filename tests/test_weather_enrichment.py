"""
Automated Tests for External Weather Acquisition and Alignment
Adaptive Solar Performance & Loss Intelligence
Milestone 5 - Phase 3 Tests
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from src.weather import fetch_open_meteo_weather, align_external_weather


def test_weather_cache_loading_and_schema():
    """Validates that external weather can be loaded and conforms to standardized schema."""
    df, meta = fetch_open_meteo_weather(force_refresh=False)

    assert len(df) == 816
    expected_cols = [
        "time",
        "ext_temp_c",
        "ext_rh_pct",
        "ext_precip_mm",
        "ext_cloud_cover_pct",
        "ext_wind_speed_kmh",
        "ext_wind_speed_ms",
        "ext_radiation_w_m2",
        "ext_radiation_kw_m2",
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing expected weather column {col}"

    assert meta["latitude"] == 14.35
    assert meta["longitude"] == 77.49
    assert meta["timezone"] == "Asia/Kolkata"


def test_weather_unit_standardization():
    """Validates standardized weather physical units."""
    df, _ = fetch_open_meteo_weather(force_refresh=False)

    # Radiation conversion W/m² to kW/m²
    assert np.allclose(df["ext_radiation_kw_m2"], df["ext_radiation_w_m2"] / 1000.0, atol=1e-4)

    # Wind speed conversion km/h to m/s
    assert np.allclose(df["ext_wind_speed_ms"], df["ext_wind_speed_kmh"] / 3.6, atol=1e-3)

    # Physical ranges
    assert 15.0 <= df["ext_temp_c"].mean() <= 45.0  # Summer in Karnataka
    assert 0.0 <= df["ext_rh_pct"].min() <= 100.0
    assert 0.0 <= df["ext_cloud_cover_pct"].min() <= 100.0
    assert df["ext_radiation_kw_m2"].min() >= 0.0


def test_alignment_row_preservation_and_no_multiplication():
    """
    Validates that alignment preserves exact generation row counts and
    maps 15-minute intervals to top-of-hour reference without fabrication.
    """
    sample_gen = pd.DataFrame(
        {
            "TIMESTAMP": pd.date_range("2020-05-15 06:00", "2020-05-15 08:45", freq="15min"),
            "PLANT_ID": 4135001,
            "SOURCE_KEY": "INV_01",
            "AC_POWER_KW": 0.8,
        }
    )
    pre_len = len(sample_gen)

    weather_df, _ = fetch_open_meteo_weather(force_refresh=False)
    aligned_df, report = align_external_weather(sample_gen, weather_df, timestamp_col="TIMESTAMP")

    assert len(aligned_df) == pre_len
    assert report["unmatched_rows"] == 0
    assert report["match_percentage"] == 100.0
    assert "has_external_weather" in aligned_df.columns
    assert aligned_df["has_external_weather"].all()

    # Verify that 06:00, 06:15, 06:30, 06:45 all map to 06:00 weather
    hour_6_vals = aligned_df[aligned_df["TIMESTAMP"].dt.hour == 6]["ext_temp_c"]
    assert hour_6_vals.nunique() == 1
