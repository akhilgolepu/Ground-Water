# 01 — Project Audit (2026-10-24)

This audit records what the original AquaSense pipeline (Phases 1–5 in the top-level
README) actually computes, verified against the committed code and data. It is the reason
the research pipeline in `src/research/` exists.

## Verdict

The legacy pipeline does not forecast groundwater. Every number in the README
(R² 0.9998, MAE 0.2566 m, PICP 99.87 %, SHAP/VSN rankings, policy briefs, GA/PSO quotas)
was computed on a constant per-well value. Those results must not be used in a paper.

## Critical defects

| # | Defect | Evidence | Location |
|---|---|---|---|
| 1 | **Wrong target.** The column picker keyword-matches `'depth'` and selects `wellDepth` (borehole construction depth, constant per station) instead of the real water level `target`. | Feature-matrix "depth" has a median of **1 distinct value per well** and the same distribution as `wellDepth` (mean 53.5 m, max 537.2 m). Copying `lag_1` gives **RMSE 0.0000 on the test split** (100 % exact). | `src/data/data_preprocessing_pipeline.py:42` |
| 2 | **Fabricated timestamps.** Dates are `2015-01-01 + row_number months`; the real `datetime` column is ignored. | Feature matrix runs to **2051-07**; real data spans 1994-01 → 2025-09 with mixed daily and quarterly sampling. | `src/data/data_preprocessing_pipeline.py:56` |
| 3 | **Meteorology dropped.** The parser returns only 5 columns, so rainfall/temperature never reach the model; API/SPEI are never computed. | `feature_matrix` has no rainfall, API or SPEI columns. | same file, `return df[[...]]` |
| 4 | **Placeholder static features.** Elevation 250, K 1.5, porosity 0.25, land cover "Agricultural" for every well. | `nunique == 1` for all four. | `src/data/feature_engineering.py:111` |
| 5 | **No-op imputation.** Spline/Kalman have no gaps to fill on a fabricated grid; the kriging surface is computed and discarded. | — | `src/data/preprocessing.py` |
| 6 | **"TFT" is not a TFT.** Input is a single time step (`unsqueeze(1)`), so the LSTM and attention run on a length-1 sequence; output is one step, not multi-horizon. The sequence dataset class is unused. | — | `src/models/tft_model.py`, `src/models/dataset.py` |
| 7 | **Training script cannot run.** It unpacks 6 values from a function returning 7, so the committed metrics file was not produced by the committed code. | `ValueError` on unpack | `src/models/train.py:103` |
| 8 | **Misread metrics.** 99.87 % coverage of an 80 % interval means the intervals are miscalibrated (far too wide). XGBoost has a lower RMSE than the "TFT" (0.93 vs 2.91 m). README λ = 10⁴ vs 500 in code. | `models/phase3_benchmark_metrics.json` | README |
| 9 | **Optimisation has no physics or data.** "Pumping" adds ±1 m to `lag_1`. The decision is a single scalar α ∈ [0, 1] (a grid search solves it exactly). One W_safe = 15 m is applied to every well, so deep wells always get α = 0. | — | `src/optimization/metaheuristic_solver.py` |
| 10 | **Dashboard numbers are not model outputs.** Forecast = q50 + linear trend with hand-built bands; "attention weights" are relabelled VSN importances; the simulator uses hard-coded coefficients (0.05, 0.03, 12 500 m³ per %). | — | `backend/app/services.py:300`, `:503` |

## Data facts established during the audit

| Property | Value |
|---|---|
| Raw rows / stations | 416 952 / 6 440 (1994-01-05 → 2025-09-27) |
| Networks | 5 518 **manual** wells (quarterly campaigns: Jan, May, Aug, Nov) + 922 **DWLR telemetry** wells (median gap ≤ 2 days, mostly 2023–2025) |
| Sign convention | Manual wells report **positive** m bgl; DWLR wells report **negative** values (95.5 % negative) |
| Gross errors | `target` spans −2014 to +2430 m; 152 values with \|x\| > 200 m |
| Weather columns | Single-day values at the observation date (NASA-POWER-like names `t2m`, `t2m_max`, `t2m_min`). For manual wells the 4 campaign-day rainfall values sum to a **median 3.4 mm per well-year**, so they cannot represent seasonal forcing |
| Encoded categoricals | `State_encoded`, `District_encoded`, `wellAquiferType_encoded` have only 2 values each and are unusable |
| Unused data | `gwq_chemical_parameter_manual_cgwb_ap_1961_2025 (1).csv` — 10 950 Andhra Pradesh water-quality samples |

## What replaced it

`src/research/ingest.py` (corrected ingestion) and `src/research/benchmark.py` (time-blocked
benchmark with naive baselines and conformal uncertainty). See
[04-methodology-and-pilot-results.md](04-methodology-and-pilot-results.md).

The legacy modules and backend endpoints were **retired in Phase 5** (2026-10-24) and moved to
`legacy/` (`legacy/src/...`, `legacy/backend/`, `legacy/models/`, `legacy/data/feature_matrix.*`,
`legacy/requirements.txt`, `legacy/notebooks/`). File paths in the table above refer to their
original locations; prepend `legacy/` to find them. The dashboard is fully static and reads only
`frontend/public/data/`.
