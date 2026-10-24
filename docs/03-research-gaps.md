# 03 — Research Gaps and Paper Strategy

Decision date: 2026-10-24. Evidence for every claim is in
[02-literature-review.md](02-literature-review.md).

## 1. What is no longer a gap (do not claim these)

| Claim | Why it is taken |
|---|---|
| "First ML/DL forecasting of Indian groundwater" | Malakar et al. 2021 (5 367 wells, LSTM) |
| "Benchmark of ML models on Indian wells" | Alphoenixx 2026 release uses **the same Kaggle file**: RF, XGBoost, LSTM, GRU, Chronos-2, conformal, risk BSS, spatial CV |
| "Zero-shot foundation models for groundwater" | Alphoenixx 2026 (Chronos-2, India); Kim et al. 2026 (TimesFM-3/Chronos-2/Moirai-2, Korea) |
| "TFT for groundwater" | Thames Basin 2024; German 5 300-well study (TFT trails N-HiTS) |
| "SHAP explanations for groundwater" | Common (review [1]); Alphoenixx has SHAP for RF/XGB at 4 horizons |
| "GA/PSO pumping optimisation" | Mature field; and impossible to do honestly without abstraction data |

## 2. Ranked gaps

Scoring: **N** = novelty (evidence of absence), **F** = feasibility with free data in ≤ 3 months,
**I** = impact on a water manager's decision. 1–5 each.

| Rank | Gap | N | F | I | Evidence |
|---|---|---|---|---|---|
| **G1** | **Does monsoon forcing add skill to national-scale Indian GWL forecasts, and how far ahead?** Proper gridded rainfall (IMD 0.25°) accumulated between campaigns, SPI-3/6/12, ENSO (Niño 3.4) and IOD (DMI) teleconnections, plus an "oracle future rainfall" experiment that bounds the value of a perfect monsoon forecast | 5 | 4 | 5 | Prior India null result is built on single-day snapshots (median 3.4 mm/yr); ENSO/IOD + India GWL prediction: 0 hits; Korean TSFM study shows known-future forcing is the dominant skill source but used 3–48 wells in a non-monsoon climate |
| **G2** | **Conditional calibration of uncertainty by aquifer depth.** Global conformal covers 88 % for shallow and 44 % for deep wells; depth-Mondrian restores 75–78 % in every class, with narrower intervals for shallow wells and honestly wider ones for deep wells | 4 | 5 | 4 | No GWL-level conformal paper in peer review; Alphoenixx's Mondrian is by region and history tercile; our pilot result |
| **G3** | **Decision value of probabilistic groundwater-drought warnings** (cost–loss relative economic value; trigger thresholds for Atal Bhujal / Gram-Panchayat water-security plans) | 5 | 5 | 5 | "cost-loss" / "relative economic value" + groundwater: 0 hits; Atal Bhujal has no published forecasting DSS |
| G4 | **Telemetry–manual fusion**: do 922 DWLR wells (6-hourly to daily, 2023–25) improve forecasts at neighbouring quarterly wells? | 5 | 3 | 4 | No ML on CGWB DWLR found; Alphoenixx uses a quarterly panel to 2023 |
| G5 | **AlphaEarth embeddings as static well descriptors** to close the spatial-transfer gap (Alphoenixx: +17 % RMSE nationally and +69 % in the IGP under spatial CV) | 5 | 3 | 4 | [3] used AlphaEarth only for a single-year spatial map; no temporal GWL use |
| G6 | **Joint quantity–quality** (level ↔ fluoride/EC/nitrate) for Andhra Pradesh using the unused CGWB quality file | 4 | 3 | 4 | No joint level-quality ML model found; [5] does quality only |
| G7 | **Systematic feature-selection comparison** (filter / RFE / FFS / SHAP-based) | 4 | 5 | 2 | Explicitly called out in review [1] |

## 3. Ideas beyond the current project

| Idea | Why it matters | Main obstacle |
|---|---|---|
| **Electricity as an abstraction proxy** (DISCOM feeder kWh × 4.7–6.0 m³/kWh) → first data-driven pumping-response model for Indian aquifers, which would make a *real* pumping optimisation possible | Turns forecasting into management; replaces the invented "pumping factor" | Feeder-level data needs a DISCOM data-sharing agreement (start with AP/Telangana) |
| **Forecast-informed stage-of-extraction categories** (CGWB GEC-2015: safe / semi-critical / critical / over-exploited) a year before the biennial assessment | Directly used by Indian regulators | Block-level GEC data must be scraped from INGRES; needs specific-yield maps |
| **Physics-guided hard-rock aquifer models** (water-table-fluctuation equation as loss, specific yield from CGWB aquifer maps) | Peninsular India is mostly hard rock, unlike the Korean/German alluvial settings in the physics-loss papers | Specific-yield data quality |
| **Grounded multilingual advisories** (Telugu/Hindi) generated *only* from calibrated forecasts, with a faithfulness audit | LLM water advice exists only as concept papers | Needs a user study for impact claims; keep as an appendix/demo |
| **GRACE-FO + well fusion** for storage forecasting at block scale | Links point wells to aquifer-scale storage | 0.5°–1° resolution vs block size |

## 4. Recommended paper (P1)

**Working title:** *Monsoon forcing, depth-aware calibration and decision value in
national-scale groundwater forecasting for India*

**Research questions**
1. **RQ1 (G1).** How much skill does properly accumulated monsoon forcing add over groundwater
   memory alone, at 3, 6 and 12 months? How much more would a perfect monsoon forecast add
   (oracle bound), and how much do ENSO/IOD indices add at long leads?
2. **RQ2 (G2).** Are conformal intervals calibrated *conditionally* across aquifer-depth classes
   and regions, and does depth-Mondrian (and adaptive) conformal fix it?
3. **RQ3 (G3).** What is the relative economic value of exceedance warnings for a range of
   cost–loss ratios, and which probability triggers maximise it?

**Contributions**
1. A documented, reproducible cleaning protocol for the widely used CGWB/Kaggle file
   (sign harmonisation, campaign grid, why its weather columns cannot be used as forcing).
2. The first national skill decomposition for monsoon India: memory → past forcing →
   future forcing (oracle) → teleconnections, by horizon, depth class and region.
3. Evidence that marginal coverage hides depth-conditional failure, and a fix.
4. The first cost–loss evaluation of groundwater warnings, giving actionable trigger probabilities.

**Pilot evidence already in hand** (memory-only XGBoost, see 04):
- Skill vs persistence: **+0.52 (3 mo), +0.54 (6 mo), +0.14 (12 mo)**. The model beats
  anomaly persistence (+0.40) at 3 months, but skill collapses at 12 months, which is exactly
  where forcing should help.
- Global conformal: 80.0 % marginal coverage, but **44 % for ≥ 40 m vs 88 % for < 5 m**.
  Depth-Mondrian: 75–78 % in every class (median width 3.1 m for shallow wells, 13.5 m for deep
  wells, versus one 4.2 m width for all). The remaining shortfall motivates adaptive conformal (Phase 3).
- Early-warning Brier skill: **+0.17 (3 mo) → +0.03 (12 mo)**.

**Data still to acquire (free):** IMD 0.25° daily gridded rainfall and 1° temperature
(1994–2025, via `imdlib`); Niño 3.4 and DMI monthly indices (NOAA PSL); IMD seasonal
monsoon outlooks (for a realistic-forecast arm); and a refresh of manual-well levels from
India-WRIS, because most manual records in the Kaggle file stop in 2022–2023 (needed for an
operational, current early-warning demonstration).

**Target venues:** *Hydrology and Earth System Sciences*, *Water Resources Research*,
*Journal of Hydrology*, *Environmental Modelling & Software*. A fallback with a faster review
is *Journal of Hydrology: Regional Studies*.

**Required citations / positioning:** cite Alphoenixx 2026 as the closest prior benchmark.
State plainly that its climate null result is limited by snapshot forcing, and show the
difference empirically by running its feature construction alongside ours.

## 5. Follow-up papers

- **P2 (G5 + G4):** "Satellite embeddings and telemetry for forecasting unmonitored and newly
  monitored wells" — spatial-transfer evaluation with blocked spatial CV.
- **P3 (G6):** joint level–quality model for Andhra Pradesh fluoride risk under drawdown.

## 6. What changes in the system

| Old component | New role |
|---|---|
| "TFT" engine | Replaced by a time-blocked benchmark (naive baselines → global GBM → TSFM as a reference) |
| PICP 99.87 % | Conformal intervals with coverage reported per depth class |
| SHAP on lag features as "policy drivers" | SHAP used to *decompose skill sources* (memory vs forcing) |
| GA/PSO pumping quotas | **Removed** until an abstraction proxy exists; replaced by probabilistic early warning and a cost–loss trigger analysis |
| NLG policy brief | Generated from calibrated outputs only (forecast, interval, exceedance probability, trigger) |
