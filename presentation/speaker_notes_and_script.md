# Presentation Script & Speaker Notes: Academic Evaluation Round II

**Project**: Adaptive Solar Performance & Loss Intelligence
**Format**: 10 Slides • 16:9 Widescreen
**Target Duration**: ~8–10 Minutes (approx. 50–60 seconds per slide)
**Presenter Persona**: Second-Year CSE Student / Engineering Lead (Technically confident, grounded in empirical evidence, transparent about physical limitations)

---

## Slide 1 — Title and Project Vision

- **Slide**: Slide 1 — Title, Subtitle, Scope Pill Cards (Phase I, Phase II, Phase III)
- **Target Time**: 0:00 – 0:50 (50 seconds)
- **Central Message**: Introduce the project, establish the core value proposition, and clarify the implemented scope versus the future roadmap right up front.

### Spoken Script
> "Good morning, respected evaluators. Today I am presenting our mini-project: **Adaptive Solar Performance & Loss Intelligence**.
>
> In photovoltaic solar installations, monitoring is typically reduced to watching power meters. But solar generation is inherently volatile—it rises and dips constantly with the sun and clouds. Our project asks a more fundamental engineering question: *Given current ambient weather and physical system characteristics, how much power SHOULD an inverter be generating, how much energy is being lost if it underperforms, and which systems require urgent physical inspection?*
>
> As shown on this opening slide, our project is organized into three distinct phases:
> - **Phase I** is our core implemented platform: an end-to-end intelligence pipeline covering 44 utility-scale inverters, featuring a 10-feature Random Forest baseline, dual-baseline anomaly detection, and a 45-minute persistence filter.
> - **Phase II** is our implemented residential validation track: ingesting and reconciling real 5-minute telemetry from an on-premise Havells 5.0 kW rooftop inverter while enforcing strict privacy governance.
> - **Phase III** represents our planned roadmap: incorporating numerical weather prediction for day-ahead forecasting and authorized live inverter streaming.
>
> Everything I demonstrate today in Phases I and II is fully implemented, empirically verified against real datasets, and backed by 46 automated unit tests."

- **Key Technical Details to Understand**:
  - The project does *not* claim deep learning or real-time IoT hardware streaming. It is an end-to-end data-driven ML and loss-accounting intelligence pipeline.
  - The separation between Phase I, II, and III shows maturity—evaluators respect teams that clearly distinguish what is completed from what is planned.
- **Transition to Next Slide**:
  > *"To understand why our approach is necessary, let's look at the fundamental operational challenge in solar telemetry."*

---

## Slide 2 — Problem and Motivation

- **Slide**: Slide 2 — The False Alarm Trap vs. The Invisible Degrade
- **Target Time**: 0:50 – 1:50 (60 seconds)
- **Central Message**: Explain why falling solar power does not automatically imply a fault, and expose the two fatal failure modes of traditional static thresholding.

### Spoken Script
> "When solar power drops, operators face a dilemma. Is the drop caused by a transient cloud passing overhead, or did a string of solar panels trip?
>
> Standard industry monitoring relies on simple static rules—for example, alerting if active power drops below 0.2 kW. This approach suffers from two severe failure modes:
>
> First, **The False Alarm Trap**: On partly cloudy days, passing cloud shadows cause sharp, temporary drops in generation lasting 5 to 15 minutes. Static rules fire off hundreds of nuisance alarms a day. Operators suffer alarm fatigue and eventually silence the alerts. In our own test dataset, we measured that **47.6 kilowatt-hours** of deviation was purely transient cloud noise that should never trigger a maintenance crew.
>
> Second, **The Invisible Degrade**: Suppose an inverter suffers a 30% partial string disconnection, localized shading, or progressive dust soiling. At midday under strong sunlight, it might still produce 1.0 kW. Because 1.0 kW is well above the low-power cutoff, static thresholds are completely blind to the defect. Over weeks or months, this silent degradation accumulates into massive lost revenue.
>
> Our platform solves this with four targeted capabilities: predicting what an inverter *should* generate given current sun and temperature; benchmarking it against concurrent sibling inverters; requiring deviations to persist over time; and integrating lost power into physical kilowatt-hours so maintenance teams know exactly where the biggest financial losses are occurring."

- **Key Technical Details to Understand**:
  - *Transient vs. Persistent*: A 15-minute cloud is transient; a 3-hour string failure is persistent.
  - *Masked Faults*: Midday power can be high in absolute terms ($1.0\text{ kW}$) yet severely underperforming relative to an expected $1.4\text{ kW}$.
- **Transition to Next Slide**:
  > *"Let's look at how our end-to-end system architecture turns raw telemetry into actionable loss intelligence."*

---

## Slide 3 — Project Architecture

- **Slide**: Slide 3 — Six-Stage Pipeline + Residential Track Callout
- **Target Time**: 1:50 – 2:50 (60 seconds)
- **Central Message**: Walk through the six sequential pipeline stages from ingestion to the dashboard, highlighting data leakage prevention and physical unit consistency.

### Spoken Script
> "Here is our complete system architecture, consisting of six modular stages:
>
> 1. **Data Ingestion & Unit Reconciliation**: We ingest telemetry from two commercial solar plants. Crucially, we discovered and resolved a 1,000-times unit discrepancy in the raw Kaggle metadata, scaling raw Watts to canonical kilowatts, and joined external weather archives while asserting zero row multiplication.
> 2. **Leakage-Safe Feature Engineering**: We construct cyclical solar time encodings and thermal gradient features while strictly excluding contemporaneous electrical outputs like DC power or daily yield.
> 3. **Chronological Splitting**: We split all time-series records in strict temporal order—60% for training, 20% for validation, and 20% for out-of-time testing—keeping records from the same timestamp strictly together.
> 4. **Expected Power Modeling**: We train regression models to predict expected AC power in kW. Our selected baseline Random Forest pipeline achieves an out-of-time test MAE of just 70.4 Watts.
> 5. **Dual-Baseline Anomaly Detection**: We compute residuals against both the individual inverter's ML baseline and a capacity-normalized peer cohort, then pass deviations through a 45-minute persistence filter.
> 6. **Loss Accounting & Prioritization**: We integrate power deficits over interval durations to calculate lost energy in kWh and rank inverters by urgency on an interactive 6-view Streamlit dashboard.
>
> Notice at the bottom: our Phase II residential validation track runs alongside as an independent pipeline, proving the framework can adapt to residential rooftop exports without contaminating the commercial training models."

- **Key Technical Details to Understand**:
  - *Chronological splitting*: Splitting by time ensures the model never peeks into the future.
  - *Pre/Post Join assertions*: `len(merged) == len(gen_df)` ensures weather joins never duplicate inverter rows.
- **Transition to Next Slide**:
  > *"Now, let's dive into the empirical data engineering and our physical unit discovery."*

---

## Slide 4 — Dataset and Preprocessing

- **Slide**: Slide 4 — Physical Unit Reconciliation, Dataset Volumes, Leakage Safeguards
- **Target Time**: 2:50 – 3:50 (60 seconds)
- **Central Message**: Explain the 1,000x Kaggle unit error discovery, literature cross-referencing, dataset volumes, and target leakage elimination.

### Spoken Script
> "A major engineering contribution of our project was identifying and correcting a critical flaw in the public dataset.
>
> In the Kaggle solar dataset, the column `AC_POWER` was documented as kilowatts. But when we inspected the raw data, the values peaked at around 1,410. If an inverter were truly producing 1,410 kW, that would be a utility sub-station, yet the concurrent plant total was only 29 thousand.
>
> We cross-referenced peer-reviewed literature published in Oxford Academic's *Clean Energy* journal in 2026, which studied these exact two plants in Karnataka, India. The paper confirmed the plant comprises 22 Growatt MIC 1500TL-X string inverters, each rated at 1.5 kW AC, with an array total of 33 kW. This proved conclusively that the raw numbers were in **Watts**, not kilowatts! We established canonical scaling across the entire project: $\text{AC\_POWER\_KW} = \text{AC\_POWER} / 1000.0$. Failing to catch this would have magnified all energy and financial loss estimates by a factor of one thousand.
>
> In total, the utility dataset provides **77,098 merged daylight records** across 44 inverters over 34 days. Our private residential dataset contributes **997 synchronous readings** at 5-minute sampling over 7 days with zero nulls.
>
> Finally, we enforced strict **target leakage elimination**: features like `DC_POWER`, `DAILY_YIELD`, and `TOTAL_YIELD` were completely removed from model inputs. Including contemporaneous DC power produces a misleading $R^2 > 0.999$, but makes the model useless for detecting inverter faults because DC power drops when the inverter fails."

- **Key Technical Details to Understand**:
  - *Kaggle error*: Raw values maxed at 1,410.95. That's 1.41 kW (under rated 1.5 kW), proving it was recorded in Watts.
  - *Leakage*: If the model uses $P_{\text{DC}}$ to predict $P_{\text{AC}}$, it learns the inverter efficiency curve ($\approx 97\%$). If the inverter trips, both DC and AC drop together, so the residual remains zero—meaning the model completely fails to catch the fault!
- **Transition to Next Slide**:
  > *"With clean, leakage-free data established, let's examine our machine learning methodology and out-of-time evaluation."*

---

## Slide 5 — AIML Methodology & Model Selection

- **Slide**: Slide 5 — The Regression Task, 10 Features, Out-of-Time Benchmark Table
- **Target Time**: 3:50 – 4:50 (60 seconds)
- **Central Message**: Explain why regression is used, detail the 10 leakage-free features, and present the benchmark table showing why Random Forest was selected on the validation split.

### Spoken Script
> "Why do we frame this as regression rather than classification? In real solar operations, degradation is continuous—soiling can cause a 5% drop, partial shading a 20% drop, or an electrical trip a 100% drop. Furthermore, raw SCADA data lacks ground-truth maintenance logs to label binary classes. Regression gives us a continuous expected baseline, allowing us to compute real-valued residuals that directly convert to lost energy in kilowatt-hours.
>
> We predict active power using 10 exogenous features: onsite pyranometer irradiance, ambient temperature, module temperature, the thermal difference between module and air, cyclical sine and cosine encodings for time-of-day and day-of-year, and categorical embeddings for plant and inverter identity.
>
> As you can see in the benchmark table, we evaluated Random Forest, Histogram Gradient Boosting, and Ridge regression across both baseline and weather-enriched configurations. All model selection was conducted strictly on the **validation partition**—from June 4th to June 11th.
>
> The Baseline Random Forest achieved the lowest validation MAE at **0.1055 kW**. When subsequently evaluated on the held-out test week—June 11th to 17th—it achieved an MAE of **0.0704 kW**, or just **70.4 Watts**. Across a 1,500-Watt inverter, an average error of 70 Watts represents just 4.7% of nameplate capacity, with an $R^2$ of **0.7337** and a WAPE of **16.46%**."

- **Key Technical Details to Understand**:
  - *Feature Count*: Exactly 10 features.
  - *Model Selection Integrity*: The decision to select Random Forest was based on the *validation* score (0.1055 kW), never on the test score. The test set was touched only once for the final reported evaluation.
- **Transition to Next Slide**:
  > *"Looking closer at our experimental results reveals an interesting scientific finding regarding external weather data."*

---

## Slide 6 — Experimental Findings & The Weather Paradox

- **Slide**: Slide 6 — The Weather Enrichment Experiment & Honest Metric Interpretation
- **Target Time**: 4:50 – 5:45 (55 seconds)
- **Central Message**: Explain why adding regional ERA5 weather reanalysis degraded performance (+1.99% error), apply Occam's razor, and interpret metrics honestly.

### Spoken Script
> "An important scientific experiment we conducted was **weather enrichment**. We integrated hourly ERA5 reanalysis weather from Open-Meteo—including regional air temperature, relative humidity, total cloud cover, and wind speed—forward-interpolated to 15-minute intervals.
>
> Counter-intuitively, adding regional weather slightly **increased** validation error by +1.99%, raising MAE from 0.1055 to 0.1076 kW.
>
> The physical reason is straightforward: ERA5 reanalysis data is modeled on a regional grid of approximately 11 by 11 kilometers. It captures macro-scale weather fronts, but it cannot resolve a localized cloud shadow passing over a specific solar array. In contrast, the onsite pyranometer and module thermocouples capture direct solar irradiance and cell temperature at the exact array location with zero spatial lag.
>
> Following **Occam's razor**, we retained the simpler 10-feature baseline. It is more accurate, less computationally complex, and eliminates dependence on an external network API.
>
> We also emphasize honest metric communication: an $R^2$ of 0.7337 across an out-of-time test week under dynamic monsoon-transition weather indicates strong predictive capability. We intentionally avoid calling $R^2$ 'accuracy', as $R^2$ measures explained variance, while MAE and WAPE measure operational magnitude."

- **Key Technical Details to Understand**:
  - *Occam's razor in ML*: When a simpler model performs equally or better than a complex model with extra features, always choose the simpler model.
  - *Spatial Resolution*: 11 km grid resolution vs. a 100-meter physical solar farm footprint.
- **Transition to Next Slide**:
  > *"Now let's examine how we translate model residuals into actionable loss intelligence."*

---

## Slide 7 — Underperformance & Loss Intelligence

- **Slide**: Slide 7 — Dual-Baseline Equations, Persistence Filtering, Fleet Loss Breakdown
- **Target Time**: 5:45 – 6:50 (65 seconds)
- **Central Message**: Detail the dual-baseline mathematical formulation, the 45-minute persistence filter, and the held-out test loss numbers (89.44 kWh persistent loss vs. 47.58 kWh noise suppressed).

### Spoken Script
> "To detect underperformance without being fooled by weather or chronic degradation, we employ a **dual-baseline architecture**:
>
> 1. First, the **Inverter ML Baseline**: We calculate the residual as expected power minus actual power: $\text{Residual} = P_{\text{expected}} - P_{\text{actual}}$. A positive residual indicates generation deficit.
> 2. Second, the **Capacity-Normalized Peer Cohort**: If an inverter has been chronically degraded for weeks, an inverter-conditioned ML model might learn that underperformance as 'normal'. To prevent this, we normalize all inverters by their 99th-percentile capacity rating ($C_i$) and compute the median generation across all concurrent peers in the same plant: $P_{\text{cohort}} = \text{Median}(\{P_j / C_j\}) \times C_i$.
>
> If either baseline indicates a deficit exceeding our validation-calibrated thresholds, the interval is flagged. However, to prevent alarm fatigue, we enforce a strict **temporal persistence filter**: the deficit must persist for at least **3 consecutive 15-minute intervals**—meaning at least **45 minutes**. If data is missing, the counter resets immediately.
>
> Look at the operational accounting results on our held-out test week:
> - The fleet produced **1,736.3 kWh**, closely matching the model-predicted baseline of **1,724.5 kWh**.
> - Raw instantaneous deviations totaled 137.0 kWh. But our persistence filter safely suppressed **47.58 kWh of transient cloud fluctuations**—saving maintenance crews from dozens of false alarms.
> - This isolated **89.44 kWh of persistent, actionable shortfall**, representing a **5.19% fleet generation loss**.
> - Furthermore, Plant 2 accounted for **92.6% of all persistent losses**, immediately directing field engineers to specific chronic inverters like `Qf4GUc1pJu5T6c6`."

- **Key Technical Details to Understand**:
  - *Why capacity-normalize peers?* Inverters have slightly different capacities due to module counts (e.g. 1.25 kW vs. 1.33 kW). Dividing by $C_i$ ensures fair comparison before multiplying back by the target inverter's capacity.
  - *Energy Arithmetic*: $\Delta E = P \times \Delta t = P \times 0.25\text{ h}$.
- **Transition to Next Slide**:
  > *"All of this intelligence is delivered through our interactive Streamlit operations dashboard."*

---

## Slide 8 — Working Prototype Demonstration

- **Slide**: Slide 8 — 2x2 Grid of Dashboard Screenshots (Overview, Explorer, Prioritization, Sandbox)
- **Target Time**: 6:50 – 7:50 (60 seconds)
- **Central Message**: Showcase the running dashboard views, Apple-inspired aesthetics, interactive controls, and the synthetic testing sandbox.

### Spoken Script
> "Here you see genuine screenshots from our running Streamlit dashboard, designed following modern Apple-inspired interface principles—featuring deep graphite surfaces, translucent cards, restrained solar amber accents, and responsive Plotly charts.
>
> The interface is organized into six dedicated views:
> - **Top-Left (Overview & Loss Summary)**: Displays high-level fleet health cards, total measured generation, expected baseline, persistent loss percentage, and interactive facility breakdown charts.
> - **Top-Right (Plant & Inverter Explorer)**: Enables operators to drill down into any of the 44 inverters. It plots 15-minute actual power against the ML baseline and peer cohort, marking persistent anomaly event windows with clear visual evidence badges.
> - **Bottom-Left (Inverter Loss Prioritization)**: An operational ranking table that sorts inverters across both plants by accumulated shortfall in kWh, loss percentage, and alert hours, with one-click CSV export for dispatch scheduling.
> - **Bottom-Right (Interactive Synthetic Sandbox)**: A testbench where operators or evaluators can inject simulated power drops—such as a 50% derate for 15 minutes, 30 minutes, or 60 minutes. It visually proves in real time that 1- and 2-interval transient drops are suppressed, while sustained drops immediately trigger persistent alarms and calculate energy shortfall."

- **Key Technical Details to Understand**:
  - The synthetic sandbox runs completely in-memory and does *not* alter historical data files.
  - The dashboard is running live right now on `http://localhost:8501`.
- **Transition to Next Slide**:
  > *"In Phase II, we took these core principles and extended them to the residential rooftop domain."*

---

## Slide 9 — Phase II Residential Solar Intelligence

- **Slide**: Slide 9 — Real Havells 5.0 kW Inverter Audit, 3-Way Energy Reconciliation, Forecast Scorecard
- **Target Time**: 7:50 – 8:50 (60 seconds)
- **Central Message**: Present the empirical Havells export analysis, 3-way energy reconciliation, privacy scrubbing, and an honest forecast readiness scorecard.

### Spoken Script
> "In Phase II, we validated our architecture against a real residential rooftop installation using a private export from a **Havells 5.0 kW single-phase grid-tied string inverter**.
>
> We audited **997 synchronous readings** across 63 telemetry channels sampled at 5-minute intervals between October 20th and 26th, 2026. The data exhibited exceptional quality: zero null values and zero duplicate timestamps.
>
> Our pipeline established several critical findings:
> - **Privacy Enforcement**: Hardware serial numbers, internal device names, and account credentials are scrubbed dynamically during load; the raw file remains excluded from Git.
> - **Operating Characteristics**: Observed peak power was **3.58 kW** (71.6% of rated capacity). Exactly six overnight gaps occurred (~12 hours each), corresponding strictly to natural sunset sleep and sunrise wake-up; zero unexpected daytime communication dropouts occurred.
> - **Three-Way Energy Reconciliation**: We compared the cumulative odometer delta (**134.90 kWh**), the sum of daily reset counters (**134.94 kWh**), and our discrete trapezoidal power integral (**135.90 kWh**). The integral matched within +0.7%, proving our numerical integration is mathematically sound.
> - **Thermocouple Semantics**: We distinguished internal chassis (up to 61°C) and radiator heatsink (up to 62°C) sensors as measuring power conversion heat, not ambient air.
>
> On the right, our **Forecast Readiness Scorecard** transparently documents that day-ahead forecasting is designated as **Phase III roadmap work**. A 7-day export is valuable for baseline profiling, but cannot train a multi-season forecasting model without severe seasonal overfitting."

- **Key Technical Details to Understand**:
  - *Three-way reconciliation*: Shows mathematical rigor by validating three independent ways of calculating energy over the same 7 days.
  - *Honest Non-Claim*: Emphasize that we do *not* claim a completed residential day-ahead model because 7 days is insufficient for training seasonal solar prediction.
- **Transition to Next Slide**:
  > *"To conclude our presentation, let's review our technical contributions, limitations, and future roadmap."*

---

## Slide 10 — Conclusion, Roadmap & Questions

- **Slide**: Slide 10 — Key Accomplishments, Explicit Limitations, Phase III Roadmap
- **Target Time**: 8:50 – 9:45 (55 seconds)
- **Central Message**: Summarize major technical achievements, state physical limitations transparently, outline Phase III, and invite questions.

### Spoken Script
> "To conclude, our project delivers four concrete engineering contributions:
>
> 1. **Empirical Physical Grounding**: We discovered and resolved the 1,000x unit mislabeling in the public SCADA dataset, grounding our model targets in peer-reviewed physical literature.
> 2. **Leakage-Free ML Modeling**: Our 10-feature Random Forest baseline achieves an out-of-time test MAE of 70.4 Watts ($R^2 = 0.7337$) on strictly chronological splits.
> 3. **Actionable Loss Intelligence**: Our dual-baseline and 45-minute persistence filter successfully suppressed 47.6 kWh of transient cloud noise while isolating 89.44 kWh of actionable underperformance.
> 4. **Cross-Domain Validation**: We built a complete, production-grade 6-view Streamlit platform, backed by 46 automated tests, and extended it to residential rooftop systems.
>
> We also stand firmly by our **methodological limitations**: our observation windows (34 days utility, 7 days residential) represent early summer conditions and cannot be annualized; and because ground-truth maintenance tickets were unavailable, our detections are responsibly framed as **candidate underperformance events**, not confirmed hardware breakdowns.
>
> For Phase III, we plan to integrate localized NWP solar irradiance forecasts for day-ahead generation prediction and establish authorized live Modbus TCP telemetry streams.
>
> Thank you for your time and attention. We are ready for your questions and to demonstrate the live application."

- **Key Technical Details to Understand**:
  - Be proud of what is implemented (Phase I & II) while completely open about limitations. Evaluators award the highest viva marks for intellectual honesty and technical defense.
- **Presentation Finish**: Stop smoothly and wait for evaluators to ask questions.

---

## Summary Time Budget Table

| Slide | Topic | Target Duration | Running Time |
| :---: | :--- | :---: | :---: |
| **1** | Title, Value Proposition & Scope Boundaries | 50s | 0:00 – 0:50 |
| **2** | Problem, False Alarms & Masked Underperformance | 60s | 0:50 – 1:50 |
| **3** | End-to-End System Architecture Pipeline | 60s | 1:50 – 2:50 |
| **4** | Data Engineering, 1,000x Unit Fix & Leakage Rules | 60s | 2:50 – 3:50 |
| **5** | AIML Methodology, 10 Features & Benchmark Table | 60s | 3:50 – 4:50 |
| **6** | Weather Reanalysis Experiment & Metric Defense | 55s | 4:50 – 5:45 |
| **7** | Dual Baseline, 45m Persistence & Test Loss Numbers | 65s | 5:45 – 6:50 |
| **8** | Working Prototype Demonstration (4 Dashboard Views) | 60s | 6:50 – 7:50 |
| **9** | Phase II Residential Validation (Havells 5.0 kW Audit) | 60s | 7:50 – 8:50 |
| **10** | Key Contributions, Limitations & Defense Readiness | 55s | 8:50 – 9:45 |
| **Total**| **Complete Technical Defense** | **~9 min 45 sec** | **Under 10 Minutes** |
