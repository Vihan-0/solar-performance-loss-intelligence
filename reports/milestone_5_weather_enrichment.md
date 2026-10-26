# Milestone 5 — External Weather Enrichment & Model Comparison Report

## 1. Executive Summary

This report evaluates whether incorporating mesoscale external historical reanalysis weather from Open-Meteo's Archive API improves upon our onsite-sensor regression baseline for predicting solar inverter active power ($P_{\text{AC, kW}}$).

Key findings:
1. **Onsite Baseline Supremacy:** The Baseline model (RandomForest on onsite pyranometers, module temperature, and cyclical timing) achieved a Validation MAE of **$0.1055\,\text{kW}$** ($105.5\,\text{W}$) and Test MAE of **$0.0704\,\text{kW}$** ($70.4\,\text{W}$).
2. **External Weather Adds Noise:** Enriching the feature matrix with 6 Open-Meteo variables (`cloud_cover`, `relative_humidity_2m`, `precipitation`, `wind_speed_10m`, `temperature_2m`, `shortwave_radiation_instant`) increased Validation MAE to **$0.1076\,\text{kW}$** ($+1.99\%$ error).
3. **Architectural Decision:** In accordance with Occam's razor and project rules ("do not assume weather enrichment will improve accuracy; retain the simpler model if it does not"), **the simpler baseline model is retained as production canonical**.

---

## 2. External Weather Retrieval & Alignment Methodology

### A. Data Retrieval Specifications
- **Provider:** Open-Meteo Historical Weather API (`https://archive-api.open-meteo.com/v1/archive`).
- **Location:** Approximate literature coordinates ($14.35^\circ\,\text{N}, 77.49^\circ\,\text{E}$ in the Kottapalle area, Karnataka).
- **Timezone:** `Asia/Kolkata` ($+05:30$).
- **Observation Horizon:** 2020-05-15 00:00 through 2020-06-17 23:00 ($816$ hourly observations).
- **Retrieved Variables:**
  - `temperature_2m` ($^\circ\text{C}$)
  - `relative_humidity_2m` ($\%$)
  - `precipitation` ($\text{mm}$, hourly sum)
  - `cloud_cover` ($\%$, total sky cover)
  - `wind_speed_10m` ($\text{km/h}$ and $\text{m/s}$)
  - `shortwave_radiation_instant` ($\text{W/m}^2$, standardized to $\text{kW/m}^2$)

### B. Time Semantics & Alignment Protocol
- **Temporal Resolution Mismatch:** The solar array records inverter generation every 15 minutes, whereas reanalysis weather is delivered hourly.
- **Alignment Rule:** Each 15-minute generation record at timestamp $t$ was joined to its reference hour via $t_{\text{ref}} = t.\text{floor}(\text{'1h'})$.
- **No Fabricated Precision:** We strictly avoided spline interpolation or fabricating intra-hour sub-grid microfluctuations that do not exist in hourly reanalysis.
- **Cardinality Assurance:** Join cardinality was strictly many-to-one, preserving $100.0\%$ of generation records ($68,778 / 68,778$ in Plant 1 and $67,698 / 67,698$ in Plant 2) with zero row multiplication.

---

## 3. Empirical Model Benchmark on Identical Splits

Models were trained and evaluated on identical chronological partitions ($60\%$ Train, $20\%$ Validation, $20\%$ Out-of-Time Test) across $77,098$ daylight observations:

| Model Architecture | Feature Set | Val MAE (kW) | Val RMSE (kW) | Val $R^2$ | Val WAPE (%) | Test MAE (kW) | Test RMSE (kW) | Test $R^2$ |
|---|---|---|---|---|---|---|---|---|
| **Ridge Regression** | Baseline (10 features) | $0.1481$ | $0.2541$ | $0.6021$ | $30.80\%$ | $0.1120$ | $0.1814$ | $0.6982$ |
| **Ridge Regression** | Enriched (16 features) | $0.1498$ | $0.2517$ | $0.6096$ | $31.16\%$ | $0.1158$ | $0.1817$ | $0.6972$ |
| **HistGradientBoosting** | Baseline (10 features) | $0.1092$ | $0.2139$ | $0.7181$ | $22.70\%$ | $0.0699$ | $0.1646$ | $0.7515$ |
| **HistGradientBoosting** | Enriched (16 features) | $0.1087$ | $0.2155$ | $0.7138$ | $22.61\%$ | $0.0735$ | $0.1634$ | $0.7550$ |
| **RandomForest** | **Baseline (10 features)** | **$\mathbf{0.1055}$** | **$\mathbf{0.2127}$** | **$\mathbf{0.7210}$** | **$\mathbf{21.95\%}$** | **$\mathbf{0.0704}$** | **$\mathbf{0.1704}$** | **$\mathbf{0.7337}$** |
| **RandomForest** | Enriched (16 features) | $0.1076$ | $0.2146$ | $0.7161$ | $22.37\%$ | $0.0708$ | $0.1660$ | $0.7473$ |

---

## 4. Why Did External Weather Not Improve Onsite Predictions?

1. **Microclimate vs. Regional Grid Cells:** Open-Meteo reanalysis operates over a spatial resolution of $\approx 10\text{–}25\,\text{km}$. A solar PV array's immediate output is governed by microscale in-plane irradiance and cell temperature.
2. **Onsite Sensor Directness:** The onsite pyranometer (`IRRADIATION`) and back-of-module thermocouple (`MODULE_TEMPERATURE`) directly measure the thermodynamic forces determining photovoltaic electron excitation.
3. **Interpolation Latency:** Hourly weather variables cannot capture 15-minute transient cloud movements over the panels. Adding regional cloud cover and 10m wind speed introduced irrelevant degrees of freedom that slightly degraded generalization.

---

## 5. Conclusion & Production Architecture

The **Baseline RandomForest pipeline** is retained as our primary expected-power estimator. The external weather pipeline remains fully integrated in `src/weather.py` and reproducible via `scripts/fetch_historical_weather.py` for regional benchmarking and sanity checks.
