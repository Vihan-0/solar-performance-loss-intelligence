# Milestone 1: Raw Data Audit Report
**Project:** Adaptive Solar Performance & Loss Intelligence
**Date:** October 24, 2026
**Audited Datasets:** 4 CSVs in `data/raw/`
**Audit Script:** [`scripts/audit_raw_data.py`](../scripts/audit_raw_data.py)
**Verification Tests:** [`tests/test_raw_data_audit.py`](../tests/test_raw_data_audit.py) (5/5 tests passing)

---

## 1. Executive Summary

This audit rigorously inspects the four raw CSV files comprising generation and meteorological sensor records from two distinct solar power plants (Plant 1 and Plant 2).

All 207,916 combined raw rows were audited for schema validity, timestamp formatting, completeness, reporting intervals, join cardinality, and predictive validity. No raw files were modified.

### Key Audit Findings Table
| Dataset | Rows | Columns | Null Count | Exact Dups | Key Dups | Unique Sources | Timestamp Range (UTC/Local) | Raw Date Format |
|---|---|---|---|---|---|---|---|---|
| **Plant 1 Generation** | 68,778 | 7 | 0 (0.0%) | 0 | 0 | 22 inverters | 2020-05-15 00:00 to 2020-06-17 23:45 | `%d-%m-%Y %H:%M` (day-first) |
| **Plant 1 Weather** | 3,182 | 6 | 0 (0.0%) | 0 | 0 | 1 sensor | 2020-05-15 00:00 to 2020-06-17 23:45 | `%Y-%m-%d %H:%M:%S` |
| **Plant 2 Generation** | 67,698 | 7 | 0 (0.0%) | 0 | 0 | 22 inverters | 2020-05-15 00:00 to 2020-06-17 23:45 | `%Y-%m-%d %H:%M:%S` |
| **Plant 2 Weather** | 3,259 | 6 | 0 (0.0%) | 0 | 0 | 1 sensor | 2020-05-15 00:00 to 2020-06-17 23:45 | `%Y-%m-%d %H:%M:%S` |

---

## 2. Investigation of Core Questions

### Question 1: Are generation timestamps consistently 15 minutes apart?
- **Empirical Findings:**
  - **Plant 1 Generation**: 99.52% of consecutive intervals per inverter are exactly 15 minutes apart. However, intervals range from **15.0 minutes to 540.0 minutes (9.0 hours)**. Total records per inverter vary between 3,104 and 3,155 (out of 3,158 unique plant timestamps).
  - **Plant 2 Generation**: 99.82% of consecutive intervals per inverter are exactly 15 minutes apart. However, maximum gap reaches **12,630.0 minutes (210.5 hours / ~8.77 days)**. Total records per inverter range from 2,355 to 3,259.
  - Specifically, four inverters in Plant 2 (`IQ2d7wF4YD8zU1Q`, `NgDl19wMapZy17u`, `mqwcsP2rE7J0TFp`, `xMbIugepa2P7lBB`) went entirely dark between **2020-05-20 21:45:00 and 2020-05-29 16:15:00** (a continuous gap of 904 intervals / ~8.77 days).
- **Engineering Implication**: Timestamps are **predominantly regular (15-min cadence)**, but pipelines cannot assume an uninterrupted time-grid. Resampling to a regular 15-minute grid or handling missing intervals explicitly is mandatory before computing rolling or lag features.

---

### Question 2: Do multiple inverters share the same timestamp?
- **Empirical Findings:**
  - **Yes, absolutely**. Each solar plant operates 22 independent inverters feeding into the grid simultaneously.
  - In **Plant 1 Generation**:
    - Timestamps with all 22 inverters reporting: **3,057**
    - Timestamps with 10 inverters reporting: **32**
    - Timestamps with 21 inverters reporting: **27**
    - Timestamps with 14 inverters reporting: **23**
    - Minimum reporting inverters at any single timestamp: **4**
  - In **Plant 2 Generation**:
    - Timestamps with all 22 inverters reporting: **2,355**
    - Timestamps with 18 inverters reporting: **840** (corresponding to the 4 missing inverters during the 8.77-day dropout)
    - Timestamps with 12 inverters reporting: **64**
    - Minimum reporting inverters at any single timestamp: **12**
- **Engineering Implication**: The generation datasets possess a **multi-entity panel structure** (22 distinct entities observed concurrently at each 15-minute time step). Time-series models must treat inverter identity (`SOURCE_KEY`) as an entity grouping key.

---

### Question 3: Must weather records be joined using both plant and timestamp?
- **Empirical Findings:**
  - Generation and weather tables operate at fundamentally different granularities:
    - **Generation**: Inverter-level (22 `SOURCE_KEY` identifiers per timestamp).
    - **Weather**: Plant-level (1 central meteorological sensor per timestamp, with keys `HmiyD2TTLFNqkNe` for Plant 1 and `iq8k7ZNt4Mwm3w0` for Plant 2).
  - Inverter `SOURCE_KEY` and weather sensor `SOURCE_KEY` share **0% overlap** (`set(gen_keys) ∩ set(weather_keys) == ∅`). Attempting to join including `SOURCE_KEY` drops 100% of rows.
  - Plant IDs are disjoint between the plants (`4135001` for Plant 1, `4136001` for Plant 2).
- **Engineering Implication**:
  - Weather's `SOURCE_KEY` must be dropped or renamed (e.g., `WEATHER_SENSOR_KEY`) prior to merging.
  - Merges must be executed on `['DATE_TIME', 'PLANT_ID']`. Joining on both fields guarantees that multi-plant data cannot be cross-contaminated.

---

### Question 4: Would a join duplicate rows?
- **Empirical Findings:**
  - In both weather datasets (`Plant_1_Weather_Sensor_Data.csv` and `Plant_2_Weather_Sensor_Data.csv`), the timestamp `DATE_TIME` is strictly unique (**0 duplicate timestamps** in weather tables).
  - Left Join Row Counts:
    - **Plant 1**: Pre-join Gen rows = 68,778 $\rightarrow$ Left-joined rows = **68,778** (0 row multiplication).
    - **Plant 2**: Pre-join Gen rows = 67,698 $\rightarrow$ Left-joined rows = **67,698** (0 row multiplication).
  - Inner Join Row Counts:
    - **Plant 1 Inner Join**: Yields 68,774 rows (exactly 4 rows dropped from generation data because timestamp `2020-06-03 14:00:00` was missing in weather telemetry).
    - **Plant 2 Inner Join**: Yields 67,698 rows (100% match).
- **Engineering Implication**: Merging generation with weather **does not duplicate any rows** when joined on `['DATE_TIME', 'PLANT_ID']`. A left-join preserves all generation observations, requiring minor forward-fill or interpolation for isolated missing weather readings (e.g., the 4 rows on June 3 at 14:00).

---

### Question 5: Does the dataset contain genuine fault labels or maintenance records?
- **Empirical Findings:**
  - A systematic search of all column names across all four CSVs reveals **zero columns** indicating errors, faults, alerts, trips, maintenance logs, or target labels (`['fault', 'alarm', 'error', 'status', 'event', 'maint', 'label', 'target']`).
- **Engineering Implication**:
  - **There is no ground-truth supervised fault dataset**.
  - All underperformance detection must be conducted using **unsupervised residual analysis** (comparing actual generation against expected baseline generation derived from solar irradiance and panel physics).
  - In accordance with Rule 5 of `AGENTS.md`, anomalies identified by ML residuals represent **candidate underperformance events**, not confirmed hardware failures.

---

### Question 6: Target Leakage Analysis for Candidate Predictor Variables
Our core modeling task is to predict **expected AC power generation** ($P_{\text{expected}}$) given ambient environmental conditions and inverter characteristics.

Evaluating candidate variables reveals critical risks:

| Variable | Empirical Pearson $r$ with `AC_POWER` | Target Leakage Risk Level | Rationale & Pipeline Rule |
|---|---|---|---|
| **`AC_POWER`** | 1.0000 | **Extreme / Direct Leakage** | Target variable ($y$). Cannot be used contemporaneously. |
| **`DC_POWER`** | 0.999996 (P1)<br>0.999997 (P2) | **Severe Functional Leakage** | `DC_POWER` is the direct electrical precursor to `AC_POWER` ($P_{AC} = \eta \cdot P_{DC}$). If contemporary `DC_POWER` is supplied to the model: (1) The model degenerates into an inverter efficiency curve ($\approx 0.975$ or $\approx 0.10$ in P1); (2) It becomes blind to DC-side faults (soiling, shading, broken strings), because as DC collapses, the model predicts low AC and reports zero loss; (3) Contemporaneous DC power is unavailable during predictive scheduling. |
| **`DAILY_YIELD`** | 0.0822 (P1)<br>0.0054 (P2) | **High Contemporaneous Leakage** | `DAILY_YIELD` is a running integration of power generated since 00:00 today ($\int_{0}^{t} P(\tau) d\tau$). Providing `DAILY_YIELD` at timestamp $t$ directly leaks the cumulative performance of earlier intervals from the same day into the current prediction. |
| **`TOTAL_YIELD`** | 0.0038 (P1)<br>0.0045 (P2) | **Stationarity & Trend Leakage** | Lifetime cumulative counter (odometer). In Plant 1 it ranges from 6.18M to 7.84M; in Plant 2 it ranges from 0 to 2.24B. It is strictly non-stationary and leaks position along the temporal axis. It should not be used as a raw continuous regressor. |

**Approved Independent Predictors ($X$) for Baseline Model**:
- Environmental: `IRRADIATION`, `AMBIENT_TEMPERATURE`, `MODULE_TEMPERATURE`.
- Temporal / Solar Position: `hour`, `day_of_year`, solar elevation/zenith proxies.
- Static Categorical: `SOURCE_KEY` (inverter identifier / one-hot encoded or target-encoded via strictly past folds).
- Strictly Lagged Performance Features: $t-24\text{h}$ or historical moving average baselines.

---

## 3. Physical & Scaling Anomalies Discovered

### Discrepancy in `DC_POWER` Scaling
- **Plant 1**:
  - `DC_POWER` Mean: 3,147.4 kW (Max: 14,471.1 kW)
  - `AC_POWER` Mean: 307.8 kW (Max: 1,410.95 kW)
  - Ratio: $P_{DC} / P_{AC} \approx 10.25$. DC power is recorded in different units (e.g., 10-Watt units or string aggregated).
- **Plant 2**:
  - `DC_POWER` Mean: 246.7 kW (Max: 1,420.93 kW)
  - `AC_POWER` Mean: 241.3 kW (Max: 1,385.42 kW)
  - Ratio: $P_{DC} / P_{AC} \approx 1.025$ ($\approx 97.5\%$ inverter conversion efficiency).
- **Takeaway**: Plant 1 and Plant 2 cannot share identical raw electrical thresholds. Models trained across plants must account for distinct feature scaling and reporting units.

---

## 4. Milestone 1 Status & Acceptance

- [x] Reproducible audit script created at [`scripts/audit_raw_data.py`](../scripts/audit_raw_data.py).
- [x] All 5 automated unit tests passing in [`tests/test_raw_data_audit.py`](../tests/test_raw_data_audit.py).
- [x] Data audit report compiled with exact empirical metrics.
- [x] Zero raw data files modified; zero premature modeling or UI code executed.
