# Milestone 4: Residual-Based Anomaly Detection & Energy-Loss Intelligence Report (SUPERSEDED)
**Project:** Adaptive Solar Performance & Loss Intelligence
**Date:** October 24, 2026 (Archived Post-Milestone 5)
**Status:** **SUPERSEDED ARCHIVE FILE — DO NOT USE FOR CURRENT OPERATIONAL SHORTFALL METRICS**

> [!WARNING]
> **SUPERSEDED PRE-UNIT AUDIT METRICS & THRESHOLDS:**
> The metrics, shortfall totals, and thresholds in this document are preserved strictly for historical record and development auditability.
> They reflect the raw Kaggle dataset's uncorrected `AC_POWER` scale (mislabeled as kW, resulting in reported fleet shortfall of ~42,520 kWh instead of the physically true 89.44 kWh, and an uncalibrated Plant 2 high-sun peer threshold of 1,119 kW).
>
> **Current, validated results in canonical kW and kWh are documented in:**
> - [Milestone 5 Physical Unit Audit](../../milestone_5_unit_audit.md)
> - [Milestone 5 Weather Enrichment & Model Comparison](../../milestone_5_weather_enrichment.md)
> - [Current Anomaly Intelligence Report](../../anomaly_report_milestone_5.json)

**Detection Code:** [`src/detect.py`](../../../src/detect.py)
**Loss Intelligence Code:** [`src/loss.py`](../../../src/loss.py)
**Historical Machine-Readable Report:** [`anomaly_report_milestone_4.json`](../../../reports/archive/superseded_pre_unit_audit/anomaly_report_milestone_4.json)
**Historical Figures:** `figures/milestone_4_inverter_shortfall_ranking.png`, `figures/milestone_4_synthetic_injection_timeline.png`

---

## 1. Executive Summary

Milestone 4 establishes a dual-baseline anomaly detection and energy-loss quantification engine.

By evaluating generation against both an **inverter-specific ML model** and a **capacity-normalized peer cohort benchmark**, the system detects both sudden mechanical dropouts and chronic array degradation without normalizing underperformance into the baseline.

Detection thresholds were calibrated strictly on the validation partition, persistence filtering was enforced to eliminate transient environmental fluctuations, and potential energy shortfall (kWh) was quantified across all 44 inverters. Controlled synthetic injection experiments verified 100% detection of persistent faults with 0% false triggering on transient 1- and 2-interval dips.

---

## 2. Dual-Baseline Detection Architecture

```
                                 [ Environmental Telemetry ]
                                     (Irradiance, Temp, Time)
                                                |
                     +--------------------------+--------------------------+
                     |                                                     |
                     v                                                     v
          [ Baseline 1: Inverter ML ]                             [ Baseline 2: Peer Cohort ]
          - Conditioned on (Weather, SOURCE_KEY)                  - Cross-inverter peer comparison
          - Learns inverter-specific curves                       - Normalizes by peak capacity C_i
          - Catches sudden acute dropouts                         - Catches chronic array degradation
                     |                                                     |
                     +--------------------------+--------------------------+
                                                |
                                    [ Residual Calculations ]
                                e = max(0, P_expected - P_actual)
                                                |
                                 [ Regime-Aware Thresholds ]
                                (Calibrated on Validation Set)
                                                |
                                 [ Persistence Filter >=3 ]
                               (Consecutive 15m; No Gap Bridge)
                                                |
                                                v
                                [ Actionable Candidate Anomalies ]
                                  & Potential Shortfall (kWh)
```

### Addressing Inverter Capacity Heterogeneity
- **Empirical Reality:** In Plant 1, inverter peak capacities are tightly clustered ($1,218.4 - 1,336.9\ \text{kW}$). In Plant 2, however, capacities range widely ($1,006.6 - 1,306.2\ \text{kW}$), with inverters such as `Quc1TzYxW2pYoWX` peaking ~20% lower than peers.
- **Fair Normalization Method:**
  1. Each inverter's effective capacity $C_i$ was estimated on the training split using its 99.5th percentile daylight generation.
  2. Observed power was normalized: $\tilde{P}_{i, t} = P_{i, t} / C_i$.
  3. The cohort baseline was computed as the plant median normalized power: $\tilde{P}_{\text{cohort}, t} = \text{median}_{j}(\tilde{P}_{j, t})$.
  4. The cohort expected power in kW was computed as:
     $$\hat{P}_{\text{cohort}, i, t} = \tilde{P}_{\text{cohort}, t} \times C_i$$
  This ensures smaller subarrays are not falsely flagged as permanently underperforming.

---

## 3. Residual Definition & Validation Threshold Calibration

### Residual Definitions
- **Positive Underperformance Residual**:
  $$\text{Residual} = \hat{P}_{\text{expected}} - P_{\text{actual}} \quad (\text{kW})$$
- **Guarded Relative Deviation**:
  $$\text{Relative Residual} = \frac{\hat{P}_{\text{expected}} - P_{\text{actual}}}{\hat{P}_{\text{expected}}} \quad (\text{for } \hat{P}_{\text{expected}} \ge 50.0\ \text{kW})$$
  (Intervals with $\hat{P} < 50\ \text{kW}$ are guarded to prevent division by near-zero at dawn/dusk).

### Validation Set Calibration
Thresholds were calibrated strictly on the validation partition (June 4 to June 11) using the 95th percentile of positive residuals across irradiance regimes ($\text{Low} \le 0.2$, $\text{Medium } 0.2-0.6$, $\text{High} > 0.6\ \text{kW/m}^2$):

| Plant | Irradiance Regime | Model Residual Threshold ($T_{\text{model}}$) | Cohort Residual Threshold ($T_{\text{cohort}}$) |
|---|---|---|---|
| **Plant 1** (`4135001`) | **Low** ($0.0 - 0.2\ \text{kW/m}^2$) | 30.0 kW | 30.0 kW |
| **Plant 1** (`4135001`) | **Medium** ($0.2 - 0.6\ \text{kW/m}^2$) | 91.5 kW | 61.6 kW |
| **Plant 1** (`4135001`) | **High** ($> 0.6\ \text{kW/m}^2$) | 200.1 kW | 137.0 kW |
| **Plant 2** (`4136001`) | **Low** ($0.0 - 0.2\ \text{kW/m}^2$) | 30.0 kW | 30.0 kW |
| **Plant 2** (`4136001`) | **Medium** ($0.2 - 0.6\ \text{kW/m}^2$) | 486.4 kW | 420.1 kW |
| **Plant 2** (`4136001`) | **High** ($> 0.6\ \text{kW/m}^2$) | 743.0 kW | 1,119.4 kW |

---

## 4. Persistence Filter & Telemetry Gap Discipline

To prevent false alarms from passing clouds, transient sensor noise, or inverter grid synchronization delays:
1. **Duration Requirement**: An alert requires at least **three consecutive valid 15-minute observations ($\ge 45$ minutes)** of threshold exceedance.
2. **Zero Gap Bridging**: If telemetry drops for $> 15$ minutes (e.g., an 8-hour communication outage), the persistence counter **immediately resets**. Missing intervals are never bridged or treated as zero generation.
3. **Episode Back-propagation**: Once a candidate run reaches 3 consecutive intervals, all intervals in that ongoing underperformance episode are flagged.

---

## 5. Potential Energy Shortfall & Inverter Prioritization

Energy shortfall for interval $t$ is calculated as:
$$\text{Shortfall}_t = \max(0, \hat{P}_t - P_{\text{actual}, t}) \times 0.25\ \text{hours} \quad (\text{kWh})$$
Nighttime intervals ($\text{IRRADIATION} \le 0$) have shortfall forced to $0.0\ \text{kWh}$.

### Out-of-Time Held-Out Test Evaluation Results
Evaluated over 16,236 test intervals (June 11 to June 17, 2020):

| Facility | Actual Generation | Expected Baseline | Total Potential Shortfall | Actionable Persistent Loss | Loss % | Flagged Hours |
|---|---|---|---|---|---|---|
| **Plant 1** (`4135001`) | 1,005,871.1 kWh | 995,819.2 kWh | 25,627.3 kWh | **6,643.3 kWh** | **0.67%** | 11.5 h |
| **Plant 2** (`4136001`) | 730,390.7 kWh | 729,107.1 kWh | 111,852.5 kWh | **35,876.8 kWh** | **4.92%** | 49.5 h |
| **Combined Total** | **1,736,261.7 kWh** | **1,724,926.3 kWh** | **137,479.8 kWh** | **42,520.1 kWh** | **2.47%** | **61.0 h** |

### Top 5 Inverters Ranked by Urgent Energy Loss
All top 4 urgent loss inverters reside in **Plant 2**:

| Rank | Plant | Inverter Key (`SOURCE_KEY`) | Actual (kWh) | Expected (kWh) | Persistent Loss (kWh) | Loss % | Flagged Hours |
|---|---|---|---|---|---|---|---|
| **#1** | Plant 2 | `Qf4GUc1pJu5T6c6` | 28,668.6 | 37,093.8 | **8,425.2 kWh** | **22.7%** | 11.25 h |
| **#2** | Plant 2 | `4UPUqMRk7TRMgml` | 30,865.2 | 37,465.1 | **6,599.9 kWh** | **17.6%** | 8.75 h |
| **#3** | Plant 2 | `oZ35aAeoifZaQzV` | 30,900.2 | 36,554.2 | **5,654.0 kWh** | **15.5%** | 7.50 h |
| **#4** | Plant 2 | `Mx2yZCDsyf6DPfv` | 32,382.9 | 35,660.8 | **3,277.9 kWh** | **9.2%** | 4.50 h |
| **#5** | Plant 1 | `1BY6WEcLGh8j5v7` | 41,013.9 | 43,868.1 | **2,854.2 kWh** | **6.5%** | 3.50 h |

---

## 6. Controlled Synthetic Injection Benchmark

To measure detector sensitivity without leaking test ground truth, controlled perturbations were injected into a separate test copy on June 12–14:

| Injection Event | Target Inverter | Nature of Injection | Duration | Expected Detector Response | Actual Result | Status |
|---|---|---|---|---|---|---|
| **Event 1** | `1BY6WEcLGh8j5v7` | Complete Inverter Trip ($P = 0.0\ \text{kW}$) | 4 intervals (60m) | Trigger Persistent Alert | **Detected = True** | **100% Recall** |
| **Event 2** | `1IF53ai7Xc0U56Y` | Partial Derate (50% power reduction) | 6 intervals (90m) | Trigger Persistent Alert | **Detected = True** | **100% Recall** |
| **Event 3** | `3PZuoBAID5Wc2HD` | Passing Cloud Dip (80% drop) | 1 interval (15m) | Reject (Do Not Trigger) | **Rejected = True** | **0% False Trigger** |
| **Event 4** | `7JYdWkrLSPkdwr4` | Transient Dip (80% drop) | 2 intervals (30m) | Reject (Do Not Trigger) | **Rejected = True** | **0% False Trigger** |

---

## 7. Automated Test Suite Verification

All 26 unit tests across all four milestones pass in `pytest` with zero warnings:

```bash
pytest -v
```
```
tests/test_anomaly_detection.py::test_normal_generation_zero_shortfall PASSED [  3%]
tests/test_anomaly_detection.py::test_isolated_dip_rejected_by_persistence_filter PASSED [  7%]
tests/test_anomaly_detection.py::test_persistent_drop_triggers_anomaly PASSED [ 11%]
tests/test_anomaly_detection.py::test_gap_bridging_prevention PASSED     [ 15%]
tests/test_anomaly_detection.py::test_nighttime_zero_shortfall PASSED    [ 19%]
tests/test_anomaly_detection.py::test_energy_shortfall_calculation PASSED [ 23%]
tests/test_anomaly_detection.py::test_peer_cohort_capacity_normalization PASSED [ 26%]
tests/test_data_pipeline.py::test_timestamp_parsing_and_types PASSED     [ 30%]
tests/test_data_pipeline.py::test_row_count_preservation_and_no_multiplication PASSED [ 34%]
tests/test_data_pipeline.py::test_weather_sensor_key_no_collision PASSED [ 38%]
tests/test_data_pipeline.py::test_missing_weather_tracking PASSED        [ 42%]
tests/test_data_pipeline.py::test_feature_engineering_integrity PASSED   [ 46%]
tests/test_data_pipeline.py::test_target_leakage_prevention PASSED       [ 50%]
tests/test_data_pipeline.py::test_pipeline_determinism PASSED            [ 53%]
tests/test_data_pipeline.py::test_processed_artifacts_exist_and_load PASSED [ 57%]
tests/test_model_training.py::test_chronological_split_strict_ordering PASSED [ 61%]
tests/test_model_training.py::test_group_integrity_same_timestamp_cohesion PASSED [ 65%]
tests/test_model_training.py::test_prohibited_leakage_features PASSED    [ 69%]
tests/test_model_training.py::test_unseen_categorical_safety PASSED      [ 73%]
tests/test_model_training.py::test_model_artifact_load_and_predict PASSED [ 76%]
tests/test_model_training.py::test_evaluation_metric_properties PASSED   [ 80%]
tests/test_raw_data_audit.py::test_file_row_counts_and_nulls PASSED      [ 84%]
tests/test_raw_data_audit.py::test_inverter_and_sensor_cardinality PASSED [ 88%]
tests/test_raw_data_audit.py::test_key_uniqueness_no_duplicates PASSED   [ 92%]
tests/test_raw_data_audit.py::test_join_integrity_no_row_multiplication PASSED [ 96%]
tests/test_raw_data_audit.py::test_no_ground_truth_fault_labels PASSED   [100%]

============================= 26 passed in 4.63s ==============================
```

---

## 8. Critical Domain Limitations & Non-Claims

1. **Shortfall is Potential Loss, Not Guaranteed Recoverable Energy**:
   - The reported $42,520.1\ \text{kWh}$ persistent shortfall represents generation unperformed relative to weather expectations. Inverter clipping, soiling, localized string shading, and grid operator curtailment all manifest as generation shortfall. It must not be marketed as guaranteed recovered revenue.
2. **No Annual Extrapolation**:
   - Telemetry covers only 34 early-summer days. Extrapolating these shortfall numbers to annual loss estimates would introduce massive seasonal bias (e.g. winter sun angles and monsoon seasons are unobserved).
3. **No Hardware Diagnosis**:
   - Identified alerts are strictly **candidate underperformance events**. Physical cause confirmation requires on-site inspection logs, thermographic drone scans, or inverter internal fault telemetry.
