# Milestone 2: Reproducible Data Pipeline & Feature Engineering Report
**Project:** Adaptive Solar Performance & Loss Intelligence
**Date:** October 24, 2026
**Pipeline Code:** [`src/data.py`](../src/data.py), [`src/features.py`](../src/features.py)
**Execution Script:** [`scripts/build_dataset.py`](../scripts/build_dataset.py)
**Verification Test Suite:** [`tests/test_data_pipeline.py`](../tests/test_data_pipeline.py) + [`tests/test_raw_data_audit.py`](../tests/test_raw_data_audit.py) (13/13 passing)
**Processed Artifacts:** Saved in `data/processed/` (untracked in Git via `.gitignore`)

---

## 1. Executive Summary

Milestone 2 establishes a fully automated, deterministic, and leak-free data ingestion, cleaning, and feature engineering pipeline.

The pipeline converts raw, heterogeneous CSV records into standardized, typed datasets without altering raw source files or inventing missing measurements. All generation observations are preserved via validated left joins, known sensor dropouts are explicitly flagged, and target leakage is strictly prevented.

---

## 2. Row Counts: Ingestion, Merging, and Filtering

All counts were empirically verified by running [`scripts/build_dataset.py`](../scripts/build_dataset.py) and passing automated assertions:

| Stage | Plant 1 | Plant 2 | Combined Multi-Plant | Notes / Integrity Guarantee |
|---|---|---|---|---|
| **Raw Generation Rows** | 68,778 | 67,698 | 136,476 | Input from `data/raw/` |
| **Raw Weather Rows** | 3,182 | 3,259 | 6,441 | Input from `data/raw/` |
| **Merged Full Dataset** | **68,778** | **67,698** | **136,476** | **100.0% row preservation** via left join with `validate='many_to_one'`. Zero rows lost or multiplied. |
| *-- With Valid Weather (`has_weather=True`)* | 68,774 | 67,698 | 136,472 | 4 rows in P1 lacked weather |
| *-- Missing Weather (`has_weather=False`)* | 4 | 0 | 4 | Timestamp `2020-06-03 14:00:00` |
| **Model-Ready Dataset**<br>*(Daylight Operational: `IRRADIATION > 0`)* | **38,376** | **38,722** | **77,098** | Daylight filtering isolates active power generation; excludes nighttime trivial zeros and missing-weather rows. |
| *-- Nighttime / Zero Irradiance Rows* | 30,398 | 28,976 | 59,374 | Preserved in merged parquet for operational shortfall baselines, filtered from initial regression set. |

---

## 3. Handling of Known Data Anomalies

### A. Missing Weather Observations (Plant 1)
- **Observation:** On `2020-06-03 14:00:00`, 4 inverters in Plant 1 reported power generation (`AC_POWER` between 685 kW and 778 kW), but the central weather station had an isolated communication dropout.
- **Decision:**
  1. In `plant_1_merged.parquet`, all 4 generation records are **strictly preserved** with `has_weather = False` and NaN for weather metrics.
  2. In `plant_1_model_ready.parquet`, these 4 records are excluded from model training because required meteorological regressors are absent.
  3. No forward-filling or synthetic temperature/irradiance interpolation was fabricated, maintaining experimental integrity.

### B. Long Reporting Gaps (Plant 2 Inverters)
- **Observation:** Four specific inverters in Plant 2 (`IQ2d7wF4YD8zU1Q`, `NgDl19wMapZy17u`, `mqwcsP2rE7J0TFp`, `xMbIugepa2P7lBB`) dropped offline from **2020-05-20 21:45:00 to 2020-05-29 16:15:00** (a continuous gap of 904 intervals / ~8.77 days).
- **Decision:**
  1. We do **NOT** interpolate missing power readings, forward-fill zero power across 8.7 days, or invent dummy rows.
  2. Gaps are preserved as true operational absences.
  3. When future lag or rolling features are evaluated, time deltas will be asserted so that an 8.7-day gap is never treated as a consecutive 15-minute lag.

### C. Join Cardinality & Key Disambiguation
- **Observation:** Generation data uses `SOURCE_KEY` for inverter hardware identifiers (22 distinct entities), whereas weather data uses `SOURCE_KEY` for the central weather station sensor (`HmiyD2TTLFNqkNe` / `iq8k7ZNt4Mwm3w0`).
- **Decision:**
  - Weather's `SOURCE_KEY` is renamed to `WEATHER_SENSOR_KEY` during ingestion.
  - Joins are executed strictly on `['TIMESTAMP', 'PLANT_ID']`.
  - Merges enforce `validate='many_to_one'`, guaranteeing that each inverter reading at timestamp $t$ maps to exactly one ambient weather reading without Cartesian multiplication.

---

## 4. Feature Engineering & Target Leakage Prevention

### Target Variable ($y$)
- **`AC_POWER`**: Continuous inverter active power output in kilowatts (kW).

### Approved Feature Matrix ($X$)
Every engineered feature in [`src/features.py`](../src/features.py) is grounded in physical domain relationships:

1. **`IRRADIATION`**: Solar irradiance ($\text{kW/m}^2$). Primary driver of photovoltaic generation.
2. **`AMBIENT_TEMPERATURE`**: Ambient dry-bulb air temperature ($^\circ\text{C}$).
3. **`MODULE_TEMPERATURE`**: PV panel back-surface temperature ($^\circ\text{C}$).
4. **`TEMP_DIFF`**: $\text{MODULE\_TEMPERATURE} - \text{AMBIENT\_TEMPERATURE}$ ($^\circ\text{C}$). Direct physical indicator of solar thermal absorption and cell operating heating efficiency.
5. **`sin_time_of_day` & `cos_time_of_day`**: Continuous diurnal cycle encoding fractional hour ($0.0$ to $23.75$), capturing smooth solar zenith / elevation progression across the day.
6. **`sin_day_of_year` & `cos_day_of_year`**: Annual seasonal cycle encoding day of year ($1$ to $365$), capturing solar declination.
7. **`SOURCE_KEY`**: Categorical inverter identity, allowing tree-based or linear models to learn inverter-specific capacity or hardware calibration differences.
8. **`PLANT_ID`**: Categorical plant identifier ($4135001$ vs $4136001$).

### Strictly Forbidden Predictors (Target Leakage Mitigation)
The pipeline enforces an automated runtime assertion that raises an exception if any of the following appear in $X$:
- **`AC_POWER`**: Direct target leakage.
- **`DC_POWER`**: Pearson $r > 0.9999$. Providing contemporaneous DC power causes the model to merely learn an inverter conversion ratio ($\approx 97.5\%$), completely masking array-level underperformance (e.g., panel soiling, shading, string dropouts).
- **`DAILY_YIELD`**: Running integral of same-day energy ($\int_0^t P(\tau)d\tau$). Leaks performance of prior intervals from the same day into the current time step.
- **`TOTAL_YIELD`**: Non-stationary lifetime odometer. Leaks absolute time and trend.

---

## 5. Automated Verification Results

All 13 automated unit tests pass in `pytest` with zero warnings:

```bash
pytest -v
```
Output:
```
tests/test_data_pipeline.py::test_timestamp_parsing_and_types PASSED     [  7%]
tests/test_data_pipeline.py::test_row_count_preservation_and_no_multiplication PASSED [ 15%]
tests/test_data_pipeline.py::test_weather_sensor_key_no_collision PASSED [ 23%]
tests/test_data_pipeline.py::test_missing_weather_tracking PASSED        [ 30%]
tests/test_data_pipeline.py::test_feature_engineering_integrity PASSED   [ 38%]
tests/test_data_pipeline.py::test_target_leakage_prevention PASSED       [ 46%]
tests/test_data_pipeline.py::test_pipeline_determinism PASSED            [ 53%]
tests/test_data_pipeline.py::test_processed_artifacts_exist_and_load PASSED [ 61%]
tests/test_raw_data_audit.py::test_file_row_counts_and_nulls PASSED      [ 69%]
tests/test_raw_data_audit.py::test_inverter_and_sensor_cardinality PASSED [ 76%]
tests/test_raw_data_audit.py::test_key_uniqueness_no_duplicates PASSED   [ 84%]
tests/test_raw_data_audit.py::test_join_integrity_no_row_multiplication PASSED [ 92%]
tests/test_raw_data_audit.py::test_no_ground_truth_fault_labels PASSED   [100%]

============================= 13 passed in 2.74s ==============================
```

---

## 6. Open Observations & Data Quality Notes

1. **Inter-Plant Electrical Scaling:**
   - As documented in Milestone 1, Plant 1 records `DC_POWER` on a $\approx 10\times$ scale relative to `AC_POWER` (mean DC 3,147 kW vs mean AC 308 kW), whereas Plant 2 records on a $\approx 1:1$ scale (mean DC 247 kW vs mean AC 241 kW).
   - Our baseline model predictors $X$ rely solely on weather (`IRRADIATION`, `TEMPERATURES`) and time/entity encodings, avoiding direct DC power contamination. However, when modeling both plants together, models should either be fitted independently per plant or conditioned on `PLANT_ID`.
2. **Daylight Filtering Justification:**
   - Nighttime records ($\text{IRRADIATION} = 0$) represent 43.5% of rows. During night, $\text{AC\_POWER} = 0.0$ kW is physically guaranteed. Including nighttime records in regression metrics trivially inflates $R^2$ to $>0.99$ while masking day-time prediction errors. Isolating daylight hours ($IRRADIATION > 0$) ensures rigorous model evaluation.
3. **External Weather Data:**
   - In accordance with Milestone 2 guidelines, external cloud cover, satellite, or NWP weather variables have not been added yet; we rely solely on verified on-site meteorological telemetry.
