"""
External Historical Weather Acquisition and Alignment Module
Adaptive Solar Performance & Loss Intelligence
Milestone 5 - Phase 3

Fetches and aligns hourly reanalysis weather data from Open-Meteo's Historical Weather API:
- Coordinates: 14.35° N, 77.49° E (approximate literature location in Kottapalle, Karnataka)
- Period: 2020-05-15 through 2020-06-17
- Timezone: Asia/Kolkata
- Variables: temperature_2m, relative_humidity_2m, precipitation, cloud_cover,
             wind_speed_10m, shortwave_radiation_instant
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, Optional, Tuple
import urllib.parse
import urllib.request
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_DATA_DIR = REPO_ROOT / "data" / "external"
DEFAULT_CACHE_CSV = EXTERNAL_DATA_DIR / "open_meteo_historical_weather.csv"
DEFAULT_META_JSON = EXTERNAL_DATA_DIR / "open_meteo_metadata.json"

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DEFAULT_LAT = 14.35
DEFAULT_LON = 77.49
DEFAULT_START = "2020-05-15"
DEFAULT_END = "2020-06-17"
DEFAULT_TIMEZONE = "Asia/Kolkata"
DEFAULT_HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "shortwave_radiation_instant",
]


def fetch_open_meteo_weather(
    start_date: str = DEFAULT_START,
    end_date: str = DEFAULT_END,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    tz: str = DEFAULT_TIMEZONE,
    hourly_vars: Optional[list] = None,
    cache_csv: Optional[Path] = DEFAULT_CACHE_CSV,
    meta_json: Optional[Path] = DEFAULT_META_JSON,
    force_refresh: bool = False,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Fetches historical weather from Open-Meteo Archive API or loads cached data.

    Returns:
        Tuple[pd.DataFrame, Dict]: (hourly_weather_df, metadata_dict)
    """
    if hourly_vars is None:
        hourly_vars = DEFAULT_HOURLY_VARS

    cache_path = Path(cache_csv) if cache_csv else None
    meta_path = Path(meta_json) if meta_json else None

    # Load from cache if available and not forcing refresh
    if not force_refresh and cache_path and cache_path.exists() and meta_path and meta_path.exists():
        df = pd.read_csv(cache_path)
        df["time"] = pd.to_datetime(df["time"])
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        return df, metadata

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(hourly_vars),
        "timezone": tz,
    }
    query_string = urllib.parse.urlencode(params)
    request_url = f"{OPEN_METEO_ARCHIVE_URL}?{query_string}"

    req = urllib.request.Request(request_url, headers={"User-Agent": "SolarIntelligencePlatform/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    hourly_dict = payload.get("hourly", {})
    if not hourly_dict or "time" not in hourly_dict:
        raise ValueError(f"Invalid API response payload: {payload}")

    raw_df = pd.DataFrame(hourly_dict)
    raw_df["time"] = pd.to_datetime(raw_df["time"])

    # Standardize units:
    # - temperature_2m (°C)
    # - relative_humidity_2m (%)
    # - precipitation (mm)
    # - cloud_cover (%)
    # - wind_speed_10m (km/h) -> also provide m/s
    # - shortwave_radiation_instant (W/m²) -> convert to kW/m² to match onsite IRRADIATION
    df_clean = pd.DataFrame()
    df_clean["time"] = raw_df["time"]
    df_clean["ext_temp_c"] = raw_df["temperature_2m"].astype(float)
    df_clean["ext_rh_pct"] = raw_df["relative_humidity_2m"].astype(float)
    df_clean["ext_precip_mm"] = raw_df["precipitation"].astype(float)
    df_clean["ext_cloud_cover_pct"] = raw_df["cloud_cover"].astype(float)
    df_clean["ext_wind_speed_kmh"] = raw_df["wind_speed_10m"].astype(float)
    df_clean["ext_wind_speed_ms"] = (raw_df["wind_speed_10m"] / 3.6).round(3)

    if "shortwave_radiation_instant" in raw_df.columns:
        df_clean["ext_radiation_w_m2"] = raw_df["shortwave_radiation_instant"].astype(float)
        df_clean["ext_radiation_kw_m2"] = (raw_df["shortwave_radiation_instant"] / 1000.0).round(4)

    metadata = {
        "source": "Open-Meteo Historical Weather API",
        "source_url": request_url,
        "retrieval_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "latitude": lat,
        "longitude": lon,
        "location_uncertainty": (
            "Approximate literature site coordinates (14.35° N, 77.49° E, Kottapalle area, Karnataka). "
            "Representative of regional mesoscale conditions; not verified GPS survey points."
        ),
        "timezone": tz,
        "start_date": start_date,
        "end_date": end_date,
        "raw_units": payload.get("hourly_units", {}),
        "standardized_units": {
            "ext_temp_c": "°C (ambient 2m)",
            "ext_rh_pct": "% (relative humidity 2m)",
            "ext_precip_mm": "mm (liquid precipitation)",
            "ext_cloud_cover_pct": "% (total cloud cover)",
            "ext_wind_speed_kmh": "km/h (wind speed at 10m)",
            "ext_wind_speed_ms": "m/s (wind speed at 10m)",
            "ext_radiation_w_m2": "W/m² (instantaneous surface solar radiation)",
            "ext_radiation_kw_m2": "kW/m² (standardized to match onsite IRRADIATION)",
        },
        "time_semantics": {
            "instantaneous": ["cloud_cover", "temperature_2m", "relative_humidity_2m", "shortwave_radiation_instant"],
            "aggregated": ["precipitation (sum over preceding hour)", "wind_speed_10m (hourly mean)"],
            "alignment_rule": (
                "Each 15-minute observation is aligned to its reference hour via t.floor('1h'). "
                "No intra-hour interpolation is fabricated."
            ),
        },
        "row_count": len(df_clean),
    }

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        df_clean.to_csv(cache_path, index=False)
    if meta_path:
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    return df_clean, metadata


def align_external_weather(
    generation_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    timestamp_col: str = "DATE_TIME",
) -> Tuple[pd.DataFrame, Dict]:
    """
    Aligns 15-minute telemetry with hourly external weather observations.

    Alignment Strategy:
    - Hourly reanalysis data represents mesoscale conditions over the reference hour.
    - Each 15-minute record is assigned its top-of-hour reference timestamp:
      ref_hour = timestamp.floor('1h')
    - This maps intervals [:00, :15, :30, :45] to the hour's weather conditions
      without fabricating non-existent intra-hour micro-fluctuations.
    - Preserves row count with strict assertion: len(merged) == len(generation_df).
    - Preserves a boolean indicator `has_external_weather`.

    Returns:
        Tuple[pd.DataFrame, Dict]: (merged_df, alignment_report)
    """
    gen = generation_df.copy()
    if not np.issubdtype(gen[timestamp_col].dtype, np.datetime64):
        gen[timestamp_col] = pd.to_datetime(gen[timestamp_col])

    wth = weather_df.copy()
    if not np.issubdtype(wth["time"].dtype, np.datetime64):
        wth["time"] = pd.to_datetime(wth["time"])

    # Reference hour mapping
    gen["_WEATHER_HOUR_REF"] = gen[timestamp_col].dt.floor("1h")

    # Rename weather columns to avoid collisions
    wth_join = wth.rename(columns={"time": "_WEATHER_HOUR_REF"})

    pre_len = len(gen)
    merged = gen.merge(wth_join, on="_WEATHER_HOUR_REF", how="left")

    if len(merged) != pre_len:
        raise ValueError(
            f"Join cardinality violation: pre-merge rows={pre_len}, post-merge rows={len(merged)}. "
            "Hourly weather keys may contain duplicates."
        )

    merged = merged.drop(columns=["_WEATHER_HOUR_REF"])
    merged["has_external_weather"] = merged["ext_temp_c"].notna()

    matched_count = int(merged["has_external_weather"].sum())
    unmatched_count = pre_len - matched_count
    match_pct = (matched_count / pre_len * 100.0) if pre_len > 0 else 0.0

    report = {
        "pre_merge_rows": pre_len,
        "post_merge_rows": len(merged),
        "matched_rows": matched_count,
        "unmatched_rows": unmatched_count,
        "match_percentage": round(match_pct, 2),
        "external_weather_columns": [c for c in wth.columns if c != "time"],
    }

    return merged, report
