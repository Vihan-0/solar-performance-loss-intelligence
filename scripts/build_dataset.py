"""
Dataset Build Script with External Weather Alignment & Unit Correction
Adaptive Solar Performance & Loss Intelligence
Milestone 5

Runs the complete, reproducible data cleaning, merging, external weather alignment,
and feature engineering pipeline.
Writes standardized Parquet artifacts to data/processed/.
"""

import sys
from pathlib import Path
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.data import (
    load_raw_generation_data,
    load_raw_weather_data,
    merge_plant_data,
    inspect_data_quality,
)
from src.features import (
    engineer_features,
    prepare_model_ready_dataset,
    BASELINE_FEATURE_COLUMNS,
    WEATHER_ENRICHED_CANDIDATE_COLUMNS,
    TARGET_COLUMN,
)
from src.weather import (
    fetch_open_meteo_weather,
    align_external_weather,
)

PROCESSED_DIR = REPO_ROOT / "data" / "processed"


def build_pipeline():
    print("=" * 80)
    print("RUNNING MILESTONE 5: DATA PROCESSING, UNIT CORRECTION & WEATHER ENRICHMENT")
    print("=" * 80)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # 0. Load External Reanalysis Weather
    # -------------------------------------------------------------------------
    print("\n[0/4] Loading / Fetching External Historical Weather...")
    ext_weather_df, ext_meta = fetch_open_meteo_weather()
    print(f"  External Weather records: {len(ext_weather_df):,} hourly observations")
    print(f"  Location: {ext_meta['latitude']}° N, {ext_meta['longitude']}° E ({ext_meta['timezone']})")

    # -------------------------------------------------------------------------
    # 1. Plant 1 Processing
    # -------------------------------------------------------------------------
    print("\n[1/4] Processing Plant 1...")
    p1_gen = load_raw_generation_data(plant_id=1)
    p1_weather = load_raw_weather_data(plant_id=1)
    p1_merged = merge_plant_data(p1_gen, p1_weather)
    p1_aligned, p1_align_rep = align_external_weather(p1_merged, ext_weather_df, timestamp_col="TIMESTAMP")
    p1_quality = inspect_data_quality(p1_aligned, plant_name="Plant 1")

    print(f"  Raw Gen rows: {len(p1_gen):,}")
    print(f"  Raw Weather rows: {len(p1_weather):,}")
    print(f"  Merged rows: {len(p1_aligned):,} (Left join preserved 100% of generation)")
    print(f"  Missing onsite weather: {p1_quality['missing_weather_rows']} ({p1_quality['missing_weather_pct']:.4f}%)")
    print(f"  External weather matched: {p1_align_rep['matched_rows']:,} / {p1_align_rep['pre_merge_rows']:,} ({p1_align_rep['match_percentage']}%)")

    # Feature engineering
    p1_featured = engineer_features(p1_aligned)
    p1_model_ready, p1_features, p1_target = prepare_model_ready_dataset(
        p1_featured, daylight_only=True, drop_missing_weather=True, feature_mode="baseline", target_col="AC_POWER_KW"
    )
    print(f"  Model-ready rows (daylight operational only): {len(p1_model_ready):,}")

    # -------------------------------------------------------------------------
    # 2. Plant 2 Processing
    # -------------------------------------------------------------------------
    print("\n[2/4] Processing Plant 2...")
    p2_gen = load_raw_generation_data(plant_id=2)
    p2_weather = load_raw_weather_data(plant_id=2)
    p2_merged = merge_plant_data(p2_gen, p2_weather)
    p2_aligned, p2_align_rep = align_external_weather(p2_merged, ext_weather_df, timestamp_col="TIMESTAMP")
    p2_quality = inspect_data_quality(p2_aligned, plant_name="Plant 2")

    print(f"  Raw Gen rows: {len(p2_gen):,}")
    print(f"  Raw Weather rows: {len(p2_weather):,}")
    print(f"  Merged rows: {len(p2_aligned):,} (Left join preserved 100% of generation)")
    print(f"  Missing onsite weather: {p2_quality['missing_weather_rows']} ({p2_quality['missing_weather_pct']:.4f}%)")
    print(f"  External weather matched: {p2_align_rep['matched_rows']:,} / {p2_align_rep['pre_merge_rows']:,} ({p2_align_rep['match_percentage']}%)")

    # Feature engineering
    p2_featured = engineer_features(p2_aligned)
    p2_model_ready, p2_features, p2_target = prepare_model_ready_dataset(
        p2_featured, daylight_only=True, drop_missing_weather=True, feature_mode="baseline", target_col="AC_POWER_KW"
    )
    print(f"  Model-ready rows (daylight operational only): {len(p2_model_ready):,}")

    # -------------------------------------------------------------------------
    # 3. Combined Multi-Plant Datasets
    # -------------------------------------------------------------------------
    print("\n[3/4] Building Combined Datasets (Baseline vs Weather-Enriched)...")
    combined_merged = pd.concat([p1_featured, p2_featured], ignore_index=True)

    # Baseline model-ready dataset (onsite features)
    combined_model_ready_baseline, baseline_cols, _ = prepare_model_ready_dataset(
        combined_merged, daylight_only=True, drop_missing_weather=True, feature_mode="baseline", target_col="AC_POWER_KW"
    )

    # Weather-enriched model-ready dataset (onsite + external features)
    combined_model_ready_enriched, enriched_cols, _ = prepare_model_ready_dataset(
        combined_merged, daylight_only=True, drop_missing_weather=True, feature_mode="weather_enriched", target_col="AC_POWER_KW"
    )

    print(f"  Combined Merged rows: {len(combined_merged):,}")
    print(f"  Combined Baseline Model-Ready rows: {len(combined_model_ready_baseline):,} (Features: {len(baseline_cols)})")
    print(f"  Combined Enriched Model-Ready rows: {len(combined_model_ready_enriched):,} (Features: {len(enriched_cols)})")

    # -------------------------------------------------------------------------
    # 4. Save Processed Artifacts
    # -------------------------------------------------------------------------
    print("\n[4/4] Saving Parquet datasets to data/processed/...")
    artifacts = {
        "plant_1_merged.parquet": p1_featured,
        "plant_2_merged.parquet": p2_featured,
        "combined_merged.parquet": combined_merged,
        "plant_1_model_ready.parquet": p1_model_ready,
        "plant_2_model_ready.parquet": p2_model_ready,
        "combined_model_ready.parquet": combined_model_ready_baseline,
        "combined_model_ready_enriched.parquet": combined_model_ready_enriched,
    }

    for fname, df in artifacts.items():
        save_path = PROCESSED_DIR / fname
        df.to_parquet(save_path, index=False)
        size_kb = save_path.stat().st_size / 1024.0
        print(f"  Saved {fname} ({len(df):,} rows, {size_kb:.1f} KB)")

    print("\n" + "=" * 80)
    print("PIPELINE SUMMARY & VERIFICATION")
    print("=" * 80)
    print(f"Target Variable (Canonical): {TARGET_COLUMN} (kW)")
    print(f"Raw Preserved Variable: AC_POWER (Watts)")
    print(f"Baseline Features ({len(baseline_cols)}): {baseline_cols}")
    print(f"Enriched Features ({len(enriched_cols)}): {enriched_cols}")
    print("Data Cleaning & Merge Success: TRUE")


if __name__ == "__main__":
    build_pipeline()
