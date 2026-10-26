"""
Milestone 4 Tests: Anomaly Detection and Energy Shortfall Verification
Validates normal generation, persistent drops, isolated dips, missing timestamp gaps,
nighttime zeroing, and energy shortfall calculations.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.detect import (
    estimate_inverter_capacities,
    compute_cohort_expected_power,
    calculate_residuals,
    calibrate_thresholds,
    apply_persistence_filter,
)
from src.loss import (
    compute_interval_shortfall,
    aggregate_inverter_loss_summary,
    aggregate_plant_loss_summary,
)


@pytest.fixture
def synthetic_timeline():
    # 10 consecutive 15-minute intervals
    timestamps = pd.date_range("2020-06-15 10:00:00", periods=10, freq="15min")
    df = pd.DataFrame(
        {
            "TIMESTAMP": timestamps,
            "PLANT_ID": 4135001,
            "SOURCE_KEY": "INV_TEST_A",
            "IRRADIATION": 0.8,
            "AC_POWER": 1000.0,
            "expected_power": 1000.0,
            "is_daylight": True,
        }
    )
    return df


def test_normal_generation_zero_shortfall(synthetic_timeline):
    # Under normal generation (expected == actual), residual is 0 and shortfall is 0
    res, rel = calculate_residuals(synthetic_timeline["AC_POWER"], synthetic_timeline["expected_power"])
    assert (res == 0.0).all()
    assert (rel == 0.0).all()

    shortfall = compute_interval_shortfall(
        synthetic_timeline["AC_POWER"], synthetic_timeline["expected_power"], synthetic_timeline["is_daylight"]
    )
    assert (shortfall == 0.0).all()


def test_isolated_dip_rejected_by_persistence_filter(synthetic_timeline):
    df = synthetic_timeline.copy()
    # Inject isolated 1-interval dip at index 4 (15 minutes only)
    df.loc[4, "AC_POWER"] = 100.0

    # Residuals
    res, _ = calculate_residuals(df["AC_POWER"], df["expected_power"])
    df["candidate"] = res > 100.0  # Threshold of 100 kW

    # Assert candidate is True only at index 4
    assert df["candidate"].sum() == 1

    # Apply persistence filter (requires >= 3 consecutive)
    df["is_persistent"] = apply_persistence_filter(df, "candidate", min_consecutive=3)

    # Isolated dip MUST NOT trigger persistent anomaly
    assert not df["is_persistent"].any(), "Isolated 1-interval dip triggered an anomaly alert!"


def test_persistent_drop_triggers_anomaly(synthetic_timeline):
    df = synthetic_timeline.copy()
    # Inject 4 consecutive intervals of severe underperformance at indices 3, 4, 5, 6 (60 mins)
    df.loc[3:6, "AC_POWER"] = 200.0

    res, _ = calculate_residuals(df["AC_POWER"], df["expected_power"])
    df["candidate"] = res > 100.0

    # Apply persistence filter (>= 3 consecutive)
    df["is_persistent"] = apply_persistence_filter(df, "candidate", min_consecutive=3)

    # Must flag the persistent episode
    assert df["is_persistent"].iloc[3:7].all(), "Persistent 4-interval drop was not detected!"
    assert not df["is_persistent"].iloc[0:3].any()
    assert not df["is_persistent"].iloc[7:].any()


def test_gap_bridging_prevention():
    # Construct timeline with a 45-minute missing gap between interval 1 and 2
    ts = [
        pd.Timestamp("2020-06-15 10:00:00"),
        pd.Timestamp("2020-06-15 10:15:00"),
        # Gap: 10:30 and 10:45 missing!
        pd.Timestamp("2020-06-15 11:00:00"),
        pd.Timestamp("2020-06-15 11:15:00"),
    ]
    df = pd.DataFrame(
        {
            "TIMESTAMP": ts,
            "PLANT_ID": 4135001,
            "SOURCE_KEY": "INV_TEST_GAP",
            "candidate": [True, True, True, True],  # All candidate underperformance
        }
    )

    # If gaps are bridged, 4 candidate points would trigger >= 3 persistence!
    # But because 10:15 to 11:00 is 45 mins (>15m), the streak MUST reset!
    df["is_persistent"] = apply_persistence_filter(df, "candidate", min_consecutive=3, max_interval_minutes=15.0)

    # Neither the pre-gap (2 intervals) nor post-gap (2 intervals) reached 3 consecutive!
    assert not df["is_persistent"].any(), "Persistence filter bridged across a 45-minute missing gap!"


def test_nighttime_zero_shortfall(synthetic_timeline):
    df = synthetic_timeline.copy()
    df["is_daylight"] = False
    df["expected_power"] = 500.0  # Erroneous prediction during night
    df["AC_POWER"] = 0.0

    shortfall = compute_interval_shortfall(df["AC_POWER"], df["expected_power"], is_daylight=df["is_daylight"])
    assert (shortfall == 0.0).all(), "Shortfall was calculated during nighttime!"


def test_energy_shortfall_calculation():
    actual = pd.Series([800.0, 1000.0, 1200.0])  # Overperforming on last interval
    expected = pd.Series([1000.0, 1000.0, 1000.0])

    shortfall = compute_interval_shortfall(actual, expected, interval_hours=0.25)

    # Interval 0: (1000 - 800) * 0.25 = 50 kWh
    assert np.isclose(shortfall.iloc[0], 50.0)
    # Interval 1: (1000 - 1000) * 0.25 = 0 kWh
    assert np.isclose(shortfall.iloc[1], 0.0)
    # Interval 2: Overperformance -> max(0, -200) * 0.25 = 0 kWh
    assert np.isclose(shortfall.iloc[2], 0.0)


def test_peer_cohort_capacity_normalization():
    # 2 inverters with different subarray capacities: Inverter A (1000 kW), Inverter B (500 kW)
    capacities = {(4135001, "INV_A"): 1000.0, (4135001, "INV_B"): 500.0}

    df = pd.DataFrame(
        {
            "TIMESTAMP": [pd.Timestamp("2020-06-15 12:00:00")] * 2,
            "PLANT_ID": [4135001, 4135001],
            "SOURCE_KEY": ["INV_A", "INV_B"],
            # Both operating at 100% capacity: INV_A=1000 kW, INV_B=500 kW
            "AC_POWER": [1000.0, 500.0],
        }
    )

    cohort_expected = compute_cohort_expected_power(df, capacities)
    # Expected power should match each inverter's own capacity: 1000 kW and 500 kW
    assert np.isclose(cohort_expected.iloc[0], 1000.0)
    assert np.isclose(cohort_expected.iloc[1], 500.0)

    # Residuals should be 0 for both!
    res_a = cohort_expected.iloc[0] - df["AC_POWER"].iloc[0]
    res_b = cohort_expected.iloc[1] - df["AC_POWER"].iloc[1]
    assert np.isclose(res_a, 0.0)
    assert np.isclose(res_b, 0.0)
