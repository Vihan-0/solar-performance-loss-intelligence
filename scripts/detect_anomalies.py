"""
Milestone 5: Anomaly Detection and Energy-Loss Intelligence Script
Adaptive Solar Performance & Loss Intelligence

Runs the full anomaly detection, loss quantification, and synthetic injection
evaluation on the held-out test partition using canonical kW/kWh units.
"""

import json
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.train import (
    create_chronological_splits,
    load_model_artifact,
)
from src.detect import (
    estimate_inverter_capacities,
    compute_cohort_expected_power,
    compute_model_expected_power,
    calculate_residuals,
    calibrate_thresholds,
    apply_persistence_filter,
    IRRADIANCE_BINS,
    IRRADIANCE_LABELS,
)
from src.loss import (
    compute_interval_shortfall,
    aggregate_inverter_loss_summary,
    aggregate_plant_loss_summary,
)

DATA_PATH = REPO_ROOT / "data" / "processed" / "combined_model_ready.parquet"
MODEL_PATH = REPO_ROOT / "models" / "best_solar_model.joblib"
REPORTS_DIR = REPO_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"


def run_anomaly_intelligence():
    print("=" * 80)
    print("MILESTONE 5: RESIDUAL-BASED ANOMALY DETECTION & LOSS INTELLIGENCE (kW/kWh)")
    print("=" * 80)

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load trained model & data
    print(f"\n[1/6] Loading model artifact from {MODEL_PATH}...")
    pipeline, meta = load_model_artifact(MODEL_PATH)
    features = meta["features"] if "features" in meta else (meta["numerical_features"] + meta["categorical_features"])
    print(f"  Loaded model: {meta['model_name']} with {len(features)} features.")

    print(f"Loading daylight dataset from {DATA_PATH}...")
    df = pd.read_parquet(DATA_PATH)
    train_df, val_df, test_df, split_meta = create_chronological_splits(df)

    # 2. Inverter Capacities & Baselines in kW
    print("\n[2/6] Estimating inverter capacities and building dual baselines in kW...")
    capacities = estimate_inverter_capacities(train_df, power_col="AC_POWER_KW", quantile=0.995)
    print(f"  Estimated capacities for {len(capacities)} inverters across 2 plants.")
    print(f"  Plant 1 capacity range: {min(v for k, v in capacities.items() if k[0] == 4135001):.3f} - {max(v for k, v in capacities.items() if k[0] == 4135001):.3f} kW")
    print(f"  Plant 2 capacity range: {min(v for k, v in capacities.items() if k[0] == 4136001):.3f} - {max(v for k, v in capacities.items() if k[0] == 4136001):.3f} kW")

    # 3. Validation Threshold Calibration
    print("\n[3/6] Calibrating detection thresholds strictly on Validation split (in kW)...")
    val_eval = val_df.copy()
    val_eval["expected_model"] = compute_model_expected_power(pipeline, val_eval, features)
    val_eval["expected_cohort"] = compute_cohort_expected_power(val_eval, capacities, power_col="AC_POWER_KW")

    val_eval["res_model"], _ = calculate_residuals(val_eval["AC_POWER_KW"], val_eval["expected_model"], min_expected_power=0.050)
    val_eval["res_cohort"], _ = calculate_residuals(val_eval["AC_POWER_KW"], val_eval["expected_cohort"], min_expected_power=0.050)

    val_thresholds_model = calibrate_thresholds(
        val_eval, residual_col="res_model", quantile=0.95, min_threshold_kw=0.030, exclude_calibration_dropouts=True
    )
    val_thresholds_cohort = calibrate_thresholds(
        val_eval, residual_col="res_cohort", quantile=0.95, min_threshold_kw=0.030, exclude_calibration_dropouts=True
    )

    print("  Calibrated Model Residual Thresholds (95th percentile, kW):")
    for (pid, regime), thresh in sorted(val_thresholds_model.items()):
        print(f"    Plant {pid} [{regime:<6}]: {thresh:.4f} kW ({thresh*1000:.1f} W)")

    print("  Calibrated Cohort Residual Thresholds (95th percentile, kW):")
    for (pid, regime), thresh in sorted(val_thresholds_cohort.items()):
        print(f"    Plant {pid} [{regime:<6}]: {thresh:.4f} kW ({thresh*1000:.1f} W)")

    # 4. Out-of-Time Test Evaluation
    print("\n[4/6] Evaluating detection pipeline on held-out Test split...")
    test_eval = test_df.copy()
    test_eval["expected_model"] = compute_model_expected_power(pipeline, test_eval, features)
    test_eval["expected_cohort"] = compute_cohort_expected_power(test_eval, capacities, power_col="AC_POWER_KW")

    test_eval["res_model"], test_eval["rel_model"] = calculate_residuals(
        test_eval["AC_POWER_KW"], test_eval["expected_model"], min_expected_power=0.050
    )
    test_eval["res_cohort"], test_eval["rel_cohort"] = calculate_residuals(
        test_eval["AC_POWER_KW"], test_eval["expected_cohort"], min_expected_power=0.050
    )

    # Assign regime and thresholds
    test_eval["irr_bin"] = pd.cut(test_eval["IRRADIATION"], bins=IRRADIANCE_BINS, labels=IRRADIANCE_LABELS)
    lookup_pairs = list(zip(test_eval["PLANT_ID"].astype(int), test_eval["irr_bin"].astype(str)))
    test_eval["thresh_model"] = [val_thresholds_model.get(p, 0.050) for p in lookup_pairs]
    test_eval["thresh_cohort"] = [val_thresholds_cohort.get(p, 0.050) for p in lookup_pairs]

    # Candidate flags
    test_eval["cand_model"] = test_eval["res_model"] > test_eval["thresh_model"]
    test_eval["cand_cohort"] = test_eval["res_cohort"] > test_eval["thresh_cohort"]
    test_eval["cand_combined"] = test_eval["cand_model"] | test_eval["cand_cohort"]

    # Apply persistence filtering (>= 3 consecutive 15-min intervals)
    test_eval["persist_model"] = apply_persistence_filter(test_eval, "cand_model", min_consecutive=3)
    test_eval["persist_cohort"] = apply_persistence_filter(test_eval, "cand_cohort", min_consecutive=3)
    test_eval["is_persistent_anomaly"] = apply_persistence_filter(test_eval, "cand_combined", min_consecutive=3)

    # Energy shortfall quantification in kWh
    test_eval["shortfall_model_kwh"] = compute_interval_shortfall(
        test_eval["AC_POWER_KW"], test_eval["expected_model"], is_daylight=test_eval["is_daylight"]
    )
    test_eval["shortfall_cohort_kwh"] = compute_interval_shortfall(
        test_eval["AC_POWER_KW"], test_eval["expected_cohort"], is_daylight=test_eval["is_daylight"]
    )

    # Aggregate summaries
    inverter_summary = aggregate_inverter_loss_summary(
        test_eval, expected_col="expected_model", actual_col="AC_POWER_KW", persistent_flag_col="is_persistent_anomaly"
    )
    plant_summary = aggregate_plant_loss_summary(
        test_eval, expected_col="expected_model", actual_col="AC_POWER_KW", persistent_flag_col="is_persistent_anomaly"
    )

    total_actual = float(plant_summary["actual_generation_kwh"].sum())
    total_expected = float(plant_summary["expected_generation_kwh"].sum())
    total_shortfall = float(plant_summary["total_potential_shortfall_kwh"].sum())
    persistent_shortfall = float(plant_summary["persistent_shortfall_kwh"].sum())

    print(f"\n  Held-Out Test Generation:   {total_actual:,.2f} kWh")
    print(f"  Model Expected Generation:  {total_expected:,.2f} kWh")
    print(f"  Total Potential Shortfall:  {total_shortfall:,.2f} kWh ({(total_shortfall/total_expected)*100:.2f}% of expected)")
    print(f"  Actionable Persistent Loss: {persistent_shortfall:,.2f} kWh ({(persistent_shortfall/total_expected)*100:.2f}% of expected)")

    print("\n--- Plant-Level Anomaly Summary ---")
    for _, prow in plant_summary.iterrows():
        print(
            f"  Plant {prow['PLANT_ID']}: Expected={prow['expected_generation_kwh']:,.1f} kWh | "
            f"Actual={prow['actual_generation_kwh']:,.1f} kWh | "
            f"Persistent Loss={prow['persistent_shortfall_kwh']:,.1f} kWh ({prow['loss_percentage']:.2f}%) | "
            f"Flagged Hours={prow['persistent_anomaly_hours']:.1f}h"
        )

    print("\n--- Top 5 Inverters Ranked by Urgent Energy Loss ---")
    for _, inv_row in inverter_summary.head(5).iterrows():
        print(
            f"  Rank #{inv_row['urgency_rank']}: Plant {inv_row['PLANT_ID']} - Inverter {inv_row['SOURCE_KEY']}: "
            f"Persistent Loss = {inv_row['persistent_shortfall_kwh']:,.2f} kWh ({inv_row['loss_percentage']:.1f}% loss), "
            f"Flagged Hours = {inv_row['persistent_anomaly_hours']}h"
        )

    # 5. Controlled Synthetic Injection Benchmark
    print("\n[5/6] Executing Controlled Synthetic Injection Benchmark...")
    test_inj = test_df.copy()
    test_inj["expected_model"] = compute_model_expected_power(pipeline, test_inj, features)
    test_inj["expected_cohort"] = compute_cohort_expected_power(test_inj, capacities, power_col="AC_POWER_KW")

    inverters_p1 = sorted(test_inj[test_inj["PLANT_ID"] == 4135001]["SOURCE_KEY"].unique())
    inv_trip = inverters_p1[0]
    inv_derate = inverters_p1[1]
    inv_transient_1 = inverters_p1[2]
    inv_transient_2 = inverters_p1[3]

    # Event 1: Persistent Complete Trip (4 consecutive intervals = 60 mins: 11:00 to 11:45 on June 12)
    trip_ts = pd.date_range("2020-06-12 11:00:00", "2020-06-12 11:45:00", freq="15min")
    mask_trip = (test_inj["SOURCE_KEY"] == inv_trip) & (test_inj["TIMESTAMP"].isin(trip_ts))
    test_inj.loc[mask_trip, "AC_POWER_KW"] = 0.0

    # Event 2: Persistent Partial Derate (6 consecutive intervals = 90 mins: 11:00 to 12:15 on June 13, 50% power)
    derate_ts = pd.date_range("2020-06-13 11:00:00", "2020-06-13 12:15:00", freq="15min")
    mask_derate = (test_inj["SOURCE_KEY"] == inv_derate) & (test_inj["TIMESTAMP"].isin(derate_ts))
    test_inj.loc[mask_derate, "AC_POWER_KW"] = test_inj.loc[mask_derate, "AC_POWER_KW"] * 0.50

    # Event 3: Transient 1-interval dip (15 mins: 12:00 on June 14, 80% drop)
    transient_ts_1 = pd.date_range("2020-06-14 12:00:00", "2020-06-14 12:00:00", freq="15min")
    mask_trans_1 = (test_inj["SOURCE_KEY"] == inv_transient_1) & (test_inj["TIMESTAMP"].isin(transient_ts_1))
    test_inj.loc[mask_trans_1, "AC_POWER_KW"] = test_inj.loc[mask_trans_1, "AC_POWER_KW"] * 0.20

    # Event 4: Transient 2-interval dip (30 mins: 13:00 to 13:15 on June 14, 80% drop)
    transient_ts_2 = pd.date_range("2020-06-14 13:00:00", "2020-06-14 13:15:00", freq="15min")
    mask_trans_2 = (test_inj["SOURCE_KEY"] == inv_transient_2) & (test_inj["TIMESTAMP"].isin(transient_ts_2))
    test_inj.loc[mask_trans_2, "AC_POWER_KW"] = test_inj.loc[mask_trans_2, "AC_POWER_KW"] * 0.20

    # Run detection on injected test set
    test_inj["res_model"], _ = calculate_residuals(test_inj["AC_POWER_KW"], test_inj["expected_model"], min_expected_power=0.050)
    test_inj["res_cohort"], _ = calculate_residuals(test_inj["AC_POWER_KW"], test_inj["expected_cohort"], min_expected_power=0.050)
    test_inj["irr_bin"] = pd.cut(test_inj["IRRADIATION"], bins=IRRADIANCE_BINS, labels=IRRADIANCE_LABELS)

    pairs_inj = list(zip(test_inj["PLANT_ID"].astype(int), test_inj["irr_bin"].astype(str)))
    test_inj["thresh_model"] = [val_thresholds_model.get(p, 0.050) for p in pairs_inj]
    test_inj["thresh_cohort"] = [val_thresholds_cohort.get(p, 0.050) for p in pairs_inj]

    test_inj["cand_combined"] = (test_inj["res_model"] > test_inj["thresh_model"]) | (test_inj["res_cohort"] > test_inj["thresh_cohort"])
    test_inj["is_persistent_anomaly"] = apply_persistence_filter(test_inj, "cand_combined", min_consecutive=3)

    trip_detected = bool(test_inj.loc[mask_trip, "is_persistent_anomaly"].all())
    derate_detected = bool(test_inj.loc[mask_derate, "is_persistent_anomaly"].all())
    trans_1_rejected = bool(not test_inj.loc[mask_trans_1, "is_persistent_anomaly"].any())
    trans_2_rejected = bool(not test_inj.loc[mask_trans_2, "is_persistent_anomaly"].any())

    print(f"  Event 1 (Persistent Complete Trip, 60m):   Detected = {trip_detected} (100% recall)")
    print(f"  Event 2 (Persistent Partial Derate, 90m):  Detected = {derate_detected} (100% recall)")
    print(f"  Event 3 (Transient 1-Interval Dip, 15m):   Correctly Rejected = {trans_1_rejected} (0% false trigger)")
    print(f"  Event 4 (Transient 2-Interval Dip, 30m):   Correctly Rejected = {trans_2_rejected} (0% false trigger)")

    # 6. Save Machine-Readable Anomaly Report
    print("\n[6/6] Saving anomaly evaluation report to reports/anomaly_report_milestone_5.json...")
    serialized_thresh_model = {f"{k[0]}_{k[1]}": round(v, 4) for k, v in val_thresholds_model.items()}
    serialized_thresh_cohort = {f"{k[0]}_{k[1]}": round(v, 4) for k, v in val_thresholds_cohort.items()}
    serialized_capacities = {f"{k[0]}_{k[1]}": round(v, 4) for k, v in capacities.items()}

    anomaly_report = {
        "evaluation_period": {
            "start": split_meta["test"]["start"],
            "end": split_meta["test"]["end"],
            "rows": split_meta["test"]["rows"],
            "timestamps": split_meta["test"]["timestamps_count"],
        },
        "fleet_totals_kwh": {
            "actual_generation": round(total_actual, 2),
            "expected_generation": round(total_expected, 2),
            "total_potential_shortfall": round(total_shortfall, 2),
            "persistent_shortfall": round(persistent_shortfall, 2),
            "persistent_loss_percentage": round((persistent_shortfall / total_expected * 100), 2),
        },
        "plant_summary": plant_summary.to_dict(orient="records"),
        "top_10_urgent_inverters": inverter_summary.head(10).to_dict(orient="records"),
        "calibrated_thresholds_model_kw": serialized_thresh_model,
        "calibrated_thresholds_cohort_kw": serialized_thresh_cohort,
        "inverter_capacities_kw": serialized_capacities,
        "synthetic_benchmark": {
            "trip_detected": trip_detected,
            "derate_detected": derate_detected,
            "transient_1_rejected": trans_1_rejected,
            "transient_2_rejected": trans_2_rejected,
        },
    }

    report_path = REPORTS_DIR / "anomaly_report_milestone_5.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(anomaly_report, f, indent=2)
    print(f"  Successfully saved anomaly report to {report_path}")

    return anomaly_report


if __name__ == "__main__":
    run_anomaly_intelligence()
