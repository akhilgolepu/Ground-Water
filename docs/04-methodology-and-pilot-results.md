# 04 — Methodology and Pilot Results

Reproduce:

```bash
conda activate anpr
python -m src.research.ingest      # corrected ingestion (≈ 4 s)
python -m src.research.benchmark   # benchmark + dashboard export (≈ 1 min, 16 cores)
```

Outputs: `data/processed/{gwl_observations_clean,gwl_campaigns,station_catalog}.parquet`,
`reports/benchmark/{benchmark_metrics.json,coverage.csv,shap_importance.json}`,
`frontend/public/data/*.json`.

## 1. Data preparation (`src/research/ingest.py`)

1. Read the real water-level column (`target`) and real dates (`datetime`).
2. Label networks: **DWLR** if the median gap between readings ≤ 7 days (922 wells), otherwise **manual** (5 518).
3. Convert to depth below ground (m bgl, positive down), using each station's majority sign
   (DWLR stations are stored negative).
4. Quality control: keep −5 ≤ depth ≤ 250 m (516 rows dropped), then drop per-station robust
   outliers with |x − median| / (1.4826·MAD) > 8 (2 330 rows dropped). 414 106 rows remain.
5. Campaign grid for manual wells: Dec–Feb → Jan, Mar–Jun → May (pre-monsoon), Jul–Sep → Aug,
   Oct–Nov → Nov (post-monsoon). Index = year·4 + season. Duplicates are averaged.
   Result: **246 887 well-campaign values, 5 516 wells**.

## 2. Forecasting task (`src/research/benchmark.py`)

- Target: depth at campaign *t + h*, h ∈ {1, 2, 4} (≈ 3, 6, 12 months).
- **Time-blocked split by target year:** train ≤ 2015 · calibration 2016–2018 · test 2019–2025.
  No per-well percentage splits; the same calendar boundary applies to every well.
- Features at the origin only: current depth, 4 lags, changes over 1 and 4 campaigns, origin
  and target season, **expanding** per-well seasonal climatology (no look-ahead), current
  anomaly, record length, latitude/longitude, borehole depth.
- Common evaluation set: rows where every baseline is defined.

### Models

| Model | Definition |
|---|---|
| Persistence | ŷ = y_t |
| Seasonal naive | ŷ = value in the target season one year before the target (equals persistence at h = 4) |
| Climatology | ŷ = expanding per-well mean for the target season |
| Anomaly persistence | ŷ = (y_t − clim_origin) + clim_target |
| XGBoost (memory-only) | global model, 600 trees, depth 6, trained on Δy = y_{t+h} − y_t |
| Quantile XGBoost | q10 / q50 / q90 (`reg:quantileerror`) |

### Uncertainty methods (80 % unless stated)
- Gaussian: ± z·σ of train residuals.
- **Split conformal:** absolute calibration residuals, finite-sample quantile ⌈(n+1)(1−α)⌉/n.
- **Mondrian conformal:** the same, per (target season × depth class) cell with ≥ 50 calibration rows.
- Raw quantile XGBoost, and **CQR** (conformalised quantile regression).

### Early warning
- Event: depth deeper than the well's 80th percentile for that season (thresholds from data ≤ 2018).
- Probability from the conformal predictive distribution: P = share of signed calibration
  residuals r with ŷ + r > threshold.
- Scored with the Brier score vs the climatological rate (0.2), plus a reliability diagram.

## 3. Pilot results (memory-only; no meteorology yet)

### Point skill (test 2019–2025)

| Horizon | n (wells) | Persistence RMSE | Seasonal naive | Climatology | Anomaly persistence | **XGBoost** |
|---|---|---|---|---|---|---|
| 3 mo | 25 340 (3 249) | 3.48 m | 3.13 (+0.19) | 3.31 (+0.10) | 2.69 (+0.40) | **2.41 m (+0.52)** |
| 6 mo | 24 073 (3 175) | 4.17 m | 3.22 (+0.40) | 3.41 (+0.33) | 3.11 (+0.44) | **2.83 m (+0.54)** |
| 12 mo | 32 472 (3 370) | 3.17 m | = persistence | 3.31 (−0.09) | = persistence | **2.94 m (+0.14)** |

(Parentheses: MSE skill vs persistence.) Per-well skill for XGBoost: median **0.60** at
3 months with 87 % of wells positive; median **0.20** at 12 months with 68 % positive.

### Interval coverage (80 % nominal)

| Method | 3 mo | 6 mo | 12 mo | Median width (3 mo) |
|---|---|---|---|---|
| Gaussian | 0.820 | 0.796 | 0.797 | 4.52 m |
| Quantile XGBoost (raw) | 0.763 | 0.756 | 0.758 | 3.15 m |
| Split conformal | 0.800 | 0.781 | 0.790 | 4.18 m |
| CQR | 0.797 | 0.789 | 0.803 | 3.39 m |
| **Mondrian conformal** | 0.780 | 0.772 | 0.767 | **3.32 m** |

**Conditional coverage by depth class (3 months; classes are left-closed, e.g. [5, 15) m):**

| Depth class | Split conformal | Mondrian conformal | Mondrian median width |
|---|---|---|---|
| < 5 m | 0.880 | 0.784 | 3.09 m |
| 5–15 m | 0.736 | 0.775 | 4.33 m |
| 15–40 m | 0.574 | 0.782 | 9.27 m |
| ≥ 40 m | **0.442** | 0.750 | 13.54 m |

A single width (4.18 m) is too wide for shallow wells and far too narrow for deep ones. Mondrian
gives each class its own width. Its marginal shortfall (≈ 2 points, 5 points for ≥ 40 m) is consistent
with temporal shift between calibration (2016–18) and test (2019–25). Adaptive conformal (Phase 3) is planned to address it.

*Correction (Phase 0, 2026-10-24):* unit tests found the conformal quantile was one rank too
conservative and depth-class edges were right-closed. Both were fixed; point metrics are unchanged
and interval coverages moved by ≤ 2 points (numbers above are post-fix).

### Early warning
Brier skill vs climatology: **+0.166 (3 mo)**, +0.049 (6 mo), +0.029 (12 mo). The reliability
diagram shows over-forecasting at mid probabilities (forecast 0.25 → observed 0.15).

### Explainability (TreeSHAP, 3 months)
Top contributions (mean |SHAP|, m): current depth 1.24, target-season climatology 0.94,
target season 0.43, depth 3 campaigns ago 0.32, change since last campaign 0.30. The
memory-only model learns the seasonal cycle; forcing variables are the missing piece (RQ1).

### Long-term trends (pre-monsoon, Sen's slope + Mann–Kendall, ≥ 8 years)
2 868 wells evaluated: **523 significantly deepening**, 306 significantly rising (p < 0.05).

## 4. Next experiments (in order)

1. **Forcing data:** IMD gridded rainfall/temperature → per-well accumulations between campaigns,
   monsoon (JJAS) totals, SPI-3/6/12; Niño 3.4 and DMI at lags of 0–9 months.
2. **Skill decomposition (RQ1):** memory → + past forcing → + oracle future forcing → + teleconnections.
   Report skill vs anomaly persistence, by horizon × depth class × region.
3. **Reproduce the snapshot-rainfall pipeline** (sum of daily snapshots) as a control arm.
4. **Uncertainty (RQ2):** adaptive conformal (ACI) and depth × region Mondrian; report PIT and CRPS.
5. **Decision value (RQ3):** relative economic value curves V(C/L) and optimal triggers.
6. Reference models: LightGBM/RF, N-HiTS, Chronos-2 zero-shot (for comparability with prior work).
7. Statistical tests: Diebold–Mariano per horizon; block bootstrap CIs on skill.
