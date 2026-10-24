# 06 — Phase Plan

Goal: submit paper P1 — *Monsoon forcing, depth-aware calibration and decision value in
national-scale groundwater forecasting for India* (gaps G1 + G2 + G3, see
[03-research-gaps.md](03-research-gaps.md)) — with a reproducible pipeline and a dashboard that
shows the paper's results.

Every phase has steps, deliverables and an exit check. A phase is done only when its exit
check passes and [05-worklog.md](05-worklog.md) records it. All Python runs in `conda activate anpr`.

| Phase | Name | Answers | Depends on |
|---|---|---|---|
| 0 | Foundations and reproducibility ✅ 2026-10-24 | — | — |
| 1 | Forcing data and features ✅ 2026-10-24 | Data for RQ1 | 0 |
| 2 | Skill decomposition experiments | RQ1 | 1 |
| 3 | Uncertainty calibration | RQ2 | 2 |
| 4 | Decision value of warnings | RQ3 | 3 |
| 5 | Dashboard integration | — | 2–4 |
| 6 | Manuscript and release | — | 2–5 |

---

## Phase 0 — Foundations and reproducibility

| Step | Action | Deliverable |
|---|---|---|
| 0.1 | Move every split year, horizon, path and seed into one config module, and make ingestion and the benchmark read it | `src/research/config.py` |
| 0.2 | Pin the research environment (versions taken from `anpr`) | `requirements-research.txt` |
| 0.3 | Unit tests for the parts that broke before or could leak: sign harmonisation, campaign mapping (Dec → next Jan), outlier rules, gap-free grid, **expanding climatology without look-ahead**, **target shift without leakage**, split boundaries, conformal quantile, Sen/Mann–Kendall | `tests/research/` (pytest) |
| 0.4 | Repo hygiene: ignore and untrack `__pycache__`/`*.pyc`; ignore external raw downloads | `.gitignore` |
| 0.5 | Data card: provenance, fields, sign conventions, sampling, known defects, licence questions | `docs/data-card.md` |
| 0.6 | One-command reproduction script that runs ingestion → benchmark → checks | `scripts/reproduce.sh` |

**Exit check:** `pytest tests/research` passes, and `scripts/reproduce.sh` regenerates the pilot
numbers in 04 exactly (RMSE 2.406 m at h = 1).

## Phase 1 — Forcing data and features

| Step | Action | Deliverable |
|---|---|---|
| 1.1 | Get IMD 0.25° daily gridded rainfall for 1994–2025 (`imdlib`). Fallback if the IMD server fails: CHIRPS 0.05° or ERA5-Land monthly | `data/external/imd/rain/` (git-ignored) |
| 1.2 | Get IMD 1° daily Tmax/Tmin for the same years | `data/external/imd/tmax`, `tmin` |
| 1.3 | Get monthly Niño 3.4 and DMI (IOD) indices from NOAA PSL | `data/external/climate_indices.parquet` |
| 1.4 | Map each well to its grid cell and aggregate to **monthly** totals/means per cell (one row per cell-month, not per well) | `data/processed/forcing_monthly.parquet` |
| 1.5 | Build causal features per (well, origin campaign): rain since the previous campaign; rain over the last 3/6/12 months; last completed JJAS monsoon total and its anomaly; SPI-3/6/12 (gamma fit on ≤ 2015 only); temperature anomaly; Niño 3.4 and DMI at lags 0, 3, 6 months | `data/processed/forcing_features.parquet` |
| 1.6 | Build the **oracle** arm: rain between origin and target (known only in hindsight; upper bound on the value of a perfect monsoon forecast) | same table, `oracle_*` columns |
| 1.7 | Build the **snapshot control** arm: the source file's single-day rainfall summed the way prior work did | same table, `snap_*` columns |
| 1.8 | Sanity checks: (a) all-India JJAS totals per year vs IMD's published seasonal departures (e.g. 2019 excess, 2023 deficit); (b) wells' monsoon recharge (May → Nov rise) should correlate positively with JJAS rain at the well; (c) no forcing value after the origin date in non-oracle columns | `reports/forcing/sanity.json`, figures |
| 1.9 | Document sources, licences, processing and checks | `docs/07-forcing-data.md` |

**Exit check:** sanity checks (a)–(c) pass, every manual well with a campaign series has forcing
coverage ≥ 95 % of its months, and a unit test proves non-oracle features use no data after the origin.

## Phase 2 — Skill decomposition (RQ1) — ✅ done (see 08)

| Step | Action |
|---|---|
| 2.1 | Nested model arms on the same rows: **M0** memory → **M1** + past forcing → **M2** + teleconnections → **M3** + oracle future rain; control **C** = M0 + snapshot rainfall |
| 2.2 | Global GBM (XGBoost/LightGBM) for every arm, with the same hyper-parameter search per arm on a 2013–2015 inner validation block |
| 2.3 | Reference models for comparability with prior work: Random Forest, N-HiTS, Chronos-2 zero-shot (with and without covariates) |
| 2.4 | Metrics: RMSE, MAE, skill vs persistence and vs anomaly persistence, per-well NSE; block-bootstrap 95 % CIs; Diebold–Mariano tests between consecutive arms |
| 2.5 | Stratify by horizon × depth class × region (IGP / peninsular hard rock / arid NW / coastal / NE) × record length |
| 2.6 | Attribution: grouped SHAP (memory / forcing / teleconnection / static) per horizon |
| 2.7 | Robustness: spatially blocked CV (unseen regions), alternative split years, CHIRPS instead of IMD |

**Exit check:** a table of skill gains with CIs for every arm × horizon, and a written answer to
RQ1 that holds under the robustness checks.

## Phase 3 — Uncertainty calibration (RQ2) — ✅ done (see 09)

| Step | Action |
|---|---|
| 3.1 | Interval methods on the best arm: Gaussian, split conformal, Mondrian (depth × season; depth × region), CQR, adaptive conformal (ACI) for drift |
| 3.2 | Coverage at 50/80/90/95 %, overall and conditional (depth, region, season, record length); interval width; Winkler score; CRPS; PIT histograms |
| 3.3 | Diagnose the 2016–18 → 2019–25 drift (why Mondrian under-covers by ~2 points) and test ACI as the fix |
| 3.4 | Formal check of conditional coverage: binomial test per group, Holm correction |

**Exit check:** a method that keeps every depth and region class within ±3 points of nominal at 80 % and 90 %.

## Phase 4 — Decision value (RQ3)

| Step | Action |
|---|---|
| 4.1 | Event definitions: seasonal exceedance (80th percentile), a standardised groundwater index below −1, and a fixed depth threshold (e.g. pump-setting depth) |
| 4.2 | Probabilistic warnings from the calibrated predictive distribution; Brier score, reliability, ROC AUC |
| 4.3 | Relative economic value V(C/L) curves (Richardson 2000) for every arm, and optimal trigger probabilities per cost–loss ratio |
| 4.4 | Case study in Atal Bhujal districts: what the warnings would have flagged in a dry year (2023) vs what happened |
| 4.5 | Plain-language advisory generated only from calibrated outputs (template first; LLM only as an appendix with a faithfulness audit) |

**Exit check:** value curves with CIs for each arm; a stated trigger recommendation with its expected hit and false-alarm rates.

## Phase 5 — Dashboard integration

| Step | Action |
|---|---|
| 5.1 | Export forcing-aware forecasts, the skill-decomposition chart, conditional coverage by region and value curves |
| 5.2 | Add a "what rainfall adds" view per well (memory-only vs forcing forecast) |
| 5.3 | Decision panel: choose a cost–loss ratio, see the trigger and which wells it flags |
| 5.4 | Refresh manual-well levels from India-WRIS so forecasts are current; schedule the refresh |
| 5.5 | Build a static deployment (no backend needed); retire the legacy FastAPI endpoints |

**Exit check:** visual QA in light/dark/mobile with no console errors; every number on screen traceable to a file in `reports/`.

## Phase 6 — Manuscript and release

| Step | Action |
|---|---|
| 6.1 | Figures (publication style) and tables generated by script from `reports/` |
| 6.2 | Manuscript: introduction (positioned against Malakar 2021, Alphoenixx 2026, Kim 2026), data, methods, results for RQ1–3, discussion, limitations |
| 6.3 | Reproducibility package: code tag, environment, processed data where licences allow, Zenodo DOI |
| 6.4 | Preprint (EarthArXiv/ESSOAr) and submission to HESS (fallback: J. Hydrology: Regional Studies) |
| 6.5 | Internal review against the checklist: leakage, baselines, uncertainty, claims vs evidence |

**Exit check:** submission confirmation and a public, citable code release.
