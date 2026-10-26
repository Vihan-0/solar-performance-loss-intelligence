"""
Data Loading, Parsing, Validation, and Merging Module
Project: Adaptive Solar Performance & Loss Intelligence

This module provides deterministic, leak-free functions to:
1. Load raw generation and weather datasets for Plant 1 and Plant 2.
2. Parse non-standard datetime formats (Plant 1 day-first vs ISO formats).
3. Validate entity cardinality and uniqueness of primary keys.
4. Merge generation and weather tables using strict left-joins with many-to-one validation.
5. Track rows with missing weather data without fabricating power measurements.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple, Union
import numpy as np
import pandas as pd

# Default paths
DEFAULT_RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# Plant metadata configuration
PLANT_CONFIGS = {
    1: {
        "plant_id": 4135001,
        "gen_filename": "Plant_1_Generation_Data.csv",
        "gen_date_format": "%d-%m-%Y %H:%M",
        "weather_filename": "Plant_1_Weather_Sensor_Data.csv",
        "weather_date_format": "%Y-%m-%d %H:%M:%S",
    },
    2: {
        "plant_id": 4136001,
        "gen_filename": "Plant_2_Generation_Data.csv",
        "gen_date_format": "%Y-%m-%d %H:%M:%S",
        "weather_filename": "Plant_2_Weather_Sensor_Data.csv",
        "weather_date_format": "%Y-%m-%d %H:%M:%S",
    },
}

REQUIRED_GEN_COLUMNS = [
    "DATE_TIME",
    "PLANT_ID",
    "SOURCE_KEY",
    "DC_POWER",
    "AC_POWER",
    "DAILY_YIELD",
    "TOTAL_YIELD",
]

REQUIRED_WEATHER_COLUMNS = [
    "DATE_TIME",
    "PLANT_ID",
    "SOURCE_KEY",
    "AMBIENT_TEMPERATURE",
    "MODULE_TEMPERATURE",
    "IRRADIATION",
]


def load_raw_generation_data(
    plant_id: int,
    raw_dir: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """
    Loads and standardizes raw generation data for a specified plant.

    Parameters
    ----------
    plant_id : int
        Plant identifier (1 or 2).
    raw_dir : Path or str, optional
        Directory containing raw CSV files.

    Returns
    -------
    pd.DataFrame
        Generation dataframe with standardized 'TIMESTAMP' column.
    """
    if plant_id not in PLANT_CONFIGS:
        raise ValueError(f"Invalid plant_id {plant_id}. Expected 1 or 2.")

    raw_path = Path(raw_dir) if raw_dir else DEFAULT_RAW_DIR
    cfg = PLANT_CONFIGS[plant_id]
    file_path = raw_path / cfg["gen_filename"]

    if not file_path.exists():
        raise FileNotFoundError(f"Generation file not found: {file_path}")

    df = pd.read_csv(file_path)

    # Validate schema
    missing_cols = set(REQUIRED_GEN_COLUMNS) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Generation file missing required columns: {missing_cols}")

    # Standardize timestamp parsing
    df["TIMESTAMP"] = pd.to_datetime(df["DATE_TIME"], format=cfg["gen_date_format"])

    # Verify expected plant ID
    unique_plants = df["PLANT_ID"].unique()
    if len(unique_plants) != 1 or unique_plants[0] != cfg["plant_id"]:
        raise ValueError(f"Unexpected PLANT_ID {unique_plants} in {cfg['gen_filename']}. Expected {cfg['plant_id']}")

    # Validate primary key uniqueness: (TIMESTAMP, SOURCE_KEY)
    duplicates = df.duplicated(subset=["TIMESTAMP", "SOURCE_KEY"]).sum()
    if duplicates > 0:
        raise ValueError(f"Found {duplicates} duplicate (TIMESTAMP, SOURCE_KEY) records in {cfg['gen_filename']}.")

    # Establish canonical target in kW while preserving raw AC_POWER in Watts
    df["AC_POWER_KW"] = df["AC_POWER"] / 1000.0

    return df


def load_raw_weather_data(
    plant_id: int,
    raw_dir: Optional[Union[Path, str]] = None,
) -> pd.DataFrame:
    """
    Loads and standardizes raw weather sensor data for a specified plant.

    Parameters
    ----------
    plant_id : int
        Plant identifier (1 or 2).
    raw_dir : Path or str, optional
        Directory containing raw CSV files.

    Returns
    -------
    pd.DataFrame
        Weather dataframe with standardized 'TIMESTAMP' and renamed 'WEATHER_SENSOR_KEY'.
    """
    if plant_id not in PLANT_CONFIGS:
        raise ValueError(f"Invalid plant_id {plant_id}. Expected 1 or 2.")

    raw_path = Path(raw_dir) if raw_dir else DEFAULT_RAW_DIR
    cfg = PLANT_CONFIGS[plant_id]
    file_path = raw_path / cfg["weather_filename"]

    if not file_path.exists():
        raise FileNotFoundError(f"Weather file not found: {file_path}")

    df = pd.read_csv(file_path)

    # Validate schema
    missing_cols = set(REQUIRED_WEATHER_COLUMNS) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Weather file missing required columns: {missing_cols}")

    # Standardize timestamp parsing
    df["TIMESTAMP"] = pd.to_datetime(df["DATE_TIME"], format=cfg["weather_date_format"])

    # Verify expected plant ID
    unique_plants = df["PLANT_ID"].unique()
    if len(unique_plants) != 1 or unique_plants[0] != cfg["plant_id"]:
        raise ValueError(f"Unexpected PLANT_ID {unique_plants} in {cfg['weather_filename']}. Expected {cfg['plant_id']}")

    # Rename weather SOURCE_KEY to avoid collision with inverter SOURCE_KEY
    df = df.rename(columns={"SOURCE_KEY": "WEATHER_SENSOR_KEY"})

    # Validate primary key uniqueness: (TIMESTAMP, PLANT_ID)
    duplicates = df.duplicated(subset=["TIMESTAMP", "PLANT_ID"]).sum()
    if duplicates > 0:
        raise ValueError(f"Found {duplicates} duplicate (TIMESTAMP, PLANT_ID) records in {cfg['weather_filename']}.")

    return df


def merge_plant_data(
    gen_df: pd.DataFrame,
    weather_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Performs a strict left join between generation records and weather observations.

    Guarantees:
    - Many-to-one validation (multiple inverters at a timestamp to one weather observation).
    - Left join preserves every generation record without discarding rows.
    - Zero row multiplication: output row count strictly equals input generation row count.
    - Tracks matching weather via boolean 'has_weather'.

    Parameters
    ----------
    gen_df : pd.DataFrame
        Standardized generation dataframe.
    weather_df : pd.DataFrame
        Standardized weather dataframe.

    Returns
    -------
    pd.DataFrame
        Merged dataframe preserving all generation records.
    """
    pre_join_count = len(gen_df)

    # Weather columns to bring into generation table
    weather_cols_to_merge = [
        "TIMESTAMP",
        "PLANT_ID",
        "WEATHER_SENSOR_KEY",
        "AMBIENT_TEMPERATURE",
        "MODULE_TEMPERATURE",
        "IRRADIATION",
    ]

    weather_subset = weather_df[weather_cols_to_merge].copy()

    # Many-to-one left merge
    merged_df = pd.merge(
        gen_df,
        weather_subset,
        on=["TIMESTAMP", "PLANT_ID"],
        how="left",
        validate="many_to_one",
    )

    # Strict assertion against row multiplication or loss
    if len(merged_df) != pre_join_count:
        raise AssertionError(
            f"Merge violation: pre-join count ({pre_join_count}) != post-join count ({len(merged_df)})"
        )

    # Track presence of matching weather observations
    merged_df["has_weather"] = merged_df["IRRADIATION"].notna()

    # Re-order columns cleanly
    preferred_order = [
        "TIMESTAMP",
        "DATE_TIME",
        "PLANT_ID",
        "SOURCE_KEY",
        "DC_POWER",
        "AC_POWER",
        "AC_POWER_KW",
        "DAILY_YIELD",
        "TOTAL_YIELD",
        "WEATHER_SENSOR_KEY",
        "AMBIENT_TEMPERATURE",
        "MODULE_TEMPERATURE",
        "IRRADIATION",
        "has_weather",
    ]
    remaining_cols = [c for c in merged_df.columns if c not in preferred_order]
    merged_df = merged_df[preferred_order + remaining_cols]

    return merged_df


def inspect_data_quality(merged_df: pd.DataFrame, plant_name: str = "Plant") -> Dict[str, Union[int, float, dict]]:
    """
    Audits data quality indicators of a merged dataset.

    Returns summary metrics including:
    - Row count
    - Missing weather count and percentage
    - Inverter count
    - Timestamp range
    - Missing power records
    """
    total_rows = len(merged_df)
    missing_weather_count = int((~merged_df["has_weather"]).sum())
    missing_weather_pct = (missing_weather_count / total_rows * 100.0) if total_rows > 0 else 0.0

    inverter_counts = merged_df.groupby("SOURCE_KEY")["TIMESTAMP"].count().to_dict()

    quality_summary = {
        "plant_name": plant_name,
        "total_rows": total_rows,
        "unique_inverters": len(inverter_counts),
        "min_inverter_records": min(inverter_counts.values()) if inverter_counts else 0,
        "max_inverter_records": max(inverter_counts.values()) if inverter_counts else 0,
        "timestamp_min": str(merged_df["TIMESTAMP"].min()),
        "timestamp_max": str(merged_df["TIMESTAMP"].max()),
        "missing_weather_rows": missing_weather_count,
        "missing_weather_pct": missing_weather_pct,
        "null_ac_power_count": int(merged_df["AC_POWER"].isna().sum()),
        "null_ac_power_kw_count": int(merged_df["AC_POWER_KW"].isna().sum()) if "AC_POWER_KW" in merged_df else 0,
        "null_dc_power_count": int(merged_df["DC_POWER"].isna().sum()),
        "negative_ac_power_count": int((merged_df["AC_POWER"] < 0).sum()),
        "negative_irradiation_count": int((merged_df["IRRADIATION"] < 0).sum()),
    }

    return quality_summary


def load_and_merge_datasets(
    raw_dir: Optional[Union[Path, str]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Loads and merges both Plant 1 and Plant 2 datasets, plus a combined pool.

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
        (p1_merged, p2_merged, combined_merged)
    """
    # Plant 1
    p1_gen = load_raw_generation_data(plant_id=1, raw_dir=raw_dir)
    p1_weather = load_raw_weather_data(plant_id=1, raw_dir=raw_dir)
    p1_merged = merge_plant_data(p1_gen, p1_weather)

    # Plant 2
    p2_gen = load_raw_generation_data(plant_id=2, raw_dir=raw_dir)
    p2_weather = load_raw_weather_data(plant_id=2, raw_dir=raw_dir)
    p2_merged = merge_plant_data(p2_gen, p2_weather)

    # Combined pool
    combined_merged = pd.concat([p1_merged, p2_merged], ignore_index=True)

    return p1_merged, p2_merged, combined_merged
