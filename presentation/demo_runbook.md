# Live Demonstration Runbook & Presentation Guide

**Project**: Adaptive Solar Performance & Loss Intelligence
**Target**: Mini-Project Evaluation Round II Demonstration
**Local URL**: `http://localhost:8501`
**Execution Environment**: Completely local & offline-capable (all model artifacts, preprocessed Parquet files, and weather caches are stored locally).

---

## 1. Quick Launch Instructions

Execute the following commands in PowerShell from the repository root:

```powershell
# Step 1: Open terminal in repository root
cd solar-performance-loss-intelligence

# Step 2: Activate the virtual environment
.venv\Scripts\Activate.ps1

# Step 3: Verify system health (runs in ~10 seconds)
pytest -v

# Step 4: Launch the Streamlit application
streamlit run app.py
```

Streamlit will launch and automatically open your default browser to:
👉 **`http://localhost:8501`**

*(Note: If the background Streamlit process is already running, you can simply open your browser directly to `http://localhost:8501`).*

---

## 2. Structured Walkthrough & Timing (3–4 Minutes Total)

### Screen 1: Overview & Loss Summary (45 seconds)
1. **Navigate**: Select **"Overview & Loss Summary"** from the sidebar.
2. **Point out the Executive Roadmap Card**: Show that Phase I and Phase II are fully implemented, and Phase III is planned.
3. **Point out the 4 KPI Cards**:
   - **Measured Generation**: $1,736.3\text{ kWh}$
   - **Expected Baseline**: $1,724.5\text{ kWh}$
   - **Persistent Shortfall**: **89.44 kWh (5.19% fleet loss)**
   - **Out-of-Time Model $R^2$**: **0.7337**
4. **Scroll down to Facility Breakdown**:
   - Point out that **Plant 2 accounts for 92.6% of fleet persistent loss** ($82.80\text{ kWh}$ vs Plant 1's $6.64\text{ kWh}$).
   - Explain: *"This demonstrates that our system immediately pinpoints which plant has chronic operational issues."*

---

### Screen 2: Plant & Inverter Explorer (60 seconds)
1. **Navigate**: Select **"Plant & Inverter Explorer"** from the sidebar.
2. **Select Facility and Inverter**:
   - **Select Plant**: Choose **`Plant 2 (4136001)`**.
   - **Select Inverter**: Choose **`Qf4GUc1pJu5T6c6`** (Rank #1 most urgent inverter).
3. **Show the High-Resolution Telemetry Chart**:
   - Point out the **Cyan Line** (Measured Active Power).
   - Point out the **Amber Dashed Line** (ML Baseline).
   - Point out the **Green Dotted Line** (Peer Cohort Benchmark).
   - Point out the **Red Event Markers**: Notice how during midday drops, the red badges flag sustained anomalous intervals where power plunged while the weather and peer inverters were high.
4. **Point out the Detection Evidence Card**:
   - Show: Expected $= 37.16\text{ kWh}$, Actual $= 25.80\text{ kWh}$, Persistent Shortfall $= 12.04\text{ kWh}$ ($32.4\%$ derate).
   - Explain: *"This inverter is operating at nearly one-third below capacity during peak hours, representing a persistent string derate that static thresholds completely missed."*

---

### Screen 3: Inverter Loss Prioritization (45 seconds)
1. **Navigate**: Select **"Inverter Loss Prioritization"** from the sidebar.
2. **Show the Urgency Ranking Table**:
   - Show that all 44 inverters across both plants are ordered by **Persistent Shortfall (kWh)**.
   - Point out the top 5 inverters—all belong to Plant 2 (`Qf4GUc1pJu5T6c6`, `4UPUqMRk7TRMgml`, `Mx2yZCDsyf6DPfv`).
3. **Demonstrate the CSV Download**:
   - Click the **"📥 Download Prioritization Report (CSV)"** button.
   - Explain: *"Operators can export this table directly into their computer-aided facility management (CAFM) system to schedule maintenance tickets based on real financial impact."*

---

### Screen 4: Interactive Synthetic Sandbox (60 seconds)
1. **Navigate**: Select **"Interactive Synthetic Demo"** from the sidebar.
2. **Explain the Sandbox**:
   - Explain: *"This sandbox runs in-memory and allows evaluators to test our persistence filter under controlled conditions without altering historical data."*
3. **Test Case 1 — Passing Cloud Transient (Demonstrate Suppression)**:
   - Set **Drop Magnitude**: `-50%`
   - Set **Duration**: `1 Interval (15 min)`
   - Click **"Inject Synthetic Drop"**.
   - **Show the Outcome**: The banner displays **"SUPPRESSED BY PERSISTENCE FILTER"** (0 alert-hours, 0 kWh shortfall).
   - Explain: *"The system recognized this as a transient cloud and suppressed the nuisance alarm."*
4. **Test Case 2 — Sustained String Outage (Demonstrate Detection)**:
   - Change **Duration** to: `4 Intervals (60 min)`
   - Click **"Inject Synthetic Drop"**.
   - **Show the Outcome**: The banner immediately flips to **"PERSISTENT CANDIDATE UNDERPERFORMANCE DETECTED"**, calculates the exact shortfall in kWh, and marks the red anomaly window.

---

### Screen 5: Phase II Residential Solar Intelligence (60 seconds)
1. **Navigate**: Select **"Phase II | Residential Solar Intelligence"** from the sidebar.
2. **Point out the KPI Strip**:
   - **997 Observations** across **7 days** (Oct 20–26, 2026).
   - **3.58 kW Peak Power** (71.6% of rated 5.0 kW capacity).
   - **134.94 kWh Total Production** (Daily mean: 19.28 kWh/day).
   - **5.0-Minute Sampling** with zero nulls.
3. **Tab 1: Overview & 3-Way Energy Reconciliation**:
   - Show the reconciliation card: Odometer Delta ($134.90\text{ kWh}$), Daily Counter Sum ($134.94\text{ kWh}$), and Discrete Integral ($135.90\text{ kWh}$, $+0.7\%$).
   - Explain: *"This mathematically validates that our numerical energy integration agrees with the physical hardware registers."*
4. **Tab 2: Telemetry Explorer**:
   - Show the smooth 7-day diurnal bell curves and explain that 6 nocturnal sleep gaps (~12h each) represent normal sunset shutdowns, with zero daytime communication dropouts.
5. **Tab 4: Roadmap & Readiness**:
   - Show the **Forecast Readiness Scorecard**.
   - Explain: *"We explicitly do not show a fake forecast. A 7-day export is valuable for baseline health, but true day-ahead forecasting is designated as Phase III roadmap work requiring multi-season data and localized NWP feeds."*

---

## 3. Resilience & Contingency Runbook

### Case A: Port 8501 is already in use
If another process is using port 8501:
```powershell
.venv\Scripts\streamlit run app.py --server.port 8502
```
Then open `http://localhost:8502`.

### Case B: External Internet is Unavailable
- The entire system operates **100% offline**.
- The Open-Meteo weather reanalysis data is already pre-fetched and cached in `data/external/open_meteo_historical_weather.parquet`.
- All processed Parquet datasets and serialized model artifacts (`models/best_solar_model.joblib`) are stored locally on disk.
- Zero network calls are required for the live demonstration.

### Case C: Hardware Display / Projector Failure Backup
If live projector connection fails, all 6 dashboard views have been captured as verified high-resolution PNG screenshots in `reports/figures/`:
1. `reports/figures/audit_view_1_overview.png`
2. `reports/figures/audit_view_2_phase_ii.png`
3. `reports/figures/audit_view_3_explorer.png`
4. `reports/figures/audit_view_4_prioritization.png`
5. `reports/figures/audit_view_5_synthetic.png`
6. `reports/figures/audit_view_6_methodology.png`
You can open and display these images directly in any standard image viewer.

---

## 4. Key Talking Points to Emphasize During the Demo

1. **"Everything you see is computed from real code and real data."**
2. **"We solved a 1,000x Kaggle unit error by cross-referencing peer-reviewed Oxford Academic literature."**
3. **"Our persistence filter eliminated 47.6 kWh of transient cloud noise in the test week."**
4. **"Phase II proves our architecture works on private residential single-phase inverters with strict PII scrubbing."**
5. **"All 46 automated unit tests pass with zero warnings."**
