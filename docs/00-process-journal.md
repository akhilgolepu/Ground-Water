# 00 — Process Journal

The complete, chronological record of this research project: every request, what was done,
what was found, what was decided and why, and where the results live. **This is the running
record.** A new entry is added at the end of every step, before the step's commit.

Each entry follows the same shape: **Request → Work → Findings → Decisions → Artefacts / commits.**

Conventions: all Python runs in `conda activate anpr`. Commits carry no AI co-author trailers.
Research work lives on branch `research/p1`.

---

## Stage 1 — Project review and first literature survey (2026-10-24, morning)

**Request.** "Review the project, do a literature survey and check if we are filling the right
gap; if you find other gaps, tell me."

**Work.**
- Read the legacy pipeline (`src/data`, `src/models`, `src/explainability`, `src/optimization`),
  the FastAPI backend and the README.
- Profiled the raw CGWB file (416 952 rows, 6 440 stations, 1994–2025) and the processed
  `feature_matrix`.
- Searched the literature (web search; OpenAlex).

**Findings.**
- **The legacy model never forecast groundwater.** The preprocessing keyword-matched `wellDepth`
  (the static borehole depth) as the target and fabricated monthly timestamps. Copying the
  previous value scored RMSE 0.0000 on the legacy test split, so the reported R² 0.9998, the
  SHAP/VSN rankings and the GA/PSO "policy" outputs were all invalid.
- Other defects: rainfall/temperature dropped; static soil/aquifer features were placeholder
  constants; the "TFT" ran on sequences of length 1; `train.py` could not run; dashboard numbers
  were hard-coded. Full list: [01-project-audit.md](01-project-audit.md).
- Literature: India-wide deep learning already existed (Malakar et al. 2021); TFT was not
  state of the art for groundwater (below N-HiTS in German studies); GA/PSO surrogate optimisation
  was mature. The claimed contribution was an integration, not a methods gap.

**Decisions.** Fix the target before judging any gap. Proposed alternative gaps: an honest Indian
benchmark, mixed-frequency (telemetry + manual) modelling, calibrated uncertainty, energy as a
pumping proxy, groundwater-drought early warning, joint level–quality modelling.

**Artefacts.** Report delivered in chat (later turned into docs 01–03). No commits.

---

## Stage 2 — Novelty search, documentation, corrected pipeline, dashboard rebuild (2026-10-24)

**Request.** Remove Claude from GitHub co-authors; find the best publishable gaps (also outside the
current project); review ten supplied papers; document the whole project; install needed skills
and MCPs; change the frontend for the final outcome, including visual changes.

**Work.**
1. *Co-author check.* The only commit (`9f586d4`) had a single author and no co-author trailer, so
   nothing had to be removed. Saved a standing rule: no attribution trailers on commits or PRs.
2. *Ten supplied papers.* Pulled their abstracts from OpenAlex and tabulated what each leaves open
   ([02 §A](02-literature-review.md)): 9/10 used ≤ 48 wells, random or single splits, no naive
   baseline, no calibrated intervals, no decision value.
3. *Wider search.* OpenAlex title/abstract searches for foundation models, conformal prediction,
   ENSO/IOD + Indian groundwater, cost–loss value, AlphaEarth, KAN/Mamba, mixed frequency.
4. *Data facts.* Established the two sign conventions (manual positive, DWLR negative), the
   quarterly CGWB campaign months, and that the file's rainfall is a single-day snapshot
   (median 3.4 mm per well-year).
5. *Corrected pipeline.* `src/research/ingest.py` (real target and dates, sign harmonisation,
   outlier QC, campaign grid) and `src/research/benchmark.py` (time-blocked split, naive baselines,
   memory-only XGBoost, five interval methods, exceedance warnings, SHAP, trends, dashboard export).
6. *Dashboard.* Replaced the marketing demo with a research dashboard: hero hydrograph below a
   ground line, national well map (warning / trend / network layers), single-well explorer, evidence
   charts, research agenda. New visual system (Archivo, chalk/slate/soil palette, validated chart
   colours, light + dark). Fixed the broken production build. QA'd in headless Chromium at desktop,
   dark and 390 px.
7. *Tools.* No new MCP was needed (OpenAlex/GitHub APIs reached directly). The Playwright MCP needs
   system Chrome, so Playwright's own Chromium was installed under `~/.cache/ms-playwright`.

**Findings.**
- **A 2026 benchmark on the same Kaggle file already exists** (Alphoenixx, Zenodo, July 2026):
  RF/XGBoost/LSTM/GRU/Chronos-2, conformal, spatial CV. A generic benchmark paper was no longer novel.
  Its climate ablation summed the snapshot rainfall, so its "climate adds ~0 %" null was untested.
- **Pilot results** (memory-only XGBoost, test 2019–2025): skill vs persistence +0.52 / +0.54 / +0.14
  at 3 / 6 / 12 months. One global conformal interval covered 88 % of readings in wells < 5 m but
  only 44 % in wells ≥ 40 m; Mondrian (season × depth) conformal fixed most of that.
- Kim et al. 2026 (Korean wells): known future weather is the main short-horizon skill source.
- No groundwater-level conformal paper, no cost–loss study, no ENSO/IOD study for India was found.

**Decisions.**
- **Paper P1:** *Monsoon forcing, depth-aware calibration and decision value in national-scale
  groundwater forecasting for India* — gaps G1 (forcing), G2 (calibration), G3 (decision value).
  Follow-ups: telemetry + manual fusion, AlphaEarth for unseen wells, level + quality, energy as
  pumping proxy. Full ranking: [03-research-gaps.md](03-research-gaps.md).
- GA/PSO pumping optimisation dropped from the narrative until a real abstraction proxy exists.
- Dashboard says "forecast after the last reading", because most manual records end in 2022–2023.

**Artefacts.** docs 01–05, data card, `references.bib`; `src/research/{ingest,benchmark}.py`;
`frontend/` rebuild. Committed later in Stage 3 (`b802160`, `5730584`, `784c617`).

---

## Stage 3 — Phase plan, Phase 0 (foundations) and Phase 1 (forcing data) (2026-10-24)

**Request.** "Create a precise plan of phases with steps; start Phase 0 and 1 immediately."
Mid-way: "make sure to use conda activate anpr". Afterwards: "commit each phase or internal
changes if necessary".

**Work.**
- *Plan:* [06-phase-plan.md](06-phase-plan.md) — Phases 0–6 with steps, deliverables, exit checks.
- *Phase 0:* `src/research/config.py` (all split years, horizons, paths, seeds); pinned
  `requirements-research.txt` from `anpr`; unit tests (`tests/research/`); `.gitignore` and removal of
  21 committed `.pyc` files; [data-card.md](data-card.md); `scripts/reproduce.sh`.
- *Phase 1:* installed `imdlib`; downloaded IMD rainfall (0.25°) and Tmax/Tmin (1°) for 1990–2025
  (36/36 years each) and NOAA Niño 3.4 + DMI; built `forcing_features.parquet` (past rain windows,
  last monsoon, SPI-3/6/12, temperature anomaly, ENSO/IOD lags, oracle arm, snapshot control).

**Findings.**
- The new unit tests caught two of my own bugs: the conformal quantile was one rank too
  conservative, and depth classes were right-closed (a 5.0 m well fell in "< 5 m"). Fixed; point
  metrics unchanged, coverage moved ≤ 2 points (Mondrian ≥ 40 m: 77 % → 75 %).
- The NOAA index URL had moved (404); switched to the PSL `/data/timeseries/` path.
- IMD rain grid contains 839 zero-rain cell-years: 362 isolated ones repaired from neighbours,
  477 in blocks (NW Rajasthan 1998–2002, Kutch 2012) set to missing.
- Sanity checks passed: monsoon departures match IMD's reported sign in 10/10 years; monsoon rain
  correlates with May → Nov recharge at 78 % of wells; snapshot rainfall is 3.6 mm vs 1 004 mm real.
  Details: [07-forcing-data.md](07-forcing-data.md).

**Decisions.** Normals for SPI/ratios fitted on ≤ 2015 only (like a scaler fitted on training data);
leakage unit tests enforce that past features never see the future.

**Commits.** `1c4f7aa` gitignore · `b802160` pipeline + Phase 0 · `5730584` docs · `784c617`
dashboard · `9468507` Phase 1.

---

## Stage 4 — Phase 2: skill decomposition, RQ1 (2026-10-24)

**Request.** "Move on to phase 2" (later: "continue").

**Work.**
- `src/research/skill_decomposition.py`: nested XGBoost arms on identical rows — M0 memory,
  M1 + past forcing, M2 + ENSO/IOD, M3 + oracle future rain, C snapshot control — each tuned on
  2013–2015; well-clustered bootstrap CIs; Diebold–Mariano; stratification by depth, region,
  record length, season; grouped SHAP. `src/research/regions.py` for coarse regions.
- `src/research/reference_models.py`: Random Forest and Chronos-2 zero-shot (with past rain and
  oracle future rain as covariates) on the GPU. Installed `chronos-forecasting` 2.3.2.
- `src/research/skill_robustness.py`: alternative split (train ≤ 2017) and 2° spatially blocked CV.
- `src/research/skill_figures.py`: three figures in `reports/skill/`.

**Findings.**
- About 30 readings per horizon (0.1 %) are datum jumps carrying 15 % of squared error; they made
  the squared-error DM test meaningless. Added absolute-loss DM, a campaign sign test, MAE CIs and
  a no-jump sensitivity run; kept the jumps in every headline number.
- **RQ1 answer:** memory carries most skill; observed forcing + ENSO/IOD adds a small, robust gain
  (positive in all 9 horizon × setting combinations; best at 6 months, +5.0 % MSE, 22/24 campaigns);
  a perfect rainfall forecast would add 2.5–9.6 % more; snapshot rainfall adds nothing. Gains
  concentrate in the monsoon-spanning May → November forecast and in wells < 15 m.
- Chronos-2 zero-shot trails the trained models; Random Forest ≈ XGBoost.
- `scripts/reproduce.sh` ran ingest after forcing features, which fails on a fresh clone. Fixed.

**Decisions.** Primary evidence = campaign sign test + MAE CIs. N-HiTS and CHIRPS deferred
(reasons in [08 §4–5](08-skill-decomposition.md)).

**Commits.** `c38d6b6` · `50976cd` · `edd9db5`.

---

## Stage 5 — Phase 3: uncertainty calibration, RQ2 (2026-10-24)

**Request.** "Start phase 3; document the whole process, including what you've done since the
beginning."

**Work.**
1. *Documentation.* Wrote this journal back to the first review; froze `05-worklog.md`; indexed the
   journal as the start page (`146bb42`). Saved a standing rule to append an entry every step.
2. *Methods* (`src/research/calibration.py`): interval methods on the Phase 2 M2 forecast —
   Gaussian, split conformal, Mondrian depth × season, Mondrian depth × region, normalised (σ̂
   cross-fitted by well), CQR (quantile XGBoost), and online methods that recalibrate with residuals
   already observed (target ≤ T − h), one with adaptive conformal inference (ACI, γ = 0.05 fixed in
   advance). Small cells fall back to coarser pools.
3. *Evaluation:* coverage at 50/80/90/95 %, conditional by depth, region, season and record length,
   binomial tests with Holm correction, Winkler score, CRPS, PIT histograms, ACI γ sweep.
4. *Tests:* 8 new unit tests (39 in total), including a no-look-ahead test for the online methods.
5. Fixed a merge bug on the first run (`target_season` present on both sides).

**Findings.**
- One interval width covers 88 % of readings in wells < 5 m but 46–51 % in wells ≥ 40 m.
- **Drift explained:** the calibration years 2016–18 followed the 2014–15 droughts, while 2019–22 had
  strong monsoons (+14 %, +13 %, +9 %), so water came in shallower than forecast (up to 73 % of
  readings in 2022). Static calibration therefore under-covers by 2–5 points.
- Rolling recalibration + ACI keeps every depth and region class within 1.6 / 1.7 / 3.02 points of
  nominal at 3 / 6 / 12 months. Season misses remain (August targets 73.4 % at 12 months).
- After seeing that, added two variants (labelled post hoc): season in the cells, and σ̂-normalised
  scores. They fix the season misses and the normalised one is ~12 % sharper (Winkler), at the cost of
  slightly larger region misses.
- Gaussian intervals over-cover by ten points because the datum jumps inflate σ.

**Decisions.**
- Primary method = the pre-registered Mondrian D×R + recal + ACI with γ = 0.05. One cell (Himalaya &
  north-east, 12 months, 80 %) is at 83.02 %: 0.02 points beyond tolerance, on the conservative side,
  Holm p = 0.23. γ was **not** re-tuned on the test period to remove it.
- The ±3-point tolerance, not the binomial test, is the practical criterion: with up to 22 000
  correlated readings per class the test flags 1-point deviations.

**Artefacts.** [09-uncertainty-calibration.md](09-uncertainty-calibration.md); `reports/calibration/`
(coverage, CRPS, PIT, γ sweep, four figures); `scripts/reproduce.sh --phase3`.

**Commits.** `146bb42` journal · `64a9eb3` calibration experiment · `97f9c4c` Phase 3 docs and figures.

---

## Stage 6 — Phase 4: decision value, RQ3 (2026-10-24)

**Request.** "Proceed to phase-4".

**Work.**
1. *Events:* E1 deeper than usual (80th percentile per well and season), E2 groundwater drought
   (SGI < −1 on Weibull plotting positions), E3 crossing an 8 m pump suction limit. Thresholds from
   readings up to 2018.
2. *Probabilities* from the Phase 3 rolling depth × region pools, separately for M0–M3
   (`src/research/decision_value.py`).
3. *Scores:* Brier skill vs each well's own climatology, ROC AUC, reliability, Richardson relative
   economic value over cost–loss ratios 0.02–0.98, trigger tables, paired well-clustered bootstrap
   for M2 − M0 and M3 − M2.
4. *Case study:* looked for the official Atal Bhujal district list and found only state-wise counts
   (80 districts in 7 states). Did not guess district names; tagged wells to states with geoBoundaries
   ADM1 (`src/research/states.py`; 6 427 / 6 438 wells; names normalised from diacritics) and compared
   the wet 2022–23 and dry 2023–24 water years.
5. *Advisory:* template text built only from forecast fields, with a unit test that the numbers match.
6. *Tests:* 6 new (45 in total).

**Findings.**
- **Raw probabilities were over-confident** (predicted 0.55 verified 33–41 %), so acting on them lost
  value above C/L ≈ 0.45. Interval calibration (Phase 3) does not imply probability calibration.
- A **static isotonic recalibration** fitted on 2016–18 over-corrected on the test years (same drift as
  Phase 3) and reduced value. A **rolling isotonic recalibration** (8 most recent observed campaigns,
  window fixed before running) put reliability on the diagonal and raised Brier skill for every arm and
  horizon. Both recalibrations were added after seeing the raw reliability diagram and are labelled post hoc.
- **Value is substantial:** peak V 0.43 / 0.32 / 0.27 for E1 and 0.65 / 0.69 / 0.54 for E3 at 3 / 6 / 12 months.
- **Forcing adds value only at 6 months** (+0.01 to +0.04, CIs exclude 0); a perfect monsoon forecast
  would add up to +0.13 (CIs exclude 0 in 40 of 45 cells).
- **2023–24 dry year:** exceedances in Atal Bhujal states rose from 17 % to 25 % while the mean warning
  probability stayed ~0.17. The forecasts lagged the turn to a dry regime.
- Corrected four numbers in my own draft of docs/10 after checking them against the CSVs.

**Decisions.** Primary probabilities = rolling isotonic. Trigger rule = warn when p ≥ C/L; defaults 0.3
for seasonal planning (E1, 3 months: hit rate 58 %, false-alarm ratio 46 %, V 0.37) and 0.2 for pump
decisions six months ahead (E3: hit rate 76 %, false-alarm ratio 48 %, V 0.58). Twelve-month suction-limit
warnings are not recommended. The LLM advisory variant is deferred.

**Artefacts.** [10-decision-value.md](10-decision-value.md); `reports/decision/` (scores, value curves,
paired differences, triggers, case study, advisories, three figures); `scripts/reproduce.sh --phase4`.

**Commits.** `5630551` decision-value experiment · `13ed3b0` Phase 4 docs and figures.

---

## Stage 7 — Audit of Phases 0–4 and Phase 5: dashboard integration (2026-10-24)

**Request.** "Proceed; also go through all the phases thoroughly and finish phase 6 as well."

**Audit of Phases 0–4.** Re-read every step and exit check of the plan against the deliverables.
- All Phase 0.3 unit tests were present. Phase 1 lacked its step 1.4 deliverable (a cell-month forcing
  table): added `forcing_monthly.parquet` and the well → cell map. Per-well forcing coverage was never
  recorded: 5 510 of 5 516 manual wells are at ≥ 95 % (the six exceptions are documented in docs/07).
- The plan's status table and journal pointer were stale; updated (`cc7543b`).

**Work (Phase 5).**
1. *India-WRIS (5.4).* Found no documented API. Reverse-engineered the portal's endpoints from the open
   QGIS plugin; documented quirks (406 = no rows, no mode filter, shifted CSV header, duplicate district
   spellings). Wrote `src/research/wris_refresh.py` (paced, cached, writes a separate updates file that never
   touches the research snapshot). A Rajasthan pilot was run (results in docs/11).
2. *Export (5.1).* `src/research/export_dashboard.py` writes summary, stations, 64 per-well bucket files and
   skill / calibration / decision payloads, each naming its source report. Operational forecasts refit M0 and
   M2 with the tuned settings and abort if they differ from the Phase 2 test predictions by more than 1 mm.
   Refactored the forcing loader and `load_dataset` for this, verified byte-identical outputs, and removed
   the pilot export from `benchmark.py`.
3. *Dashboard (5.2–5.3).* Warnings panel (event, horizon, cost of acting → hit rate, false alarms, value with CI,
   wells flagged), well view with forecasts with and without rainfall and per-well errors, findings for RQ1–RQ3.
4. *Static (5.5).* Removed the API proxy; moved the legacy pipeline and FastAPI backend to `legacy/` with a
   README explaining why its results are invalid.

**Findings.**
- At 390 px the long source paths overflowed by 262 px; fixed with wrapping.
- A calibrated probability displayed as "100 %"; probabilities now display as "> 99 %" / "< 1 %" at the extremes.
- The hero chart's threshold label covered data points; moved into the legend.

**Checks.** `tests/research/test_dashboard_trace.py` (5 tests) compares the dashboard data with the reports.
Visual QA in light, dark and 390 px on the dev server and on the static production build: no console errors,
no overflow.

**Commits.** `5cee084` groundwork · `85a3a80` export · `7362d36` dashboard · `b085d38` legacy retired.

---

## Stage 8 — Phase 6: manuscript and release (2026-10-24)

**Work.**
1. *Figures and tables (6.1).* `src/research/paper_figures.py` generates eight publication figures, five LaTeX
   tables and `paper/numbers.tex` (macros for every number quoted in the text) from `reports/`.
2. *Manuscript (6.2).* `paper/main.tex` → `main.pdf` (12 pages): introduction positioned against Malakar et al.
   (2021), the 2026 benchmark and Kim et al. (2026); data; methods; results for RQ1–RQ3; discussion;
   limitations; conclusions. Portable article layout; to be ported to the Copernicus class at submission.
3. *References.* Found that a citation used since Stage 2 was wrong: HESS 28:4407 is Gomez et al. (1-D CNN,
   Lower Saxony), not Heudorfer et al. (that is HESS 28:525). Fixed in the bibliography and docs/02. Replaced
   an unverified Malakar et al. author list. Added 20 references; 37 of 38 DOIs checked against OpenAlex.
4. *Internal review (6.5).* New end-to-end look-ahead test on the real data (features at three cutoff
   origins identical with and without later readings). Review in [12-internal-review.md](12-internal-review.md).
   Two manuscript fixes: the probability recalibrations are now disclosed as post hoc, and the default
   triggers are called illustrative because they were read from the test period.
5. *Release package (6.3).* README rewritten around the results; `CITATION.cff`; local tag `v1.0.0-rc1`.
6. *Submission package (6.4).* Cover letter draft and checklist in `paper/submission/`.

**Not done, and why.** Pushing to GitHub, minting the Zenodo DOI, posting the preprint and submitting are
outward-facing actions that need the author's accounts and decisions (licence, authorship, data
redistribution terms). They are listed in `paper/submission/checklist.md`. The Phase 6 exit check
("submission confirmation and a public, citable release") therefore remains open until the author acts.

**Commits.** `c8bc5be` figures and draft · `bf5199c` internal review · `8eab5b2` README and citation.
