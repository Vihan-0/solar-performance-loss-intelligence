import glob
from pathlib import Path
import pandas as pd
import numpy as np

def verify():
    csv_files = list(Path("data/home_havells/raw").glob("*.csv"))
    if not csv_files:
        print("No CSV found.")
        return
    df = pd.read_csv(csv_files[0])
    df["dt"] = pd.to_datetime(df["System Time"])
    df = df.sort_values("dt").reset_index(drop=True)

    # Calculate dt difference in hours, clipping nighttime gaps to 0 (since power is 0 when shutting down/booting)
    df["gap_sec"] = df["dt"].diff().dt.total_seconds().fillna(300.0)
    # If gap is > 15 minutes, it's overnight: power before gap was near 0
    df["active_gap_hr"] = np.where(df["gap_sec"] > 900, 5.0/60.0, df["gap_sec"] / 3600.0)

    power_kw = df["Total AC Output Power(W)"] / 1000.0
    df["int_kwh"] = power_kw * df["active_gap_hr"]

    print(f"Total rows: {len(df)}")
    print(f"Date range: {df['dt'].min()} to {df['dt'].max()}")
    print(f"Peak AC Power: {power_kw.max():.2f} kW ({df['Total AC Output Power(W)'].max()} W)")

    daily_stats = []
    for d, g in df.groupby(df["dt"].dt.date):
        c_max = g["Daily Production (Active)(kWh)"].max()
        c_first = g["Daily Production (Active)(kWh)"].iloc[0]
        c_delta = c_max - c_first
        int_sum = g["int_kwh"].sum()
        peak_p = (g["Total AC Output Power(W)"] / 1000.0).max()
        daily_stats.append({
            "date": str(d),
            "rows": len(g),
            "counter_max_kwh": c_max,
            "counter_delta_kwh": c_delta,
            "integrated_kwh": round(int_sum, 2),
            "peak_kw": peak_p,
        })
        print(f"Date {d}: CounterMax={c_max:.2f} kWh, Delta={c_delta:.2f} kWh, Integrated={int_sum:.2f} kWh, Peak={peak_p:.2f} kW")

    tot_counter = sum(x["counter_max_kwh"] for x in daily_stats)
    tot_int = sum(x["integrated_kwh"] for x in daily_stats)
    print(f"Total 7-day Counter Sum: {tot_counter:.2f} kWh")
    print(f"Total 7-day Integrated Sum: {tot_int:.2f} kWh")
    cum_diff = df["Cumulative Production (Active)(kWh)"].iloc[-1] - df["Cumulative Production (Active)(kWh)"].iloc[0]
    print(f"Cumulative Counter Start-to-End Diff: {cum_diff:.2f} kWh")

if __name__ == "__main__":
    verify()
