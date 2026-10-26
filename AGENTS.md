# AGENTS.md

## Project: Adaptive Solar Performance & Loss Intelligence

This repository hosts an end-to-end solar intelligence platform designed to:
1. **Predict Expected AC Power**: Model baseline inverter-level AC generation given weather (irradiance, ambient/module temperature) and system characteristics.
2. **Detect Persistent Candidate Underperformance**: Flag multi-interval anomalous generation deviations while filtering out transient environmental fluctuations.
3. **Estimate Potential Energy Shortfall**: Quantify accumulated energy loss (kWh) attributable to underperformance over operational windows.
4. **Prioritize Systems for Investigation**: Rank inverters and subsystems by urgency, recurring underperformance patterns, and financial/energy impact.

---

## Approved Technology Stack
- **Language & Runtime**: Python 3.10+
- **Data Manipulation & Numerics**: `pandas`, `NumPy`
- **Machine Learning & Modeling**: `scikit-learn`
- **Dashboard & User Interface**: `Streamlit`, `Plotly`
- **Testing & Quality Assurance**: `pytest`

---

## Repository Architecture & Core Rules

All contributors and AI agents must strictly adhere to the following rules:

### 1. Inspect Real Data Before Making Assumptions
- **Empirical Verification First**: Never assume schemas, column casing, date formats, or sensor sampling rates without inspecting the actual raw files.
- **Observed Repository Realities**:
  - *Plant 1 Generation*: 68,778 rows, 22 inverters (`SOURCE_KEY`), date format `%d-%m-%Y %H:%M` (day-first).
  - *Plant 1 Weather*: 3,182 rows, 1 sensor key (`SOURCE_KEY`), date format `%Y-%m-%d %H:%M:%S`.
  - *Plant 2 Generation*: 67,698 rows, 22 inverters (`SOURCE_KEY`), date format `%Y-%m-%d %H:%M:%S`.
  - *Plant 2 Weather*: 3,259 rows, 1 sensor key (`SOURCE_KEY`), date format `%Y-%m-%d %H:%M:%S`.
  - Missing intervals and nighttime zero-irradiance readings must be handled explicitly and intentionally.

### 2. Prevent Future Data Leakage
- **Chronological Splitting Only**: Never use random `train_test_split` or standard k-fold cross-validation on time-series records. All train/validation/test partitions must strictly follow temporal order (e.g., train on prior weeks, evaluate on subsequent weeks).
- **Transformation Boundaries**: Fit all scalers, encoders, and feature imputation logic *strictly* on training data slices. Never fit or transform across split boundaries.
- **Rolling & Lag Features**: Target-based or lagged predictors must use strictly prior timestamps ($t - 1, t - 2$) to eliminate lookahead bias.

### 3. Validate Joins to Prevent Row Multiplication
- **Key Cardinality Verification**:
  - Generation data contains 22 inverters per 15-minute timestamp.
  - Weather data contains 1 weather station sensor per 15-minute timestamp with its own distinct `SOURCE_KEY`.
  - Joins between generation and weather data must be executed on `(DATE_TIME, PLANT_ID)` (after datetime normalization), **never** joining on `SOURCE_KEY`.
- **Pre- and Post-Join Assertions**: Always assert that post-join row counts equal pre-join generation row counts (e.g., `len(merged_df) == len(gen_df)`). Multiplied rows distort statistics and invalidate model training.

### 4. Never Invent Metrics or Report Phantom Experiments
- **Zero Hallucination Policy**: Do not fabricate validation metrics (MAE, RMSE, $R^2$), benchmark scores, or operational shortfall estimates.
- **Execution Proof**: Every reported metric must be directly produced by executable code, verified via script outputs, and backed by automated tests.

### 5. Distinguish Candidate Anomalies from Confirmed Hardware Faults
- **Honest Terminology**: ML model residuals and threshold flags identify **candidate underperformance** or **anomalous intervals**.
- **Domain Context**: Underperformance can stem from soiling, localized shading, inverter clipping, sensor drift, grid curtailment, or equipment malfunctions. Never label a candidate anomaly as a "confirmed inverter failure" without physical inspection logs or ground-truth maintenance telemetry.

### 6. Keep Raw Datasets and Secrets Out of Version Control
- All raw CSV/Parquet files (`data/raw/`, `*.csv`), environment configs (`.env`), and credentials must remain untracked in `.gitignore`.
- Only sanitized schema definitions, processing pipelines, and synthetic or minimal test fixtures may be committed.

### 7. Work in Small Milestones with Tests and Explanations
- Develop modular, single-responsibility components with accompanying `pytest` unit tests.
- Explain trade-offs, assumptions, and validation metrics transparently at each milestone before proceeding to subsequent modules.
