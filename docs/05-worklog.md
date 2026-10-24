# 05 — Worklog

> **Frozen.** Superseded by [00-process-journal.md](00-process-journal.md), the single running record
> from Stage 5 (Phase 3) onward. This short log is kept unchanged as the original record of Stages 2–4.

## 2026-10-24 (evening) — Phase 2 complete: skill decomposition (RQ1)

Details and tables: [08-skill-decomposition.md](08-skill-decomposition.md).
- Nested XGBoost arms M0 → M3 + snapshot control on identical rows, each tuned on 2013–2015.
- **Answer to RQ1:** memory carries most skill; observed forcing + ENSO/IOD adds a small, robust
  gain (positive in all 9 horizon × validation settings; best at 6 months, +5.0 % MSE, 22/24 campaigns);
  a perfect rainfall forecast would add 2.5–9.6 % more; the source file's snapshot rainfall adds nothing.
- Found that 0.1 % of test readings (datum jumps, e.g. 69.8 → 6.9 m in a quarter) carry 15 % of
  squared error. Kept in all headline numbers; added absolute-loss DM, a campaign sign test and a
  no-jump sensitivity run. Decision: sign test + MAE CIs are the primary evidence.
- Reference models: Random Forest ≈ XGBoost; Chronos-2 zero-shot trails (skill 0.40 vs 0.51 at
  3 months) but gains 6–7 % MAE from rain covariates. N-HiTS and CHIRPS deferred (reasons in 08).
- Robustness: alternative split (train ≤ 2017) and 2° spatial blocks (unseen regions).
- Fixed `scripts/reproduce.sh`: ingest now runs before forcing features (fresh clones failed);
  added `--phase2`. Installed `chronos-forecasting` 2.3.2 into `anpr`.

**Next:** Phase 3 (depth- and region-aware calibration, adaptive conformal) on the M2 predictions.

## 2026-10-24 (later) — Phase 0 and Phase 1 complete

**Phase 0 — foundations** (exit check passed)
- `src/research/config.py` holds all split years, horizons, paths and seeds; ingest and benchmark read it.
- `requirements-research.txt` is pinned from `anpr` (Python 3.12.13).
- 25 unit tests in `tests/research/` (`python -m pytest`). They caught two real defects, both fixed:
  1. The conformal quantile used `np.quantile(..., method="higher")`, which is one rank too
     conservative. It now uses the exact ⌈(n+1)(1−α)⌉-th smallest score.
  2. Depth-class bins were right-closed (5.0 m fell into "< 5 m"). They are now left-closed, and the
     deepest class is labelled "≥ 40 m".
  Point metrics are unchanged (RMSE 2.406 m at h = 1). Coverage moved ≤ 2 points; Mondrian ≥ 40 m is now 75.0 %. Docs 03/04 are updated.
- `.gitignore` added; 21 committed `__pycache__/*.pyc` files untracked (still on disk).
- `docs/data-card.md` and `scripts/reproduce.sh` (re-runs everything and asserts the pilot RMSE).

**Phase 1 — forcing data** (exit check passed; details in [07](07-forcing-data.md))
- `imdlib` 0.4.0 installed in `anpr`. Downloaded IMD rain (0.25°) and Tmax/Tmin (1°) for 1990–2025
  (36/36 years each), plus Niño 3.4 and DMI from NOAA PSL (HadISST). The first PSL URL had moved
  (404); switched to `/data/timeseries/month/data/`.
- Found and handled 839 zero-rain cell-years in the IMD grid (362 repaired from neighbours,
  477 set to missing).
- `forcing_features.parquet`: 334 068 well-campaign rows × 27 columns (past rain, monsoon, SPI,
  temperature, ENSO/IOD lags, oracle arm, snapshot control).
- Sanity: JJAS departures agree in sign with IMD for 10/10 years; recharge correlates with
  monsoon rain at 78 % of wells; snapshot rainfall median 3.6 mm vs real 1 004 mm.

**Next:** Phase 2 (skill decomposition M0 → M3 + control C).

## 2026-10-24 — Audit, literature survey, pivot, pilot benchmark, dashboard rebuild

**Done**
- Audited the legacy pipeline ([01](01-project-audit.md)). Found that the target was `wellDepth`
  (constant), so all published metrics are invalid.
- Literature survey including the 10 supplied papers ([02](02-literature-review.md)).
- Found the **Alphoenixx 2026** benchmark on the same dataset. That forced a pivot away from a
  generic "benchmark" paper ([03](03-research-gaps.md)).
- Found that the dataset's weather columns are single-day snapshots (median 3.4 mm/yr for
  manual wells). This is the basis of gap G1.
- Built `src/research/ingest.py` and `src/research/benchmark.py`. Pilot results are in [04](04-methodology-and-pilot-results.md).
- Rebuilt the frontend as a research dashboard over the real artefacts (`frontend/public/data/`).
- Git: there is no Claude co-author on the single commit (`9f586d4`), so nothing needed removing.
  Future commits will not carry attribution trailers.

- Fixed the frontend build: `vite.config.ts` never loaded `@tailwindcss/vite`, so production
  builds failed even before this work. Fixed a type error in `__root.tsx`.
- Removed the demo components that showed fabricated numbers (policy simulator, linear-trend
  "forecast" chart, VSN-as-attention panel, stock hero images).
- Visual QA in headless Chromium (Playwright's own build in `~/.cache/ms-playwright`; the
  Playwright MCP needs system Chrome, which is not installed). Light, dark and 390 px mobile
  views were checked with no horizontal overflow and no console errors.
- Found that most manual-well records in the source file end in 2022–2023. The dashboard now
  says "forecast after the last reading" instead of "next"/"current".
- Environment: all Python runs in `conda activate anpr`.

**Decisions**
- Primary paper = G1 (monsoon forcing) + G2 (depth-aware calibration) + G3 (decision value).
- GA/PSO "pumping optimisation" removed from the narrative until an abstraction proxy exists.
- Legacy modules and API endpoints kept for history but marked deprecated.

**Open / next**
- Acquire IMD gridded rainfall and temperature (`pip install imdlib`) and the NOAA Niño 3.4/DMI indices.
- Implement forcing features and the oracle-forcing arm; add ACI; add the cost–loss analysis.
- Decide on a Google Earth Engine account for AlphaEarth (P2).
