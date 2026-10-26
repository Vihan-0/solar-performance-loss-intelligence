"""
Executable Script to Fetch and Cache External Historical Weather
Adaptive Solar Performance & Loss Intelligence
Milestone 5 - Phase 3
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.weather import fetch_open_meteo_weather


def main():
    print("Fetching external historical weather from Open-Meteo Archive API...")
    df, meta = fetch_open_meteo_weather(force_refresh=True)
    print(f"Successfully retrieved {len(df)} hourly records.")
    print(f"Date range: {df['time'].min()} to {df['time'].max()}")
    print("Standardized columns:", list(df.columns))
    print(f"Location: {meta['latitude']}° N, {meta['longitude']}° E ({meta['timezone']})")
    print(f"Cached data to data/external/open_meteo_historical_weather.csv")
    print(f"Cached metadata to data/external/open_meteo_metadata.json")


if __name__ == "__main__":
    main()
