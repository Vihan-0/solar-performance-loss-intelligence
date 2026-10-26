# Milestone 5 — Physical Unit & Capacity Audit Report

## 1. Executive Summary

This audit establishes the physical scale and true measurement units of the solar power telemetry in `Plant_1_Generation_Data.csv` and `Plant_2_Generation_Data.csv`.

Although the Kaggle dataset description erroneously labels `AC_POWER` as **kilowatts (kW)** and `DAILY_YIELD` as **kilowatt-hours (kWh)**, physical plant specifications, published peer-reviewed research, and raw measurement distributions confirm that:
- **Raw `AC_POWER` is recorded in Watts (W)**, NOT kilowatts.
- **Raw `DAILY_YIELD` is recorded in Watt-hours (Wh)**, NOT kilowatt-hours.
- **Canonical modeling target is `AC_POWER_KW = AC_POWER / 1000.0`** (kW).
- **Canonical energy accounting is $\Delta E = P_{\text{AC, kW}} \times \Delta t_{\text{hours}}$** (kWh).

---

## 2. Published Research & Ground-Truth Hardware Specifications

A published study detailing these exact facilities provides ground-truth hardware specifications:

- **Reference:** *"A physics-guided explainable machine learning framework for residual-based performance deviation detection and probabilistic severity assessment in photovoltaic systems"*, *Clean Energy* (Oxford Academic, 2026). DOI: [10.1093/ce/zkae050](https://academic.oup.com/ce/article/10/3/143/8698220).
- **Site Location:** Kottapalle area, Karnataka, India (~$14.35^\circ\,\text{N}, 77.49^\circ\,\text{E}$).
- **Facility IDs:** Plant 1 (`4135001`) and Plant 2 (`4136001`).
- **Array Capacity:** 176 Trina Solar TSM-320PD14 polycrystalline modules ($320\,\text{Wp}$ each) arranged in 22 strings ($8$ modules per string $= 2,560\,\text{Wp}$ per string/inverter).
- **Total Installed DC Capacity:** $176 \times 320\,\text{W} = 56,320\,\text{Wp} = \mathbf{56.32\,\text{kWp}}$ per plant.
- **Inverters:** 22 grid-connected **Growatt MIC 1500TL-X** inverters per plant.
- **Inverter Rating:** Maximum rated AC output power is **$1,500\,\text{W}$ ($1.5\,\text{kW}$)** per inverter.
- **Observed Plant Peak AC Generation:** **$\mathbf{29.15\,\text{kW}}$**.

---

## 3. Empirical Verification Against Raw CSV Datasets

Using `scripts/audit_units_and_physics.py`, we audited the raw files:

```
=== PHYSICAL & UNIT AUDIT RESULTS ===
Plant 1 Inverter Peak AC (raw): 1410.95 (Growatt MIC 1500TL-X rated 1500W)
Plant 2 Inverter Peak AC (raw): 1385.42 (Growatt MIC 1500TL-X rated 1500W)
Plant 1 Plant-Level Concurrent Peak: 29150.2 W = 29.15 kW
Plant 2 Plant-Level Concurrent Peak: 25979.8 W = 25.98 kW
Literature Reported Observed Peak: ~29.15 kW
```

### Key Physical Proof Points:
1. **Inverter AC Rating:** The Growatt MIC 1500TL-X inverter has a hardware ceiling of $1,500\,\text{W}$. In the raw data, the maximum observed individual inverter generation is $1,410.95$ in Plant 1 and $1,385.42$ in Plant 2. If the raw values were in kW, an inverter the size of a home router would be generating $1.41\,\text{MW}$, which is physical nonsense.
2. **Plant Peak Summation:** Summing all 22 inverters at the single timestamp of peak generation produces **$29,150.2\,\text{W} = \mathbf{29.15\,\text{kW}}$**, matching the literature reported plant peak ($29.15\,\text{kW}$) to 4 significant figures.
3. **Daily Energy Yield:** Peak recorded `DAILY_YIELD` per inverter is $9,163.0$ (Plant 1) and $9,873.0$ (Plant 2). For a $2.56\,\text{kWp}$ string operating over 5–6 peak sun hours in Karnataka, the expected daily generation is $\approx 9\text{–}12\,\text{kWh} = 9,000\text{–}12,000\,\text{Wh}$. Thus, `DAILY_YIELD` is in **Watt-hours (Wh)**.

---

## 4. Discrepancy with Kaggle Dataset Metadata

The Kaggle uploader labeled `AC_POWER` as "kW" and `DAILY_YIELD` as "kWh". This naive labeling introduced a $1,000\times$ unit error in earlier reporting:
- Previous reports quoted test set generation as $\approx 1.73\,\text{million kWh}$ ($1.73\,\text{GWh}$), which would require an enormous utility-scale solar farm.
- In reality, for a $56.32\,\text{kWp}$ plant over 7 days, actual generation is $\approx \mathbf{1,736.3\,\text{kWh}}$, and estimated persistent shortfall is $\approx \mathbf{42.5\,\text{kWh}}$.

---

## 5. Architectural & Pipeline Decisions

To establish strict unit integrity without corrupting the raw source datasets:
1. **Raw Preservation:** Original raw CSV files remain unaltered in `data/raw/`.
2. **Canonical Target:** `src/data.py` creates and exposes `AC_POWER_KW = AC_POWER / 1000.0`.
3. **Model Re-training:** Models are retrained to predict `AC_POWER_KW` directly. All metrics (MAE, RMSE) are reported in kW.
4. **Energy Integration:** Energy shortfall and generation are computed via:
   $$\Delta E_t = P_{\text{kW}, t} \times \Delta t_{\text{hours}} \quad (\text{kWh})$$
5. **Thresholds & Reports:** Residual thresholds, capacity proxies, diagnostic reports, and dashboard visualizations are recalibrated and expressed in true physical kW and kWh.
