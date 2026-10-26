# Adaptive Solar Performance & Loss Intelligence: Project Source of Truth

**Document Purpose**: Definitive, empirical technical reference and single source of truth for the academic mini-project evaluation. All facts, metrics, schemas, and architectural boundaries in this document are directly verified against the repository codebase, serialized artifacts, test suite, and raw datasets.

---

## A. Project Definition

### 1. Exact Title
**Adaptive Solar Performance & Loss Intelligence: Inverter-Level Baselining, Peer-Cohort Benchmarking, and Operational Shortfall Quantification**

### 2. Problem Statement
In operational photovoltaic (PV) systems, raw power output fluctuates continuously due to diurnal solar geometry and transient cloud cover. A drop in generated power does not inherently indicate a system fault—it is frequently normal meteorological behavior. Conversely, serious sub-module faults (such as string disconnects, diode failures, localized shading, inverter derating, or progressive soiling) are frequently masked on sunny days when power remains moderately high, or dismissed as normal cloud behavior on overcast days.

Traditional Supervisory Control and Data Acquisition (SCADA) systems rely on static lower-bound power thresholds (e.g., $P < 0.2\text{ kW}$), which trigger high false-alarm rates during dawn/dusk and overcast periods while failing completely to catch partial degradation under strong sunlight. Operators lack an automated, physically sound mechanism to:
1. Distinguish transient weather fluctuations from persistent equipment underperformance.
2. Separate acute inverter dropouts from chronic sub-optimal generation.
3. Quantify cumulative lost energy in kilowatt-hours (kWh) to prioritize maintenance dispatch based on real energy and financial impact.

### 3. Why the Problem Matters
- **Operational Scalability**: Commercial solar farms house tens to hundreds of string inverters across sprawling footprints. Manual inspection of raw telemetry streams is operationally impossible.
- **Alarm Fatigue**: Operators routinely silence or ignore unconditioned alerts because transient clouds trigger hundreds of daily threshold violations.
- **Lost Revenue Recovery**: A persistent 15% string derate on an inverter can persist unnoticed for months, accumulating substantial lost energy ($>10,000\text{ kWh/yr}$ on utility strings) without ever triggering a complete zero-output alarm.
- **Residential Democratization**: Small-scale residential rooftop owners lack dedicated monitoring engineers and require automated, intelligible loss intelligence rather than raw uninterpreted power curves.

### 4. Project Objectives
1. **Model Expected Power ($P_{\text{expected}}$)**: Establish a baseline ML model that predicts expected AC active power (kW) for each inverter conditioned on local meteorological predictors (pyranometer irradiance, module and ambient temperatures) and cyclical solar time.
2. **Dual-Baseline Benchmarking**: Combine the individual inverter ML baseline with a concurrent **Capacity-Normalized Peer-Cohort Benchmark** ($P_{\text{cohort}}$) to detect both acute sudden failures and chronic long-term derating.
3. **Filter Transient Weather Noise**: Enforce a strict temporal persistence filter ($\ge 3$ consecutive valid 15-minute intervals / $\ge 45\text{ minutes}$) with gap-reset logic to reject transient cloud shadows while isolating actionable performance loss.
4. **Quantify Potential Energy Shortfall**: Integrate residual power deficits over time to calculate lost energy in kilowatt-hours ($\Delta E = P_{\text{loss}} \times \Delta t$), avoiding double-counting and rejecting phantom nighttime losses.
5. **Urgency-Driven Maintenance Prioritization**: Rank inverters across facilities by persistent energy shortfall (kWh), loss percentage, and accumulated alert-hours to guide field engineering dispatches.
6. **Residential Validation Track (Phase II)**: Ingest, sanitize, and validate single-phase residential rooftop telemetry (Havells 5.0 kW inverter), proving cross-domain adaptability while maintaining strict data governance.

### 5. Existing Solutions vs. Our Engineering Contribution

| Dimension | Standard Industry / Naive Baseline | Adaptive Solar Intelligence Platform (This Work) | Engineering Rationale & Impact |
| :--- | :--- | :--- | :--- |
| **Detection Paradigm** | Static thresholding (e.g. $P < 0.2\text{ kW}$) or basic statistical z-scores. | **Dual-Baseline Architecture**: Inverter ML Model (weather-driven) + Capacity-Normalized Peer Cohort. | Inverter-only models learn chronic faults as "normal" behavior; pure peer cohorts fail during plant-wide cloud cover. Dual baselines detect acute trips AND chronic derates. |
| **Transient Weather Handling** | Instantaneous point-in-time alerts, causing alarm fatigue on passing clouds. | **Temporal Persistence Filter**: Requires $\ge 3$ consecutive 15-min intervals ($\ge 45\text{ min}$) with gap reset. | Suppressed **47.58 kWh** of transient passing cloud noise in held-out test data, targeting dispatch solely to sustained anomalies. |
| **Out-of-Time Validation** | Random `train_test_split` or standard k-fold CV across shuffled rows (lookahead leakage). | **Strict Chronological Splitting**: Train (60%), Validation (20%), Out-of-Time Test (20%) on sorted timestamp groups. | Preserves operational causality and temporal group cohesion; transformers and scalers fit strictly on training slices. |
| **Feature Leakage Safeguards** | Telemetry models often leak contemporaneous `DC_POWER` or cumulative `DAILY_YIELD`. | **Strict Target-Leakage Elimination**: Zero electrical outputs or cumulative counters in feature vectors. | Relies purely on exogenous weather, temperatures, cyclical time encodings, and entity embeddings. |
| **Physical Accounting & Units** | Blind reliance on raw metadata (e.g. 1,000× Kaggle unit mislabeling of Watts as kW). | **Empirical Physics Reconciliation**: Canonical kW conversion, literature ground truth, and 3-way energy reconciliation. | Prevented 1,000× distortion in fleet loss metrics; verified against peer-reviewed physical plant literature (*Clean Energy*, Oxford Academic). |
| **Residential Extensibility** | Monolithic utility pipelines incapable of ingesting single-inverter residential rooftop exports. | **Phase II Residential Track**: Dynamic discovery, PII stripping (SN/account IDs), standby gap analysis, and 3-way accounting. | Expands framework to residential rooftop domain while maintaining complete separation from commercial training corpora. |

### 6. What We Can Legitimately Claim as Innovation
1. **Capacity-Normalized Peer Cohort Benchmarking**: A dynamic, robust peer-median formulation that scales inverters by their empirical capacity ratings ($C_i$), enabling fair peer comparisons across inverters with slight string variations without normalizing chronic degradation.
2. **Empirical Physical Unit Grounding**: Discovery and resolution of the 1,000× Kaggle unit mislabeling through cross-referencing published literature (*Clean Energy*, Oxford Academic, 2026), establishing canonical scaling ($1\text{ kW} = 1,000\text{ W}$) and physical bound validation.
3. **Outage-Filtered Threshold Recalibration**: Preventing catastrophic multi-inverter grid dropouts from distorting validation residual quantiles, restoring full detection sensitivity to subtle string derates ($84.6\text{ W}$ threshold vs $1,119\text{ W}$ distorted).
4. **Dual-Domain Evaluation**: Validating the methodology across two distinct operational regimes: multi-inverter commercial three-phase utility arrays (Plants 1 & 2) and single-inverter residential single-phase rooftop systems (Havells 5.0 kW).

---

## B. Exact Technology Stack & Dependencies

All technologies are verified present in the project runtime environment (`Python 3.13.3`, Windows x64):

| Technology | Installed / Declared Version | Exact Role in OUR Project |
| :--- | :--- | :--- |
| **Python** | `3.13.3` | Core runtime language executing data pipelines, ML workflows, automated tests, and dashboard rendering. |
| **pandas** | `2.2.3` | Ingests CSV/Parquet files, performs timestamp parsing, chronological slicing, join assertions, and daily energy aggregation. |
| **NumPy** | `2.2.3` | Computes cyclical solar encodings ($\sin/\cos$ transforms), array clipping, vector residuals, and trapezoidal integrals. |
| **scikit-learn** | `1.6.1` | Constructs end-to-end ML pipelines: `StandardScaler`, `OneHotEncoder`, `RandomForestRegressor`, `HistGradientBoostingRegressor`, and `Ridge`. |
| **joblib** | `1.4.2` | Serializes and loads trained model pipelines and associated metadata (`models/best_solar_model.joblib`). |
| **pyarrow** | `19.0.1` | Reads and writes high-performance columnar storage for model-ready datasets and weather caches (`data/processed/*.parquet`). |
| **Streamlit** | `1.43.2` | Serves the interactive 6-view visual operations dashboard with reactive sliders, dropdowns, and download handlers. |
| **Plotly** | `6.0.0` | Renders interactive, zoomable time-series charts, residual scatter plots, and telemetry traces with dark glassmorphic styling. |
| **matplotlib** | `3.10.1` | Provides underlying color mapping and static figure export utilities. |
| **pytest** | `9.1.1` | Executes the 46 automated unit and integration tests across data integrity, model properties, anomaly persistence, and residential math. |
| **python-pptx** | `1.0.2` | Programmatically generates the 16:9 widescreen presentation slide deck with exact Apple-inspired styling and assets. |
| **Open-Meteo API** | REST / JSON | Free, public historical meteorological archive providing regional ERA5 hourly reanalysis data (14.35° N, 77.49° E) for enrichment experiments. |

### Explicit Technical Non-Claims (Integrity Enforcement)
- **NO Deep Learning / Neural Networks / PyTorch / TensorFlow**: We do not use neural networks or LLMs for power modeling. Tabular weather and SCADA telemetry are modeled using scikit-learn tree ensembles.
- **NO Cloud Database / Live Streaming**: Data is processed locally in Parquet/CSV formats. The system operates on historical telemetry batches, not a live Kafka/cloud stream.
- **NO `pvlib` Physical Modeling**: We do not implement a physics-based cell-temperature/angle-of-incidence `pvlib` simulator; we employ empirical data-driven machine learning.
- **NO Live Inverter Connection**: The residential page evaluates a verified local CSV export, not an active cloud API webhook or Modbus connection.

---

## C. Datasets and Data Processing Pipeline

### 1. Public Utility-Scale Solar Dataset (Kaggle)
- **Source**: Kaggle Solar Power Generation Dataset (Rahman, 2020).
- **Physical Installation**: Two solar power plants in Karnataka, India (~14.35° N, 77.49° E). Each plant has 22 string inverters (Growatt MIC 1500TL-X, rated 1.5 kW AC each; array total 33 kW AC, 56.32 kWp DC).
- **Temporal Horizon**: 34 contiguous days (May 15, 2020 to June 17, 2020), early summer dry period.
- **Sampling Cadence**: 15-minute synchronous intervals.
- **Raw File Statistics**:
  - `Plant_1_Generation_Data.csv`: 68,778 rows, 22 inverters (`SOURCE_KEY`), date format `%d-%m-%Y %H:%M` (day-first).
  - `Plant_1_Weather_Sensor_Data.csv`: 3,182 rows, 1 weather sensor key, date format `%Y-%m-%d %H:%M:%S`.
  - `Plant_2_Generation_Data.csv`: 67,698 rows, 22 inverters (`SOURCE_KEY`), date format `%Y-%m-%d %H:%M:%S`.
  - `Plant_2_Weather_Sensor_Data.csv`: 3,259 rows, 1 weather sensor key, date format `%Y-%m-%d %H:%M:%S`.
- **Pre- and Post-Join Assertions**:
  - Weather station readings are joined strictly on `(DATE_TIME, PLANT_ID)`. Joining on `SOURCE_KEY` is prohibited because generation keys (inverters) and weather keys (sensors) are distinct namespaces.
  - Asserted `len(merged_df) == len(gen_df)` (zero row multiplication).
  - Merged daylight dataset ($\text{IRRADIATION} > 0$): **77,098 rows**.

### 2. External Historical Weather Dataset (Open-Meteo)
- **Source**: Open-Meteo Historical Weather API (ECMWF ERA5 reanalysis).
- **Coordinates**: 14.35° N, 77.49° E (matching the literature-verified plant site).
- **Variables Retrieved**: Temperature (2m), Relative Humidity (2m), Cloud Cover (total), Wind Speed (10m), Surface Pressure.
- **Temporal Alignment**: Regional hourly observations are forward-interpolated to 15-minute intervals without lookahead bias.
- **Result**: Cached as `data/external/open_meteo_historical_weather.parquet` (817 hourly timestamps).

### 3. Private Residential Inverter Export (Havells 5.0 kW)
- **Source**: On-premise CSV export from a real Havells 5.0 kW single-phase grid-tied string inverter (`data/home_havells/raw/*.csv`).
- **Telemetry Volume**: 997 synchronous readings across 63 telemetry channels.
- **Date Range**: October 20, 2026 06:01:17 to October 26, 2026 17:56:09 (7 consecutive days).
- **Sampling Cadence**: Nominal 300 seconds (5.0 minutes) with minor clock jitter ($\pm 4$s).
- **Data Quality Invariants**: **0 missing nulls, 0 duplicate timestamps**.
- **Nocturnal Standby Gaps**: Exactly 6 overnight gaps ($\sim 12$ hours each) from dusk ($\sim 17:55$) to dawn ($\sim 06:01$) when the inverter goes to sleep. **Zero daytime communication dropouts occurred**.
- **Peak AC Active Power**: **3.58 kW** ($3,580\text{ W}$), operating at 71.6% of rated capacity.
- **Thermal Semantics**: Internal motherboard chassis temperature (0–61°C) and heatsink radiator temperature (0–62°C) sensors reflect internal power dissipation, not ambient air.
- **Privacy Protections**: Hardware serial numbers (`SN`, `Device SN`), internal device names, account credentials, and inverter PCU IDs are scrubbed dynamically during load. Raw files are gitignored.

### 4. Data Preprocessing & Leakage Elimination
1. **Canonical Unit Conversion**:
   $$\text{AC\_POWER\_KW} = \frac{\text{AC\_POWER}}{1000.0}$$
2. **Target Leakage Elimination**:
   `DC_POWER`, `DAILY_YIELD`, and `TOTAL_YIELD` are contemporaneous electrical outputs or cumulative counters. Including them produces near-trivial $R^2 \approx 0.999$, destroying the model's ability to identify when AC power drops relative to weather. They are strictly excluded.
3. **Cyclical Solar Time Features**:
   To allow linear and tree models to capture smooth diurnal and annual solar geometry:
   $$\text{sin\_time} = \sin\left(\frac{2\pi \cdot (\text{hour} \times 60 + \text{min})}{1440}\right), \quad \text{cos\_time} = \cos\left(\frac{2\pi \cdot (\text{hour} \times 60 + \text{min})}{1440}\right)$$
   $$\text{sin\_day} = \sin\left(\frac{2\pi \cdot \text{day\_of\_year}}{365.25}\right), \quad \text{cos\_day} = \cos\left(\frac{2\pi \cdot \text{day\_of\_year}}{365.25}\right)$$
4. **Thermal Feature**:
   $$\text{TEMP\_DIFF} = \text{MODULE\_TEMPERATURE} - \text{AMBIENT\_TEMPERATURE}$$

---

## D. Machine Learning Implementation & Model Selection

### 1. Task Definition: Why Regression?
The objective is to quantify **expected active power generation in kilowatts (kW)** under prevailing weather conditions. Binary classification ("fault" vs "normal") fails because:
- Solar degradation occurs on a continuous spectrum (e.g., 5% soiling, 15% partial shade, 50% string drop, 100% trip).
- No ground-truth maintenance logs exist to label binary classes.
- Regression produces real-valued residuals ($\text{Residual} = P_{\text{expected}} - P_{\text{actual}}$) that directly yield lost energy in physical kilowatt-hours ($\text{kWh}$).

### 2. Feature Vector (10 Predictors)
$$\mathbf{x} = [\text{IRRADIATION}, \text{AMBIENT\_TEMPERATURE}, \text{MODULE\_TEMPERATURE}, \text{TEMP\_DIFF}, \text{sin\_time}, \text{cos\_time}, \text{sin\_day}, \text{cos\_day}, \text{PLANT\_ID}, \text{SOURCE\_KEY}]$$

### 3. Chronological Validation Strategy
Random splitting (e.g. `train_test_split`) violates time-series causality, causing adjacent 15-minute readings to leak between train and test sets and artificially inflating metrics. We employ strict chronological splitting on sorted unique timestamps:
- **Train Split (60%)**: May 15, 2020 05:45 to June 4, 2020 11:15 (44,966 daylight rows)
- **Validation Split (20%)**: June 4, 2020 11:30 to June 11, 2020 07:00 (15,896 daylight rows) — used exclusively for model selection and residual threshold calibration.
- **Held-Out Test Split (20%)**: June 11, 2020 07:15 to June 17, 2020 18:45 (16,236 daylight rows) — strictly reserved for final out-of-time evaluation.

### 4. Model Selection Benchmark (Held-Out Test Set: June 11–17, 2020)

| Model Architecture | Val MAE (kW) | Val WAPE (%) | Test MAE (kW) | Test RMSE (kW) | Test $R^2$ | Test WAPE (%) | Selection Decision |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Baseline (RandomForest)** | **0.1055** | **21.95%** | **0.0704** | **0.1704** | **0.7337** | **16.46%** | **SELECTED & RETAINED** |
| Enriched (RandomForest) | 0.1076 | 22.37% | 0.0708 | 0.1660 | 0.7473 | 16.56% | Rejected (higher val error) |
| Baseline (HistGBR) | 0.1073 | 22.33% | 0.0699 | 0.1646 | 0.7515 | 16.35% | Evaluated alternative |
| Enriched (HistGBR) | 0.1105 | 22.99% | 0.0735 | 0.1634 | 0.7550 | 17.19% | Rejected (higher val error) |
| Baseline (Ridge) | 0.1257 | 26.15% | 0.1120 | 0.1814 | 0.6982 | 26.18% | Reference baseline |
| Enriched (Ridge) | 0.1287 | 26.79% | 0.1158 | 0.1817 | 0.6972 | 27.08% | Reference baseline |

*Evaluation Metric Definitions*:
- $\text{MAE} = \frac{1}{N}\sum |y_i - \hat{y}_i| = \mathbf{0.0704\text{ kW}} = \mathbf{70.4\text{ W}}$
- $\text{RMSE} = \sqrt{\frac{1}{N}\sum (y_i - \hat{y}_i)^2} = \mathbf{0.1704\text{ kW}} = \mathbf{170.4\text{ W}}$
- $R^2 = 1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y})^2} = \mathbf{0.7337}$
- $\text{WAPE} = \frac{\sum |y_i - \hat{y}_i|}{\sum y_i} \times 100\% = \mathbf{16.46\%}$

### 5. Why the Simpler Baseline Was Retained (Occam's Razor)
Incorporating regional ERA5 reanalysis weather from Open-Meteo increased validation error by $+1.99\%$ MAE ($0.1055$ to $0.1076\text{ kW}$). Onsite pyranometers and module thermocouples capture direct array physics at high spatial fidelity; regional reanalysis ($0.1^\circ$ grid / $\sim 11\text{ km}$) introduces spatial smoothing that obscures microclimate variations. Per Occam's razor, the simpler 10-feature baseline was retained.

---

## E. Anomaly Detection, Persistence, and Loss Intelligence

### 1. Residual Definition and Sign Convention
$$\text{Residual}_{\text{model}}(t, i) = P_{\text{expected}}(t, i) - P_{\text{actual}}(t, i)$$
- **Positive Residual ($>0$)**: Generation deficit ($P_{\text{actual}} < P_{\text{expected}}$) $\implies$ candidate underperformance.
- **Negative Residual ($<0$)**: Over-performance ($P_{\text{actual}} > P_{\text{expected}}$) $\implies$ normal / high irradiance. Clamped to zero for shortfall accounting.

### 2. Capacity-Normalized Peer-Cohort Benchmark
To detect chronic underperformance that an inverter ML model might normalize as "expected", we evaluate concurrent peer inverters within the same plant:
1. Estimate each inverter's effective peak capacity $C_i$ (99th percentile of observed daylight power).
2. Compute normalized peer generation across all inverters in the plant:
   $$P_{\text{cohort}}(t, i) = \text{Median}\left(\left\{\frac{P_{\text{actual}}(t, j)}{C_j}\right\}_{j \in \text{Plant}}\right) \times C_i$$
3. Peer residual:
   $$\text{Residual}_{\text{cohort}}(t, i) = P_{\text{cohort}}(t, i) - P_{\text{actual}}(t, i)$$

### 3. Threshold Calibration & Outage Filtering
- Residual thresholds are calibrated on the **validation split** across three solar regimes:
  - Low Sun ($\text{Irradiation} < 0.2\text{ kW/m}^2$): Threshold $= 0.0300\text{ kW}$
  - Medium Sun ($0.2 \le \text{Irradiation} \le 0.6\text{ kW/m}^2$): Threshold $= 0.0904\text{ kW}$ (Plant 1), $0.3336\text{ kW}$ (Plant 2)
  - High Sun ($\text{Irradiation} > 0.6\text{ kW/m}^2$): Threshold $= 0.1775\text{ kW}$ (Plant 1), $0.0846\text{ kW}$ (Plant 2 recalibrated)
- **Recalibration Insight**: In Plant 2, massive multi-inverter outages during validation inflated the unconditioned 95th quantile to $1.119\text{ kW}$. Calibrating exclusively on operating inverters ($P > 0.05\text{ kW}$) restored sensitivity ($0.0846\text{ kW}$), catching subtle string derates while the inverter ML model catches trips.

### 4. Temporal Persistence Filter
An instantaneous deviation does not trigger an alarm. An anomaly is confirmed actionable if and only if:
$$\text{Persistent Anomaly} = (\text{Residual} > \text{Threshold}) \quad \text{for } \ge 3 \text{ consecutive intervals } (\ge 45\text{ min})$$
- **Gap-Reset Logic**: Missing timestamps reset the persistence counter to zero, preventing false bridging across nocturnal sleep periods or communication gaps.

### 5. Operational Loss Accounting (Held-Out Test Set Results)
- **Total Measured Generation**: $1,736.26\text{ kWh}$
- **Expected Generation**: $1,724.51\text{ kWh}$
- **Total Raw Residual Shortfall**: $137.02\text{ kWh}$ (7.95% of expected)
- **Persistent Actionable Shortfall ($\ge 45$m)**: **89.44 kWh (5.19% fleet loss)**
- **Transient Cloud Noise Suppressed**: **47.58 kWh** (34.7% of raw shortfall safely rejected)
- **Accumulated Inverter Alert-Hours**: **158.75 hours** (Plant 1: 11.5 h; Plant 2: 147.25 h)
- **Facility Disparity**: Plant 2 accounts for **92.6% of fleet persistent loss** ($82.80\text{ kWh}$), dominated by chronic daytime inverter dropouts on inverters `Qf4GUc1pJu5T6c6` ($12.04\text{ kWh}$ shortfall, 32.4% loss) and `4UPUqMRk7TRMgml` ($9.55\text{ kWh}$ shortfall).

---

## F. Architectural Separation: Phase I, Phase II, and Phase III

### Phase I — Commercial Fleet Performance Intelligence (IMPLEMENTED)
- Dual-plant utility-scale SCADA analytics (44 inverters across Plants 1 & 2).
- Validated 10-feature Random Forest expected power model ($R^2 = 0.7337$, $\text{MAE} = 70.4\text{ W}$).
- Dual-baseline detection, temporal persistence filtering ($\ge 45$m), operational shortfall accounting, and urgency ranking table.
- Interactive synthetic sandbox for controlled validation.

### Phase II — Residential Solar Intelligence (IMPLEMENTED)
- Dedicated analytics pipeline ingesting local Havells 5.0 kW single-phase string inverter export (`data/home_havells/raw/*.csv`).
- Dynamic file discovery and automated PII scrubbing (serial numbers, device IDs, credentials).
- Telemetry validation: 997 synchronous readings, 5.0-minute cadence, 0 nulls, 6 nocturnal standby gaps (~12h each), 0 daytime dropouts.
- Peak power verification: 3.58 kW observed (71.6% rated capacity).
- 3-Way Energy Reconciliation: Odometer Delta ($134.90\text{ kWh}$), Daily Counter Sum ($134.94\text{ kWh}$), Trapezoidal Integral ($135.90\text{ kWh}$).
- Operating state distribution: Grid Connected (96.8%), Waiting (2.3%), Recoverable Fault (0.7%), Checking (0.2%).
- Internal chassis motherboard (0–61°C) and radiator heatsink (0–62°C) temperature semantics.
- Strictly maintained as a separate validation track; **never merged into utility training data**.

### Phase III — Day-Ahead Forecasting & Live Integration (PLANNED ROADMAP)
- **Planned Weather-Informed Day-Ahead Forecasting**: Numerical Weather Prediction (NWP) solar irradiance forecasts coupled to trained regression models.
- **Planned Live Inverter Ingestion**: Authorized cloud webhook or on-premise Modbus TCP polling gateway.
- **Status**: Formally documented as future work. The dashboard presents an honest **Forecast Readiness Scorecard** outlining required prerequisite feeds. No fabricated forecast is presented.

---

## G. Limitations, Risks, and Viva Defense Boundaries

1. **Short Observation Horizon (34 Days Utility, 7 Days Residential)**: Telemetry is confined to early summer dry periods. Extrapolating or annualizing losses across monsoon or winter seasons is scientifically invalid.
2. **Absence of Ground-Truth Maintenance Telemetry**: Neither dataset contains physical repair logs or maintenance work orders. Deviations are strictly labeled **candidate underperformance intervals**, not confirmed component failures.
3. **Regional Reanalysis Resolution**: Open-Meteo ERA5 reanalysis operates at $\sim 11\text{ km}$ grid resolution, unable to resolve localized cloud shadows as effectively as onsite pyranometers.
4. **Phase III Forecasting Maturity**: A 7-day residential export cannot train a multi-season day-ahead forecast without severe seasonal overfitting.
5. **Zero Open Defects**: 46 automated unit tests pass with 0 warnings; all numbers across documentation, JSON reports, and dashboard agree exactly.
