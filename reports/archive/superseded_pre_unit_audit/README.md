# Superseded Pre-Unit-Audit Archive

This directory preserves historical reports, JSON metric dumps, and diagnostic plots generated during **Milestone 3 (Model Training)** and **Milestone 4 (Anomaly Intelligence)** prior to the comprehensive physical unit audit in **Milestone 5**.

---

## Why Were These Artifacts Superseded?

In the original Kaggle dataset release (*Solar Power Generation Data*, Rahman 2020), the `AC_POWER` column was labeled in kilowatts (`kW`). However, empirical engineering validation against manufacturer specifications (22 Growatt MIC 1500TL-X to 2500TL-X inverters rated 1.5–2.5 kW each, ~56.32 kWp total installed DC capacity per plant) revealed that raw numeric values were recorded in **Watts (W)**, not kW.

### Impact of Pre-Unit Scale:
1. **Model Evaluation Metrics (Milestone 3)**:
   - Reported validation MAE was **~105.20** and RMSE was **~212.14**.
   - After canonical unit correction (`AC_POWER_KW = AC_POWER / 1000.0`), the true physical errors are **MAE = 0.1055 kW (105.5 W)** and **RMSE = 0.1704 kW (170.4 W)**.
2. **Operational Energy Shortfall (Milestone 4)**:
   - Reported fleet persistent shortfall was **~42,520 kWh**.
   - After canonical unit conversion, the true physical persistent shortfall over the 7-day held-out test window is **89.44 kWh (5.19% loss)**.
3. **Plant 2 High-Irradiance Cohort Threshold**:
   - In Milestone 4, severe multi-inverter zero-power dropouts during high irradiance in the validation split distorted the unconditioned 95th percentile cohort threshold to **1,119 W (1.119 kW)**.
   - In Milestone 5, calibrating cohort thresholds exclusively on generating inverters ($P > 0.05$ kW under high sun) reduced the cohort threshold to **0.0846 kW (84.6 W)**, restoring high-sensitivity string derate detection.

---

## Archived Artifacts

- [`milestone_3_model_evaluation.md`](../../../reports/archive/superseded_pre_unit_audit/milestone_3_model_evaluation.md): Preliminary regression benchmark report with pre-unit values.
- [`milestone_4_anomaly_evaluation.md`](../../../reports/archive/superseded_pre_unit_audit/milestone_4_anomaly_evaluation.md): Preliminary dual-baseline anomaly detection report with pre-unit shortfall figures.
- [`metrics_milestone_3.json`](../../../reports/archive/superseded_pre_unit_audit/metrics_milestone_3.json): Machine-readable metrics from pre-unit model runs.
- [`anomaly_report_milestone_4.json`](../../../reports/archive/superseded_pre_unit_audit/anomaly_report_milestone_4.json): Machine-readable detection summary from pre-unit runs.
- `figures/milestone_4_inverter_shortfall_ranking.png`: Diagnostic bar chart with pre-unit shortfall scales.
- `figures/milestone_4_synthetic_injection_timeline.png`: Time series plot with pre-unit power scales.

---

## Current Canonical Results

For all current, physically grounded results, consult:
1. **[Milestone 5 Unit Audit Report](../../milestone_5_unit_audit.md)**: Full physical and empirical proof of inverter capacities and canonical kW units.
2. **[Milestone 5 Weather Enrichment Report](../../milestone_5_weather_enrichment.md)**: Rigorous evaluation of baseline vs Open-Meteo enriched models.
3. **[Current Model Metrics Comparison JSON](../../metrics_milestone_5_comparison.json)**: Production model benchmark metrics.
4. **[Current Anomaly Intelligence Report JSON](../../anomaly_report_milestone_5.json)**: Canonical operational shortfall and inverter prioritization rankings.
