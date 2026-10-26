"""
Automated Tests for Unit Conversions & Physical Energy Arithmetic
Adaptive Solar Performance & Loss Intelligence
Milestone 5 - Phase 1 Tests
"""

import numpy as np
import pandas as pd
import pytest
from src.data import load_raw_generation_data
from src.loss import compute_interval_shortfall, aggregate_inverter_loss_summary


def test_canonical_ac_power_kw_conversion():
    """Validates that AC_POWER_KW is strictly AC_POWER / 1000.0."""
    p1 = load_raw_generation_data(plant_id=1)
    p2 = load_raw_generation_data(plant_id=2)

    assert "AC_POWER_KW" in p1.columns
    assert "AC_POWER_KW" in p2.columns
    assert np.allclose(p1["AC_POWER_KW"], p1["AC_POWER"] / 1000.0, equal_nan=True)
    assert np.allclose(p2["AC_POWER_KW"], p2["AC_POWER"] / 1000.0, equal_nan=True)


def test_physical_inverter_and_plant_bounds():
    """
    Validates physical plausibility against hardware specs:
    - Growatt MIC 1500TL-X rated at 1500 W max AC (1.5 kW)
    - Total plant peak AC ~ 29.15 kW (<= 33 kW rated)
    """
    p1 = load_raw_generation_data(plant_id=1)
    p2 = load_raw_generation_data(plant_id=2)

    # Inverter peak AC power in kW
    assert p1["AC_POWER_KW"].max() <= 1.50, f"Plant 1 inverter peak {p1['AC_POWER_KW'].max()} exceeds 1.5 kW rating"
    assert p2["AC_POWER_KW"].max() <= 1.50, f"Plant 2 inverter peak {p2['AC_POWER_KW'].max()} exceeds 1.5 kW rating"
    assert p1["AC_POWER_KW"].min() >= 0.0
    assert p2["AC_POWER_KW"].min() >= 0.0

    # Plant-level concurrent peak
    p1_plant_peak_kw = p1.groupby("TIMESTAMP")["AC_POWER_KW"].sum().max()
    p2_plant_peak_kw = p2.groupby("TIMESTAMP")["AC_POWER_KW"].sum().max()

    assert 28.0 <= p1_plant_peak_kw <= 32.0, f"Plant 1 peak {p1_plant_peak_kw} kW deviates from literature (~29.15 kW)"
    assert 24.0 <= p2_plant_peak_kw <= 30.0, f"Plant 2 peak {p2_plant_peak_kw} kW deviates from literature (~26 kW)"


def test_energy_arithmetic_kwh():
    """
    Validates that energy shortfall arithmetic uses power in kW and time in hours:
    energy_kWh = power_kW * interval_hours.
    """
    # 1.2 kW expected, 0.4 kW actual for 15 minutes (0.25 h)
    expected_kw = pd.Series([1.2, 1.0, 0.5])
    actual_kw = pd.Series([0.4, 1.0, 0.8])
    is_daylight = pd.Series([True, True, True])

    shortfall_kwh = compute_interval_shortfall(
        actual=actual_kw,
        expected=expected_kw,
        is_daylight=is_daylight,
        interval_hours=0.25,
    )

    # Interval 0: (1.2 - 0.4) * 0.25 = 0.8 * 0.25 = 0.20 kWh
    # Interval 1: (1.0 - 1.0) * 0.25 = 0.0 kWh
    # Interval 2: actual > expected -> 0.0 kWh
    assert np.isclose(shortfall_kwh.iloc[0], 0.20)
    assert np.isclose(shortfall_kwh.iloc[1], 0.00)
    assert np.isclose(shortfall_kwh.iloc[2], 0.00)


def test_daily_yield_scale():
    """
    Validates that recorded DAILY_YIELD is in Watt-hours (Wh) corresponding to 0-15 kWh/day per string.
    """
    p1 = load_raw_generation_data(plant_id=1)
    p2 = load_raw_generation_data(plant_id=2)

    # In Wh, daily yield should be < 15,000 Wh (< 15 kWh) for a 2.56 kWp string
    assert p1["DAILY_YIELD"].max() <= 15000.0, f"Unexpectedly large DAILY_YIELD in Plant 1: {p1['DAILY_YIELD'].max()}"
    assert p2["DAILY_YIELD"].max() <= 15000.0, f"Unexpectedly large DAILY_YIELD in Plant 2: {p2['DAILY_YIELD'].max()}"
