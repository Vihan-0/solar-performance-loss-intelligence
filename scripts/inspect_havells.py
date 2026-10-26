"""Script to inspect Havells CSV without leaking PII."""
from pathlib import Path
import pandas as pd
import numpy as np

def main():
    raw_dir = Path("data/home_havells/raw")
    csv_files = list(raw_dir.glob("*.csv"))
    print(f"Files found in {raw_dir}: {len(csv_files)}")
    if not csv_files:
        print("No CSV files found.")
        return

    file_path = csv_files[0]
    df = pd.read_csv(file_path)

    out_path = Path("reports/havells_inspection.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"Files found in {raw_dir}: {len(csv_files)}\n")
        f.write(f"Shape: {df.shape}\n\n--- ALL COLUMNS ---\n")
        for idx, col in enumerate(df.columns):
            f.write(f"{idx}: {col}\n")

        f.write("\n--- SYSTEM TIME & UPDATED TIME ---\n")
        if "System Time" in df.columns:
            f.write(f"Head System Time:\n{df['System Time'].head(5).to_string()}\nTail System Time:\n{df['System Time'].tail(5).to_string()}\n")

        power_cols = [c for c in df.columns if any(w in c.lower() for w in ["power", "watt", "yield", "production", "voltage", "current", "temp", "status", "state", "work", "inverter"])]
        f.write("\n--- RELEVANT COLUMNS ---\n")
        for c in power_cols:
            f.write(f"Column: {c} | dtype: {df[c].dtype} | nulls: {df[c].isna().sum()} | min: {df[c].min()} | max: {df[c].max()}\n")

        if "System Time" in df.columns and "Daily Production (Active)(kWh)" in df.columns:
            df["dt"] = pd.to_datetime(df["System Time"], errors="coerce")
            df = df.sort_values("dt")
            df["date"] = df["dt"].dt.date
            f.write("\n--- DAILY SUMMARY ---\n")
            for date, group in df.groupby("date"):
                min_prod = group["Daily Production (Active)(kWh)"].min()
                max_prod = group["Daily Production (Active)(kWh)"].max()
                first_prod = group["Daily Production (Active)(kWh)"].iloc[0]
                last_prod = group["Daily Production (Active)(kWh)"].iloc[-1]
                rows_cnt = len(group)
                f.write(f"Date: {date} | Rows: {rows_cnt} | Min: {min_prod} | Max: {max_prod} | First: {first_prod} | Last: {last_prod}\n")

            f.write("\n--- SAMPLING INTERVALS ---\n")
            diffs = df["dt"].diff()
            f.write(f"Intervals value counts:\n{diffs.value_counts().head(10).to_string()}\n")
            large_gaps = df[diffs > pd.Timedelta(minutes=15)]
            f.write(f"Large gaps (>15m): {len(large_gaps)}\n")
            for _, r in large_gaps.iterrows():
                prev_time = r['dt'] - diffs.loc[r.name]
                f.write(f"Gap: from {prev_time} to {r['dt']} (duration: {diffs.loc[r.name]})\n")
    print("Inspection written successfully to", out_path)

if __name__ == "__main__":
    main()
