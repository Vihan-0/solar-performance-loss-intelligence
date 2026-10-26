# Final Pre-Evaluation Release Audit Report

**Project**: Adaptive Solar Performance & Loss Intelligence
**Role**: Senior ML Engineer, QA Engineer, Product Designer & Release Reviewer
**Audit Timestamp**: October 27, 2026
**Evaluation Target**: Academic Viva & Final Demonstration
**Automated Test Status**: **46 Passed, 0 Failures, 0 Warnings** (in 9.97 seconds)

---

## 1. Executive Summary & Audit Scope

In preparation for academic evaluation, this release audit independently verified the end-to-end scientific, numerical, engineering, and visual integrity of the **Adaptive Solar Performance & Loss Intelligence** platform.

The audit covered all components across three architectural phases:
1. **Phase I (Utility-Scale Solar Fleet Intelligence)**: Ingestion of 4 Kaggle SCADA CSVs (Plants 1 & 2), canonical unit reconciliation ($1\text{ kW} = 1,000\text{ W}$), leakage-free feature engineering, chronological train/validation/test partitioning, 10-feature Random Forest baseline modeling, weather-enrichment experimentation, dual-baseline anomaly detection, temporal persistence filtering ($\ge 45\text{ min}$), and operational energy-shortfall estimation.
2. **Phase II (Residential Single-Phase Solar Intelligence)**: Dedicated residential validation track ingesting raw telemetry from a private Havells 5.0 kW single-phase string inverter export (`data/home_havells/raw/*.csv`), dynamic file discovery, PII stripping, sampling/gap classification (nocturnal standby vs daytime loss), 3-way energy accounting reconciliation, and honest forecast readiness evaluation.
3. **Phase III (Planned Extensions)**: Explicitly separated and communicated as future roadmap items (weather-informed day-ahead forecasting, authorized live inverter integration via cloud webhooks or Modbus TCP).

All checks were executed empirically on local machine hardware against real datasets, serialized artifacts, and running frontend processes.

---

## 2. Phase 0 — Protection of Work & Git Hygiene Review

Prior to implementing any code fixes or tests, repository state and git exclusion boundaries were verified:

1. **Working Tree Protection**:
   - `git status --short` was recorded before and after all operations. No files were reset, wiped, or unintentionally modified.
   - In accordance with audit constraints, **zero commits or git pushes were executed**.
2. **Data Exclusion Invariants**:
   - Confirmed that `.gitignore` strictly ignores:
     - `data/raw/` (raw Kaggle utility CSVs)
     - `data/processed/` (intermediate Parquet files)
     - `data/external/` (cached Open-Meteo weather Parquet files)
     - `data/home_havells/` (private residential Havells CSV exports)
     - `models/` (`*.joblib` serialized model artifacts)
     - `*.csv`, `*.parquet`, `*.joblib`, `*.feather`, `*.pkl`
     - `.venv/`, `.env`, and IDE configuration files
   - Verified that no private telemetry, credentials, API keys, or inverter serial numbers have been staged or committed.

---

## 3. Phase 1 — Scientific & Numerical Correctness Verification

### 3.1 Units and Energy Accounting
- **1,000× Kaggle Discrepancy Resolution**:
  - The raw Kaggle datasets (`Plant_1_Generation_Data.csv` and `Plant_2_Generation_Data.csv`) labeled `AC_POWER` in kW, but empirical values peaked at $1,410.95$ (Plant 1) and $1,385.42$ (Plant 2).
  - Cross-referenced with published literature (*Clean Energy*, Oxford Academic, 2026, DOI: 10.1093/ce/zkae050), each plant comprises 22 Growatt MIC 1500TL-X inverters rated at $1.5\text{ kW}$ each ($33.0\text{ kW}$ plant total). The raw values represent **Watts (W)**.
  - Canonical scaling was verified across all modules:
    $$\text{AC\_POWER\_KW} = \frac{\text{AC\_POWER}}{1000.0}$$
- **Energy Shortfall Integration**:
  - Energy is calculated strictly via trapezoidal/rectangular time-step integration:
    $$\Delta E (\text{kWh}) = P (\text{kW}) \times \Delta t (\text{hours}) = P (\text{kW}) \times 0.25\text{ h}$$
  - Negative model predictions are strictly clamped to zero ($\max(0, \hat{y})$) prior to residual computation.
  - Cumulative daily counters (`DAILY_YIELD`) are **never summed across rows**. Daily yield was verified to be recorded in Watt-hours (peaking at $\sim 9,873\text{ Wh/day} = 9.87\text{ kWh/day}$) and is strictly excluded from model feature sets.
- **Nighttime Handling**:
  - Nighttime intervals ($\text{IRRADIATION} \le 0$ or Sun below horizon) produce zero generation by definition. Anomaly detection and shortfall estimation are restricted strictly to daylight operational intervals.

### 3.2 Model Evaluation & Artifact Verification
- **Artifact Tested**: `models/best_solar_model.joblib`
- **Model Architecture**: Scikit-learn Pipeline with `StandardScaler` + `OneHotEncoder(handle_unknown='ignore')` + `RandomForestRegressor(n_estimators=100, max_depth=12, min_samples_leaf=5, random_state=42)`.
- **Feature Set Verified**: Exactly 10 leakage-free features:
  `['IRRADIATION', 'AMBIENT_TEMPERATURE', 'MODULE_TEMPERATURE', 'TEMP_DIFF', 'sin_time_of_day', 'cos_time_of_day', 'sin_day_of_year', 'cos_day_of_year', 'PLANT_ID', 'SOURCE_KEY']`
  - Prohibited electrical predictors (`DC_POWER`, `AC_POWER`, `DAILY_YIELD`, `TOTAL_YIELD`) were verified absent.
- **Chronological Split Integrity**:
  - Training: May 15, 2020 05:45:00 to June 4, 2020 11:15:00 (44,966 daylight rows, 60%)
  - Validation: June 4, 2020 11:30:00 to June 11, 2020 07:00:00 (15,896 daylight rows, 20%)
  - Out-of-Time Test: June 11, 2020 07:15:00 to June 17, 2020 18:45:00 (16,236 daylight rows, 20%)
  - Split was executed on sorted unique timestamp groups; observations from the same timestamp are strictly kept in the same partition.
- **Recomputed vs. Saved Milestone 5 Benchmark Metrics**:
  An independent recomputation script (`scripts/verify_model_and_metrics.py`) loaded the serialized artifact and evaluated it on the held-out test partition:

| Metric | Saved Milestone 5 Report | Recomputed from Artifact | Discrepancy | Status |
| :--- | :---: | :---: | :---: | :---: |
| **MAE** | 0.0704 kW (70.4 W) | 0.0704 kW (70.4 W) | 0.0000 kW | **Exact Match** |
| **RMSE** | 0.1704 kW (170.4 W) | 0.1704 kW (170.4 W) | 0.0000 kW | **Exact Match** |
| **$R^2$** | 0.7337 | 0.7337 | 0.0000 | **Exact Match** |
| **WAPE** | 16.46% | 16.46% | 0.00% | **Exact Match** |
| **Mean Residual** | -0.0029 kW | -0.0029 kW | 0.0000 kW | **Exact Match** |
| **Median Abs Error** | 0.0167 kW | 0.0167 kW | 0.0000 kW | **Exact Match** |
| **Sample Size** | 16,236 rows | 16,236 rows | 0 rows | **Exact Match** |

### 3.3 Anomaly Detection & Shortfall Mathematics
- **Dual-Baseline Architecture**:
  1. *Inverter ML Baseline*: Evaluates actual active power against weather expectations conditioned on inverter identity.
  2. *Capacity-Normalized Peer Cohort Benchmark*: Normalizes each inverter by its 99th-percentile capacity rating ($C_i$) and compares against concurrent plant peer median generation:
     $$P_{\text{cohort}}(t, i) = \text{Median}\left(\left\{\frac{P_{\text{actual}}(t, j)}{C_j}\right\}_{j \in \text{Plant}}\right) \times C_i$$
- **Threshold Calibration**:
  - Evaluated on the validation split across three irradiance regimes: Low ($<0.2\text{ kW/m}^2$), Medium ($0.2–0.6\text{ kW/m}^2$), and High ($>0.6\text{ kW/m}^2$).
  - Plant 2 High-Sun threshold recalibrated to $0.0846\text{ kW}$ on operating inverters, preventing catastrophic dropouts from inflating normal derate thresholds.
- **Persistence Filter Rules**:
  - Anomaly condition must persist for $\ge 3$ consecutive valid 15-minute intervals ($\ge 45\text{ minutes}$).
  - Missing intervals reset the persistence counter to zero (gap-bridging is strictly prevented).
- **Verified Fleet Loss Accounting (Held-Out Test Set)**:
  - Total Measured Generation: **1,736.26 kWh**
  - Expected Model Generation: **1,724.51 kWh**
  - Total Raw Positive Residual Shortfall: **137.02 kWh** (7.95% of expected)
  - Persistent Actionable Shortfall ($\ge 45$m): **89.44 kWh (5.19% fleet loss)**
  - Suppressed Transient Fluctuation: **47.58 kWh** (nuisance cloud shadows safely ignored)
  - Accumulated Inverter Alert-Hours: **158.75 hours** (Plant 1: 11.5 h; Plant 2: 147.25 h)
  - Plant 2 accounts for **92.6% of fleet persistent loss** (82.80 kWh).
- **Terminology Governance**:
  - Detections are labeled **candidate underperformance events**, not confirmed physical hardware failures.

### 3.4 Weather Enrichment Experiment
- Regional hourly ERA5 reanalysis data from Open-Meteo was mapped to 15-minute timestamps via forward interpolation without lookahead leakage.
- Enriched models added `weather_temperature_2m`, `weather_relative_humidity_2m`, `weather_cloud_cover`, `weather_wind_speed_10m`, and `weather_surface_pressure`.
- **Empirical Result**: Validation MAE slightly worsened from $0.1055\text{ kW}$ (Baseline RF) to $0.1076\text{ kW}$ (Enriched RF, $+1.99\%$). Onsite pyranometers and thermocouples capture direct module physics superior to regional grid approximations. Per Occam's razor, the baseline model was retained.

---

## 4. Phase 2 — Phase II Residential Solar Intelligence Audit

### 4.1 Ingestion, Discovery & Privacy
- **Dynamic File Discovery**: `src/residential.py` uses dynamic globbing (`data/home_havells/raw/*.csv`) rather than hardcoded machine paths. If no file exists, the dashboard displays an informative guidance card.
- **Privacy Enforcement**:
  - Column headers containing hardware serial numbers (`SN`, `Device SN`), account credentials, or inverter PCU IDs are scrubbed dynamically during ingestion (`sanitize_dataframe`).
  - No personal identifiers, network endpoints, or raw serial numbers are stored in reports or rendered on the frontend.
  - `data/home_havells/` is strictly untracked in `.gitignore`.

### 4.2 Telemetry Invariants & EDA
Verified directly against the 7-day Havells export (October 20–26, 2026):
- **Observations**: 997 synchronous records across 63 telemetry channels. 0 nulls, 0 duplicate timestamps.
- **Sampling Cadence**: Nominal 300-second (5.0-minute) intervals with minor clock jitter ($\pm 4$s).
- **Nocturnal Standby Gaps**: Exactly 6 overnight gaps ($\sim 12$ hours each), corresponding to natural shutdown at sunset ($\sim 17:55$) and wake-up at dawn ($\sim 06:01$). **Zero unexpected daytime communication dropouts occurred**.
- **Peak AC Power**: **3.58 kW** ($3,580\text{ W}$) observed at midday on Oct 20 (71.6% of rated 5.0 kW capacity without clipping).
- **Operating States**: Grid Connected (96.8%, 965 intervals), Waiting (2.3%, 23 intervals at dawn/dusk), Recoverable Fault (0.7%, 7 intervals during transient utility grid excursions), Checking (0.2%, 2 intervals).
- **Thermocouple Semantics**: Internal motherboard chassis temperature (0–61°C) and radiator heatsink temperature (0–62°C) sensors reflect inverter power conversion dissipation, not external weather ambient air.

### 4.3 Three-Way Energy Accounting Reconciliation
The three separate energy measurements were reconciled across the 7-day period:
1. **Cumulative Odometer Delta**: $E_{\text{end}} - E_{\text{start}} = 7,992.0 - 7,857.1 = \mathbf{134.90\text{ kWh}}$
2. **Daily Counter Sum**: $\sum_{d=1}^{7} E_{\text{daily}} = 22.79 + 20.83 + 20.49 + 19.70 + 18.20 + 16.78 + 16.15 = \mathbf{134.94\text{ kWh}}$
3. **Discrete Trapezoidal Integral**: $\sum P(t)\Delta t = \mathbf{135.90\text{ kWh}}$ ($+0.7\%$ delta due to 5-minute discrete sampling).

### 4.4 Day-Ahead Forecast Readiness & Non-Claims
- In strict adherence to `AGENTS.md` and honest scientific methodology, the dashboard does not present a fabricated day-ahead forecast for tomorrow.
- A 7-day export is appropriate for baseline profiling and inverter operational health assessment, but is insufficient to train a multi-season day-ahead ML model without extreme seasonal overfitting.
- The platform presents a structured **Forecast Readiness Scorecard** identifying prerequisite data feeds (localized high-resolution solar irradiance forecasts, live API authorization, multi-month historical telemetry) required for Phase III implementation.

---

## 5. Phase 3 & 4 — Frontend, UX & Synthetic Demonstration

### 5.1 Design & Visual Architecture
The frontend was designed following the `apple-design` design skill:
- **Surface & Palette**: Deep midnight graphite surfaces (`#0c1417` / `#131e22`), translucent card containers with subtle 1px border treatments (`rgba(255,255,255,0.08)`), and restrained emerald (`#10b981`) and amber (`#f59e0b`) accents.
- **Typography & Layout**: Standardized layout padding, high-contrast typography, tabular numerals for energy numbers, and readable Plotly charts with custom dark templates and hover tooltips.
- **Responsive Navigation**: Sidebar navigation dividing the product into 6 coherent, dedicated views.

### 5.2 Six-View Browser Inspection Results
The running application at `http://localhost:8501` was inspected using the automated browser agent across all six views:

| View | Verification Checklist & Observations | Verified Screenshot |
| :--- | :--- | :--- |
| **1. Overview & Loss Summary** | Executive roadmap card, 4 KPI cards ($1,736.3\text{ kWh}$ measured, $1,724.5\text{ kWh}$ expected, $89.44\text{ kWh}$ persistent shortfall, $0.7337\text{ }R^2$), fleet timeline, plant loss breakdown cards. | [audit_view_1_overview.png](../reports/figures/audit_view_1_overview.png) |
| **2. Phase II | Residential Solar Intelligence** | 6-metric KPI strip (997 readings, 7 days, 3.58 kW peak, 134.94 kWh total, 5.0m sampling, Baseline Ready), 4 interactive tabs, 3-way energy reconciliation card, thermal & state charts, forecast readiness scorecard. | [audit_view_2_phase_ii.png](../reports/figures/audit_view_2_phase_ii.png) |
| **3. Plant & Inverter Explorer** | Interactive plant and inverter selector (tested Plant 2, inverter `Qf4GUc1pJu5T6c6`), dual baseline traces, evidence cards, anomaly markers, and interval telemetry table. | [audit_view_3_explorer.png](../reports/figures/audit_view_3_explorer.png) |
| **4. Inverter Loss Prioritization** | Urgency ranking table across all 44 inverters with persistent shortfall, loss percentage, alert hours, and CSV export functionality. | [audit_view_4_prioritization.png](../reports/figures/audit_view_4_prioritization.png) |
| **5. Interactive Synthetic Sandbox** | Interactive sliders for severity and duration; verified that 1-interval and 2-interval transient dips are filtered, while $\ge 3$ intervals trigger persistent anomaly detection. | [audit_view_5_synthetic.png](../reports/figures/audit_view_5_synthetic.png) |
| **6. Model Architecture & Methodology** | System architecture diagram, physical unit discrepancy resolution, 10-feature documentation, benchmark comparison table, and domain limitations. | [audit_view_6_methodology.png](../reports/figures/audit_view_6_methodology.png) |

### 5.3 Synthetic Demonstration Validation
The interactive synthetic engine was verified against four canonical test cases:
1. **1-Interval Transient Reduction (-50%, 15m)**: Suppressed by persistence filter; 0 alert-hours, 0 kWh shortfall.
2. **2-Interval Transient Reduction (-50%, 30m)**: Suppressed by persistence filter; 0 alert-hours, 0 kWh shortfall.
3. **Persistent Complete Trip (0 kW, 60m)**: Correctly flagged as persistent underperformance; calculated positive shortfall.
4. **Persistent Partial Derate (-40%, 60m)**: Correctly flagged as persistent underperformance; calculated positive shortfall.

---

## 6. Phase 5 — Defect Remediations & QA Fixes Applied

During the course of the release audit, several latent numerical, syntax, and deprecation defects were identified and resolved:

1. **Plant Loss Summary Unit Scaling Fix ([src/loss.py](../src/loss.py))**:
   - *Defect*: `aggregate_plant_loss_summary` defaulted to `"AC_POWER"` without applying the `0.001` scale factor that `aggregate_inverter_loss_summary` used.
   - *Fix*: Standardized the default column name to `"AC_POWER_KW"` and added dynamic unit scaling (`scale = 0.001 if col == "AC_POWER" else 1.0`), ensuring plant-level aggregations are immune to unit mismatches.
2. **Plotly ColorBar Property Fix ([src/residential.py](../src/residential.py))**:
   - *Defect*: Setting `titleside="right"` inside `marker=dict(colorbar=...)` triggered a runtime Plotly `ValueError` because `titleside` is invalid in current Plotly versions.
   - *Fix*: Replaced with `colorbar=dict(title="AC Power (kW)")`, resolving the chart rendering failure.
3. **Pandas Deprecation Warnings ([src/features.py](../src/features.py) & [src/weather.py](../src/weather.py))**:
   - *Defect*: Usage of `Series.dt.dayofyear` triggered deprecation warnings in pandas 2.2+; usage of `inplace=True` on `DataFrame.drop` triggered deprecation warnings.
   - *Fix*: Updated `features.py` to use `day_of_year` where supported, and updated `weather.py` to `merged = merged.drop(...)`. All deprecation warnings in the test suite were eliminated (0 warnings).
4. **Windows CP1252 Terminal Encoding Fix**:
   - *Defect*: Resistance headers containing the Greek Ohm symbol (`KΩ`) threw `UnicodeEncodeError` when printed to standard Windows console streams.
   - *Fix*: Inspection scripts were refactored to write outputs with explicit UTF-8 encoding.

---

## 7. Automated Test Suite Results

The full test suite was executed via pytest in the clean virtual environment:

```
============================= test session starts =============================
platform win32 -- Python 3.13.3, pytest-9.1.1, pluggy-1.7.0
rootdir: solar-performance-loss-intelligence
plugins: anyio-4.15.1
collected 46 items

tests/test_anomaly_detection.py::test_normal_generation_zero_shortfall PASSED [  2%]
tests/test_anomaly_detection.py::test_isolated_dip_rejected_by_persistence_filter PASSED [  4%]
tests/test_anomaly_detection.py::test_persistent_drop_triggers_anomaly PASSED [  6%]
tests/test_anomaly_detection.py::test_gap_bridging_prevention PASSED     [  8%]
tests/test_anomaly_detection.py::test_nighttime_zero_shortfall PASSED    [ 10%]
tests/test_anomaly_detection.py::test_energy_shortfall_calculation PASSED [ 13%]
tests/test_anomaly_detection.py::test_peer_cohort_capacity_normalization PASSED [ 15%]
tests/test_dashboard.py::test_load_reports PASSED                        [ 17%]
tests/test_dashboard.py::test_load_pipeline_artifact PASSED              [ 19%]
tests/test_dashboard.py::test_load_processed_data PASSED                 [ 21%]
tests/test_dashboard.py::test_prepare_evaluation_datasets PASSED         [ 23%]
tests/test_dashboard.py::test_simulate_synthetic_event PASSED            [ 26%]
tests/test_data_pipeline.py::test_timestamp_parsing_and_types PASSED     [ 28%]
tests/test_data_pipeline.py::test_row_count_preservation_and_no_multiplication PASSED [ 30%]
tests/test_data_pipeline.py::test_weather_sensor_key_no_collision PASSED [ 32%]
tests/test_data_pipeline.py::test_missing_weather_tracking PASSED        [ 34%]
tests/test_data_pipeline.py::test_feature_engineering_integrity PASSED   [ 36%]
tests/test_data_pipeline.py::test_target_leakage_prevention PASSED       [ 39%]
tests/test_pipeline_determinism PASSED                                  [ 41%]
tests/test_processed_artifacts_exist_and_load PASSED                    [ 43%]
tests/test_model_training.py::test_chronological_split_strict_ordering PASSED [ 45%]
tests/test_model_training.py::test_group_integrity_same_timestamp_cohesion PASSED [ 47%]
tests/test_model_training.py::test_prohibited_leakage_features PASSED    [ 50%]
tests/test_model_training.py::test_unseen_categorical_safety PASSED      [ 52%]
tests/test_model_training.py::test_model_artifact_load_and_predict PASSED [ 54%]
tests/test_model_training.py::test_evaluation_metric_properties PASSED   [ 56%]
tests/test_raw_data_audit.py::test_file_row_counts_and_nulls PASSED      [ 58%]
tests/test_raw_data_audit.py::test_inverter_and_sensor_cardinality PASSED [ 60%]
tests/test_raw_data_audit.py::test_key_uniqueness_no_duplicates PASSED   [ 63%]
tests/test_raw_data_audit.py::test_join_integrity_no_row_multiplication PASSED [ 65%]
tests/test_raw_data_audit.py::test_no_ground_truth_fault_labels PASSED   [ 67%]
tests/test_residential.py::test_missing_file_graceful_handling PASSED    [ 69%]
tests/test_residential.py::test_dynamic_file_discovery_empty PASSED      [ 71%]
tests/test_residential.py::test_dynamic_file_discovery_success PASSED    [ 73%]
tests/test_pii_sanitization PASSED                  [ 76%]
tests/test_residential.py::test_unit_conversion_watts_to_kw PASSED       [ 78%]
tests/test_residential.py::test_daily_energy_calculation_no_counter_multiplication PASSED [ 80%]
tests/test_residential.py::test_sampling_interval_and_gap_detection PASSED [ 82%]
tests/test_residential.py::test_real_havells_file_if_present PASSED      [ 84%]
tests/test_unit_conversions.py::test_canonical_ac_power_kw_conversion PASSED [ 86%]
tests/test_unit_conversions.py::test_physical_inverter_and_plant_bounds PASSED [ 89%]
tests/test_unit_conversions.py::test_energy_arithmetic_kwh PASSED        [ 91%]
tests/test_unit_conversions.py::test_daily_yield_scale PASSED            [ 93%]
tests/test_weather_enrichment.py::test_weather_cache_loading_and_schema PASSED [ 95%]
tests/test_weather_enrichment.py::test_weather_unit_standardization PASSED [ 97%]
tests/test_weather_enrichment.py::test_alignment_row_preservation_and_no_multiplication PASSED [100%]

============================= 46 passed in 9.97s ==============================
```

---

## 8. Explicit Limitations & Viva Defense Boundaries

To ensure complete defensibility during tomorrow's evaluation, the following boundaries and non-claims are documented:

1. **Short Observation Horizon (34 Days Utility, 7 Days Residential)**:
   - The utility dataset spans May 15 to June 17, 2020 (early summer). Models have not been exposed to monsoon cloud cover or winter sun angles. Annualizing energy loss or claiming year-round performance is methodologically invalid.
2. **Absence of Physical Maintenance Work Orders**:
   - Neither Kaggle nor the residential inverter export provides ground-truth maintenance logs. All detections represent **candidate underperformance intervals** requiring dispatch and physical inspection, not proven hardware component breakdowns.
3. **Weather Reanalysis Spatial Resolution**:
   - External Open-Meteo reanalysis operates at regional grid scales ($\sim 11\text{ km}$ / $0.1^\circ$), which cannot capture localized cloud shadows as effectively as onsite pyranometers.
4. **Phase III Forecasting Status**:
   - The platform does not claim a validated day-ahead solar forecasting model for the residential system. Implementing day-ahead NWP forecasting requires verified rooftop GPS coordinates and multi-month operational data.

---

## 9. Launch & Reproduction Instructions

To execute the application for the evaluation demonstration:

```bash
# 1. Activate virtual environment
.venv\Scripts\activate

# 2. Run test suite to verify system health
pytest -v

# 3. Launch interactive Streamlit application
streamlit run app.py
```

The application is hosted locally at `http://localhost:8501`.
