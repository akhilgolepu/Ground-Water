# 12 — Internal Review (Phase 6.5)

A pre-submission review of the manuscript (`paper/main.tex`) against the checklist in the phase plan:
leakage, baselines, uncertainty, claims vs evidence. Each item records what was checked, how, and
the outcome. Items that changed the manuscript are marked **fixed**.

## 1. Leakage

| Check | How | Outcome |
|---|---|---|
| Features see nothing after the origin | Unit tests on synthetic data: expanding climatology, target shift, lags, forcing windows, SPI/ratio normals, oracle isolation (`tests/research/test_benchmark.py`, `test_forcing.py`) | Pass |
| The same, end to end on the real data | New test `test_no_lookahead_end_to_end.py`: delete every reading after a cutoff campaign (May 2017, Nov 2020, May 2022), rebuild with production code, compare every M2 input at the cutoff origins | **Identical** at all three cutoffs, horizons 3 and 12 months |
| Split boundaries | By target year, same for every well; unit-tested | Pass |
| Hyper-parameters chosen on test data | Inner validation 2013–2015 only (`skill_decomposition.tune_and_fit`) | Pass |
| Online intervals and warnings use future outcomes | Unit tests: a residual or outcome at target *T* cannot affect anything issued before *T* + *h* (`test_calibration.py`, `test_decision_value.py`) | Pass |
| Event thresholds | Fitted on readings ≤ 2018 (train + calibration), never on test | Pass |
| Same wells in train and test | By design for a temporal split; the spatial-block CV (unseen regions) bounds the effect | Disclosed; gains survive (Table 3) |

## 2. Baselines

Persistence, seasonal naive, per-well climatology and anomaly persistence on identical rows; Random
Forest; zero-shot Chronos-2 with and without rain covariates; the snapshot-rainfall construction of
prior work. **Pass.** N-HiTS and CHIRPS were planned but not run; the reasons are in docs/08 and the
limitations name the regional and data gaps.

## 3. Uncertainty

| Check | Outcome |
|---|---|
| Point-skill CIs | Well-clustered bootstrap, 1 000 draws |
| Tests robust to the datum jumps | Absolute-loss DM, campaign sign test, no-jump sensitivity; jumps kept in all headline numbers |
| Multiple comparisons | 15 nested-arm comparisons. The headline (M2 vs M0 at 6 months, sign test p = 4 × 10⁻⁵) survives Bonferroni (0.05 / 15 = 0.0033). Other individual comparisons are reported as estimates with CIs, not as significance claims |
| Interval coverage | Conditional by depth, region, season and record length; binomial + Holm; practical ±3-point criterion stated in advance |
| Post-hoc choices | Season-aware ACI variants, normalised ACI, static and rolling isotonic recalibration: all labelled post hoc in docs 09/10 and in the manuscript (**fixed**: the manuscript's Methods did not say the recalibrations were post hoc) |
| Parameters fixed before testing | ACI γ = 0.05, rolling window = 8 campaigns, depth classes, the ±3-point tolerance |

## 4. Claims vs evidence

- Every number in the abstract, results and conclusions is either a macro from `paper/numbers.tex` or
  a cell of a generated table, except the following, each verified by hand against the report named:

| Number in text | Source |
|---|---|
| M2 vs M0: 1.1 / 1.3 % MSE, 2.0 / 1.5 % MAE; 3.1 % alt. split, 3.7 % unseen regions | `reports/skill/diebold_mariano.csv`, `robustness.csv` (Table 3) |
| 12 % May → Nov gain at 6 months | `reports/skill/strata.csv` (Fig. 4) |
| C vs M0: −2.1 to +0.2 % | `diebold_mariano.csv` |
| Chronos-2 0.40 vs XGBoost 0.51; 6–7 % MAE gain at 3–6 months | `reports/skill/reference_metrics.csv` |
| 0.68 m median residual in 2022 | `data/processed/skill_predictions.parquet` (Fig. 6) |
| Himalaya & NE 83.0 %, n = 854, Holm p = 0.23; CQR/normalised misses up to 9.4 points | `reports/calibration/coverage.csv` |
| Raw p 0.55 → 33–41 %; value gain +0.01 to +0.04; oracle up to 0.13 | `reports/decision/reliability.csv`, `value_differences.csv` |
| 2023–24: 17 → 25 %, mean p 0.16 → 0.17 | `reports/decision/case_study_2023.csv` |
| 362 / 477 zero-rain cell-years; 10 / 10 JJAS signs | `reports/forcing/sanity.json` |

- **Fixed:** the trigger defaults 0.3 and 0.2 were read from the test period, so the conclusion now calls
  them illustrative; the rule "warn when p ≥ C/L" itself needs no tuning.
- **Fixed earlier in this phase:** a wrong citation (HESS 28:4407 is Gomez et al., not Heudorfer et al.),
  and an unverified author list (Malakar et al.). 37 of the 38 references were checked against OpenAlex by DOI; McKee et al. (1993) is a conference paper without a DOI.
- The abstract's "median 3.6 mm per year" is the four-campaign (≈ one-year) sum of the snapshot rainfall.

## 5. Reproducibility

`bash scripts/reproduce.sh --forcing --phase2 --phase3 --phase4` rebuilds every result from the raw file
and the public forcing downloads, asserting reference values at each phase; `python -m
src.research.paper_figures` regenerates every figure, table and number in the paper; 56 tests pass.

## 6. Open items before submission (for the author)

1. Author name, affiliation, ORCID, contributions (placeholders in `paper/main.tex`).
2. Licence for the code and outputs, and confirmation that the Kaggle compilation of CGWB data may be
   redistributed (data card §Licence).
3. ~~Port to the Copernicus LaTeX class~~ — done: `paper/make_hess.py` builds `paper/hess/main_hess.pdf` from `main.tex`.
4. Push the release to GitHub and archive it on Zenodo to obtain the DOI (outward-facing; not done).
5. Preprint (ESSOAr or EarthArXiv) and submission (author's accounts).
