# Milestone 3: Regression Model Training & Evaluation Report (SUPERSEDED)
**Project:** Adaptive Solar Performance & Loss Intelligence
**Date:** October 24, 2026 (Archived Post-Milestone 5)
**Status:** **SUPERSEDED ARCHIVE FILE — DO NOT USE FOR CURRENT PERFORMANCE BENCHMARKS**

> [!WARNING]
> **SUPERSEDED PRE-UNIT AUDIT METRICS:**
> The metrics, evaluations, and figures in this document are preserved strictly for historical record and development auditability.
> They reflect the raw Kaggle dataset's uncorrected `AC_POWER` scale (mislabeled as kW, but physically representing Watts, resulting in a 1,000× numeric scale distortion e.g., MAE ~105 kW instead of 0.105 kW).
>
> **Current, validated results in canonical kW and kWh are documented in:**
> - [Milestone 5 Physical Unit Audit](../../milestone_5_unit_audit.md)
> - [Milestone 5 Weather Enrichment & Model Comparison](../../milestone_5_weather_enrichment.md)
> - [Current Model Metrics Comparison JSON](../../metrics_milestone_5_comparison.json)

**Training Pipeline:** [`src/train.py`](../../../src/train.py)
**Historical Metrics JSON:** [`metrics_milestone_3.json`](../../../reports/archive/superseded_pre_unit_audit/metrics_milestone_3.json)

---

## 1. Executive Summary

Milestone 3 establishes expected AC power baseline models using strictly chronological partitions, zero target leakage, and fair model comparisons.

Models estimate expected AC power ($P_{\text{expected}}$) conditional on contemporaneous on-site weather (`IRRADIATION`, `AMBIENT_TEMPERATURE`, `MODULE_TEMPERATURE`, `TEMP_DIFF`), cyclical diurnal/seasonal timing, and inverter identity. Models were trained on the earliest 60% of unique daylight timestamps, selected on the subsequent 20% validation split, and evaluated on the final 20% held-out test split.

---

## 2. Chronological Split Boundaries & Row Counts

Splitting was conducted strictly across **sorted unique timestamps** ($1,871$ daylight intervals), ensuring all concurrent inverter records for any given timestamp remain together in the same partition:

| Partition | Share | Unique Timestamps | Timestamp Range | Row Count | Purpose & Integrity Boundary |
|---|---|---|---|---|---|
| **Train** | 60.0% | 1,122 | **2020-05-15 05:45:00** to **2020-06-04 11:15:00** | **44,966** | Pipeline fitting (StandardScaler, OneHotEncoder, Estimators) |
| **Validation** | 20.0% | 374 | **2020-06-04 11:30:00** to **2020-06-11 07:00:00** | **15,896** | Model comparison & hyperparameter selection |
| **Test (Out-of-Time)** | 20.0% | 375 | **2020-06-11 07:15:00** to **2020-06-17 18:45:00** | **16,236** | Final unbiased evaluation of chosen model |
| **Total Daylight** | 100.0% | 1,871 | 2020-05-15 05:45:00 to 2020-06-17 18:45:00 | 77,098 | $100\%$ account of operational records |

> [!IMPORTANT]
> There is **zero overlap** between partitions:
> $$\max(T_{\text{train}}) < \min(T_{\text{val}}) \quad \text{and} \quad \max(T_{\text{val}}) < \min(T_{\text{test}})$$

---

## 3. Model Benchmark & Validation Selection

Candidate models were trained strictly on the training partition and compared on the validation partition:

| Model Architecture | Preprocessing / Encoders | Val MAE (kW) | Val RMSE (kW) | Val $R^2$ | Val WAPE (%) | Training Time |
|---|---|---|---|---|---|---|
| **DummyRegressor** (Mean Baseline) | None (constant mean prediction) | 354.78 | 403.83 | -0.0051 | 73.79% | < 0.1s |
| **Ridge Regression** ($\alpha = 10.0$) | `StandardScaler` + `OneHotEncoder(handle_unknown='ignore')` | 148.09 | 254.10 | 0.6021 | 30.80% | ~0.3s |
| **HistGradientBoostingRegressor** | Passthrough nums + `OneHotEncoder(handle_unknown='ignore')` | 109.11 | 213.79 | 0.7183 | 22.69% | ~1.2s |
| **RandomForestRegressor** ($100$ trees, depth $16$) | Passthrough nums + `OneHotEncoder(handle_unknown='ignore')` | **105.20** | **212.14** | **0.7226** | **21.88%** | ~3.8s |

### Model Selection Decision:
`RandomForestRegressor` achieved the lowest Validation MAE (**105.20 kW**) and highest $R^2$ (**0.7226**), closely matched by `HistGradientBoostingRegressor` (**109.11 kW**, $R^2$ **0.7183**). Both nonlinear models dramatically outperformed linear Ridge regression ($\Delta \text{MAE} \approx 43\ \text{kW}$) and the Dummy baseline ($\Delta \text{MAE} \approx 250\ \text{kW}$).

---

## 4. Held-Out Out-of-Time Test Evaluation

Once `RandomForestRegressor` was selected, all models were evaluated on the held-out test partition (unseen future week: June 11 to June 17):

| Model (Evaluated on Test Split) | Test MAE (kW) | Test RMSE (kW) | Test $R^2$ | Test WAPE (%) | Mean Residual (kW) |
|---|---|---|---|---|---|
| **Dummy (Mean Baseline)** | 290.13 | 340.14 | -0.0614 | 67.83% | +84.50 |
| **Ridge (Regularized Linear)** | 112.01 | 181.39 | 0.6982 | 26.18% | -10.56 |
| **HistGradientBoosting** | **69.85** | **164.40** | **0.7521** | **16.33%** | **-0.89** |
| **RandomForest (Selected Model)** | **70.53** | **170.39** | **0.7336** | **16.49%** | **-1.04** |

On unseen future data, the nonlinear models generalized with Test MAE $\approx 70\ \text{kW}$ (an error of only $\approx 16.4\%$ relative to active daylight generation) and near-zero overall residual bias ($-1.04\ \text{kW}$).

---

## 5. Diagnostic Performance Slices (Selected Model on Test Set)

### A. Performance by Solar Plant
A significant disparity emerges between the two plants:

| Facility | Sample Size ($n$) | Test MAE (kW) | Test RMSE (kW) | Test $R^2$ | Test WAPE (%) |
|---|---|---|---|---|---|
| **Plant 1** (`4135001`) | 7,986 | **30.08** | **67.47** | **0.9627** | **5.97%** |
| **Plant 2** (`4136001`) | 8,250 | **109.70** | **229.63** | **0.3814** | **30.98%** |

- **Plant 1** exhibits high modeling fidelity ($R^2 = 0.9627$, $\text{WAPE} = 5.97\%$). Inverters track irradiance closely with minimal anomalous scatter.
- **Plant 2** displays substantially higher error ($\text{MAE} = 109.70\ \text{kW}$, $R^2 = 0.3814$). This elevated error is driven by high inter-inverter generation variance, multi-day dropouts, and widespread inverter-level underperformance.

---

### B. Performance by Irradiance Regime
Evaluating errors across solar irradiance levels reveals where errors originate:

| Irradiance Regime ($\text{kW/m}^2$) | Intervals ($n$) | Test MAE (kW) | Test RMSE (kW) | Test $R^2$ | Test WAPE (%) | Mean Generation |
|---|---|---|---|---|---|---|
| **Low ($0.0 - 0.2$)** | 6,050 | **7.32** | **14.00** | **0.9772** | **6.35%** | 115.3 kW |
| **Medium ($0.2 - 0.6$)** | 7,788 | **69.08** | **144.49** | **0.3767** | **12.74%** | 542.4 kW |
| **High ($> 0.6$)** | 2,398 | **234.74** | **358.16** | **0.1137** | **27.80%** | 844.3 kW |

- **Low Irradiance**: Low error ($\text{MAE} = 7.32\ \text{kW}$). Morning and evening ramp-up curves are modeled accurately.
- **High Irradiance**: High absolute error ($\text{MAE} = 234.74\ \text{kW}$). At solar noon, inverters experience thermal derating, capacity ceiling clipping, and severe divergence between healthy and underperforming inverters.

---

### C. Inverter-Level Residual Diagnostics
Residual is defined as:
$$\text{Residual} = \hat{P}_{\text{expected}} - P_{\text{actual}}$$
- **$\text{Residual} > 0$**: Inverter generated *less* power than expected (candidate underperformance).
- **$\text{Residual} \approx 0$**: Inverter closely matched expected physical generation.
- **$\text{Residual} < 0$**: Inverter generated *more* power than expected baseline.

#### Top 5 Highest-Error Inverters in Test Set (Underperformance Candidates)
All top high-error inverters belong to **Plant 2**:

| Plant | Inverter Key (`SOURCE_KEY`) | Test MAE (kW) | Mean Residual (kW) | Diagnosis / Behavior |
|---|---|---|---|---|
| Plant 2 | `Qf4GUc1pJu5T6c6` | **160.55** | **+121.28** | Chronic Severe Underperformance (averages 121 kW below model expectations) |
| Plant 2 | `Mx2yZCDsyf6DPfv` | **141.24** | **+87.29** | Chronic Underperformance (averages 87 kW below model expectations) |
| Plant 2 | `4UPUqMRk7TRMgml` | **140.17** | **+89.60** | Chronic Underperformance (averages 90 kW below model expectations) |
| Plant 2 | `oZ35aAeoifZaQzV` | **139.84** | **+88.50** | Chronic Underperformance (averages 88 kW below model expectations) |
| Plant 2 | `LYwnQax7tkwH5Cb` | **123.67** | **-96.69** | High-Yield Outlier (consistently outperforms plant cohort average) |

#### Top 5 Lowest-Error Inverters in Test Set (Cohort Baselines)
All top baseline-consistent inverters belong to **Plant 1**:

| Plant | Inverter Key (`SOURCE_KEY`) | Test MAE (kW) | Mean Residual (kW) | Diagnosis / Behavior |
|---|---|---|---|---|
| Plant 1 | `YxYtjZvoooNbGkE` | **23.49** | **-3.30** | Benchmark Baseline Inverter |
| Plant 1 | `sjndEbLyjtCKgGv` | **23.66** | **-9.65** | Benchmark Baseline Inverter |
| Plant 1 | `ih0vzX44oOqAx2f` | **23.68** | **-0.46** | Benchmark Baseline Inverter |
| Plant 1 | `ZoEaEvLYb1n2sOq` | **24.14** | **-4.42** | Benchmark Baseline Inverter |
| Plant 1 | `7JYdWkrLSPkdwr4` | **24.65** | **-7.09** | Benchmark Baseline Inverter |

---

## 6. Important Methodological Limitations

1. **Short Observation Horizon (~34 Days)**:
   - Data spans May 15 to June 17, 2020. The models learn early-summer solar characteristics and have not been validated across seasonal transitions (winter/monsoon).
2. **Absence of Ground-Truth Fault Labels**:
   - The datasets contain operational telemetry only. Large residuals identify **candidate underperformance events** (which could stem from soiling, localized shading, string disconnection, or inverter clipping), not confirmed hardware breakdown.
3. **Risk of Learning Underperformance as Normal**:
   - When training an entity-aware model (e.g., conditioning on `SOURCE_KEY`), if an inverter underperformed throughout the 24-day training period, the model could fit a lower expected baseline for that inverter, partially normalizing the fault. In Milestone 4, peer-cohort relative benchmarking will be used to counteract this bias.
4. **Plant 2 Heterogeneity**:
   - Plant 2 displays severe operational anomalies (8.77-day telemetry dropout across 4 inverters, large inter-inverter spreads). Modeling Plant 1 and Plant 2 with a single unified model requires conditioning on `PLANT_ID`.

---

## 7. Milestone 3 Verification Checklist

- [x] Splitting performed on sorted unique timestamps with 60/20/20 proportions.
- [x] Observations from the same timestamp kept strictly together.
- [x] Preprocessing and models fitted exclusively on training split.
- [x] Model selection based strictly on validation split performance.
- [x] Evaluation conducted on held-out test split only after selection.
- [x] Zero target leakage: `AC_POWER`, `DC_POWER`, `DAILY_YIELD`, `TOTAL_YIELD` strictly excluded from $X$.
- [x] Daylight isolation enforced (`IRRADIATION > 0`).
- [x] Performance evaluated by plant, irradiance range, and inverter.
- [x] 19 automated unit tests passing in `pytest`.
- [x] Model artifact saved to `models/best_solar_model.joblib`.
- [x] Machine-readable metrics recorded in `reports/metrics_milestone_3.json`.
