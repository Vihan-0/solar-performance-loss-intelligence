"""
Unit Tests for Residential Solar Intelligence Module
Project: Adaptive Solar Performance & Loss Intelligence

Tests dynamic discovery, PII stripping, unit conversions, daily energy arithmetic,
sampling interval and gap detection, and graceful missing-file behavior.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.residential import (
    find_havells_export,
    sanitize_dataframe,
    load_and_preprocess_havells,
    SENSITIVE_IDENTIFIERS,
)


def test_missing_file_graceful_handling(tmp_path):
    """Verifies system returns structured unavailable state when no export exists."""
    empty_dir = tmp_path / "empty_raw"
    empty_dir.mkdir()

    result = load_and_preprocess_havells(file_path=empty_dir / "nonexistent.csv")
    assert result["is_available"] is False
    assert "not found" in result["message"].lower() or "error" in result["message"].lower()
    assert "instructions" in result


def test_dynamic_file_discovery_empty(tmp_path):
    """Verifies discovery returns None when search directory has no CSVs."""
    empty_dir = tmp_path / "empty_dir"
    empty_dir.mkdir()
    discovered = find_havells_export(search_dir=empty_dir)
    assert discovered is None


def test_dynamic_file_discovery_success(tmp_path):
    """Verifies discovery finds CSV without hardcoded filename."""
    test_dir = tmp_path / "test_raw"
    test_dir.mkdir()
    dummy_csv = test_dir / "RandomName_Export_1234.csv"
    dummy_csv.write_text("col1,col2\n1,2\n")

    discovered = find_havells_export(search_dir=test_dir)
    assert discovered == dummy_csv


def test_pii_sanitization():
    """Verifies all serial numbers and hardware identifiers are stripped."""
    raw_df = pd.DataFrame(
        {
            "System Time": ["2026-10-20 06:00:00"],
            "SN": ["SENSITIVE_SERIAL_123"],
            "Device SN": ["SENSITIVE_DEV_456"],
            "PCU_ID": ["PCU_SECRET_789"],
            "Slave Address": [1],
            "Device Name": ["Secret_Rooftop_Inverter"],
            "Parent Device ": ["Parent_Gateway_000"],
            "Total AC Output Power(W)": [2500],
            "Rated Power(W)": [5000],
        }
    )
    sanitized = sanitize_dataframe(raw_df)
    for col in SENSITIVE_IDENTIFIERS:
        clean_col = col.strip()
        assert clean_col not in sanitized.columns
        assert col not in sanitized.columns
    assert "Total AC Output Power(W)" in sanitized.columns


def test_unit_conversion_watts_to_kw(tmp_path):
    """Verifies AC power is accurately converted from Watts to kW."""
    csv_file = tmp_path / "synthetic_telemetry.csv"
    csv_file.write_text(
        "System Time,Total AC Output Power(W),Rated Power(W),PV Total Power(W)\n"
        "2026-10-20 12:00:00,3580,5000,3650\n"
        "2026-10-20 12:05:00,3400,5000,3480\n"
    )
    result = load_and_preprocess_havells(file_path=csv_file)
    assert result["is_available"] is True
    assert result["rated_power_kw"] == 5.0
    assert result["peak_ac_power_w"] == 3580.0
    assert result["peak_ac_power_kw"] == pytest.approx(3.58, rel=1e-3)


def test_daily_energy_calculation_no_counter_multiplication(tmp_path):
    """
    CRITICAL TEST: Verifies that Daily Production (Active)(kWh) is treated as a
    cumulative daily counter that resets, and is NOT summed across 5-minute intervals.
    """
    csv_file = tmp_path / "energy_counter_test.csv"
    # Create two days of 5-minute readings where the counter increments
    rows = [
        "System Time,Total AC Output Power(W),Daily Production (Active)(kWh),Rated Power(W)",
        # Day 1: counter starts at 0.0, reaches 20.0
        "2026-10-20 08:00:00,1000,1.0,5000",
        "2026-10-20 12:00:00,3000,12.0,5000",
        "2026-10-20 17:00:00,500,20.0,5000",
        # Day 2: counter resets to 0.0, reaches 15.0
        "2026-10-21 08:00:00,800,0.8,5000",
        "2026-10-21 12:00:00,2500,10.0,5000",
        "2026-10-21 17:00:00,400,15.0,5000",
    ]
    csv_file.write_text("\n".join(rows))

    result = load_and_preprocess_havells(file_path=csv_file)
    assert result["is_available"] is True

    daily_df = result["daily_summary_df"]
    assert len(daily_df) == 2

    # Day 1 daily energy must be 20.0, NOT 1.0 + 12.0 + 20.0 = 33.0
    day1_row = daily_df.iloc[0]
    assert day1_row["daily_energy_kwh"] == 20.0

    # Day 2 daily energy must be 15.0
    day2_row = daily_df.iloc[1]
    assert day2_row["daily_energy_kwh"] == 15.0

    # Total energy must be 20.0 + 15.0 = 35.0 kWh
    assert result["total_energy_kwh"] == 35.0


def test_sampling_interval_and_gap_detection(tmp_path):
    """Verifies ~5m sampling interval and overnight gap identification."""
    csv_file = tmp_path / "gap_test.csv"
    rows = [
        "System Time,Total AC Output Power(W),Rated Power(W)",
        # Day 1 evening
        "2026-10-20 17:55:00,50,5000",
        "2026-10-20 18:00:00,0,5000",
        # Overnight shutdown (12h gap)
        "2026-10-21 06:00:00,0,5000",
        "2026-10-21 06:05:00,100,5000",
    ]
    csv_file.write_text("\n".join(rows))

    result = load_and_preprocess_havells(file_path=csv_file)
    assert result["is_available"] is True
    assert result["typical_cadence_min"] == 5.0
    assert len(result["large_gaps"]) == 1

    gap = result["large_gaps"][0]
    assert gap["duration_hours"] == 12.0
    assert gap["is_night"] is True
    assert result["night_gaps_count"] == 1
    assert result["daytime_gaps_count"] == 0


def test_real_havells_file_if_present():
    """If real Havells export exists in data/home_havells/raw/, run end-to-end audit."""
    real_path = find_havells_export()
    if real_path is None:
        pytest.skip("No local Havells file present in repository.")

    result = load_and_preprocess_havells(real_path)
    assert result["is_available"] is True
    assert result["total_rows"] == 997
    assert result["valid_readings"] == 997
    assert result["duplicate_timestamps"] == 0
    assert result["total_nulls"] == 0
    assert result["peak_ac_power_kw"] == pytest.approx(3.58, rel=1e-2)
    assert result["rated_power_kw"] == 5.0
    assert result["days_covered"] == 7
    assert result["total_energy_kwh"] == pytest.approx(134.94, rel=1e-2)
    assert result["night_gaps_count"] == 6
    assert result["daytime_gaps_count"] == 0
