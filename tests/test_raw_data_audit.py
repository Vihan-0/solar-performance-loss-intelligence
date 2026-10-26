"""
Milestone 1 Tests: Raw Data Verification
Validates the structural realities and invariants discovered during the audit of the four CSV files.
"""

from pathlib import Path
import pandas as pd
import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


@pytest.fixture(scope="module")
def p1_gen():
    df = pd.read_csv(DATA_DIR / "Plant_1_Generation_Data.csv")
    df["PARSED_DATE_TIME"] = pd.to_datetime(df["DATE_TIME"], format="%d-%m-%Y %H:%M")
    return df


@pytest.fixture(scope="module")
def p1_weather():
    df = pd.read_csv(DATA_DIR / "Plant_1_Weather_Sensor_Data.csv")
    df["PARSED_DATE_TIME"] = pd.to_datetime(df["DATE_TIME"], format="%Y-%m-%d %H:%M:%S")
    return df


@pytest.fixture(scope="module")
def p2_gen():
    df = pd.read_csv(DATA_DIR / "Plant_2_Generation_Data.csv")
    df["PARSED_DATE_TIME"] = pd.to_datetime(df["DATE_TIME"], format="%Y-%m-%d %H:%M:%S")
    return df


@pytest.fixture(scope="module")
def p2_weather():
    df = pd.read_csv(DATA_DIR / "Plant_2_Weather_Sensor_Data.csv")
    df["PARSED_DATE_TIME"] = pd.to_datetime(df["DATE_TIME"], format="%Y-%m-%d %H:%M:%S")
    return df


def test_file_row_counts_and_nulls(p1_gen, p1_weather, p2_gen, p2_weather):
    assert len(p1_gen) == 68778
    assert len(p1_weather) == 3182
    assert len(p2_gen) == 67698
    assert len(p2_weather) == 3259

    # Zero nulls across all files
    assert p1_gen.isnull().sum().sum() == 0
    assert p1_weather.isnull().sum().sum() == 0
    assert p2_gen.isnull().sum().sum() == 0
    assert p2_weather.isnull().sum().sum() == 0


def test_inverter_and_sensor_cardinality(p1_gen, p1_weather, p2_gen, p2_weather):
    # Generation has 22 inverters per plant
    assert p1_gen["SOURCE_KEY"].nunique() == 22
    assert p2_gen["SOURCE_KEY"].nunique() == 22

    # Weather has 1 sensor per plant
    assert p1_weather["SOURCE_KEY"].nunique() == 1
    assert p2_weather["SOURCE_KEY"].nunique() == 1

    # Inverter IDs and Weather sensor IDs do NOT overlap
    assert len(set(p1_gen["SOURCE_KEY"]).intersection(set(p1_weather["SOURCE_KEY"]))) == 0
    assert len(set(p2_gen["SOURCE_KEY"]).intersection(set(p2_weather["SOURCE_KEY"]))) == 0


def test_key_uniqueness_no_duplicates(p1_gen, p1_weather, p2_gen, p2_weather):
    # In generation data, (timestamp, source_key) is unique
    assert not p1_gen.duplicated(subset=["PARSED_DATE_TIME", "SOURCE_KEY"]).any()
    assert not p2_gen.duplicated(subset=["PARSED_DATE_TIME", "SOURCE_KEY"]).any()

    # In weather data, timestamp is unique
    assert not p1_weather.duplicated(subset=["PARSED_DATE_TIME"]).any()
    assert not p2_weather.duplicated(subset=["PARSED_DATE_TIME"]).any()


def test_join_integrity_no_row_multiplication(p1_gen, p1_weather, p2_gen, p2_weather):
    # Plant 1 Left Join
    p1_merged = p1_gen.merge(
        p1_weather.drop(columns=["SOURCE_KEY"]),
        on=["PARSED_DATE_TIME", "PLANT_ID"],
        how="left",
    )
    assert len(p1_merged) == len(p1_gen), "Join multiplied or lost rows in Plant 1 left join"

    # Plant 2 Left Join
    p2_merged = p2_gen.merge(
        p2_weather.drop(columns=["SOURCE_KEY"]),
        on=["PARSED_DATE_TIME", "PLANT_ID"],
        how="left",
    )
    assert len(p2_merged) == len(p2_gen), "Join multiplied or lost rows in Plant 2 left join"


def test_no_ground_truth_fault_labels(p1_gen, p1_weather, p2_gen, p2_weather):
    # Confirm no explicit error/fault/maintenance columns exist
    prohibited_substrings = ["fault", "alarm", "error", "status", "event", "maint", "label", "target"]
    for name, df in [("P1 Gen", p1_gen), ("P1 Weather", p1_weather), ("P2 Gen", p2_gen), ("P2 Weather", p2_weather)]:
        matching_cols = [c for c in df.columns if any(sub in c.lower() for sub in prohibited_substrings)]
        assert len(matching_cols) == 0, f"Found unexpected label column in {name}: {matching_cols}"
