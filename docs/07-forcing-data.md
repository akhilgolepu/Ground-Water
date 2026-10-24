# 07 — Forcing Data (Phase 1)

Reproduce (in `conda activate anpr`):

```bash
python -m src.research.forcing_download   # IMD grids + NOAA indices → data/external/ (git-ignored, ~1 GB)
python -m src.research.forcing_features   # → data/processed/forcing_features.parquet + reports/forcing/
```

## Sources

| Variable | Source | Resolution | Years | Access |
|---|---|---|---|---|
| Daily rainfall | IMD gridded rainfall (Pai et al. 2014), via `imdlib` 0.4.0 | 0.25° | 1990–2025 | imdpune.gov.in; free for research, cite IMD |
| Daily Tmax / Tmin | IMD gridded temperature (Srivastava et al. 2009) | 1° | 1990–2025 | same |
| Niño 3.4 anomaly | NOAA PSL, HadISST "long" series (anomaly vs 1981–2010) | monthly | 1870–2026 | psl.noaa.gov/data/timeseries/month |
| Dipole Mode Index (IOD) | NOAA PSL, HadISST "long" series | monthly | 1870–2026 | same |

1990–1993 are downloaded only so that 12-month windows and SPI exist for the first well readings (1994).

## Processing

1. Daily → monthly per grid cell (rain: sum, requiring ≥ 20 valid days; temperature: mean of (Tmax + Tmin)/2).
2. **Zero-rain artefacts.** 839 cell-years read 0 mm for the whole year. Isolated ones, where the
   neighbours' median annual rain is > 100 mm, are replaced by the neighbour mean (362 cell-years).
   Blocks of zero cells, mainly NW Rajasthan 1998–2002 and Kutch 2012, are set to missing (477
   cell-years). Only 50 of 246 887 observed well-campaigns lose their rainfall features.
3. Each well → nearest grid cell **with data** (coastal wells often fall in sea cells). 6 436 of 6 438
   wells are mapped. Two manual wells at 22.08° N, 91.05° E (3 readings each) are not.
4. Features per (well, campaign origin). Every past window ends the month **before** the campaign month.

| Column | Meaning |
|---|---|
| `rain_since_prev` | Rain from the previous campaign month to the month before this one (mm) |
| `rain_3m`, `rain_6m`, `rain_12m` | Rain over the last 3/6/12 months (mm) |
| `jjas_last_mm`, `jjas_last_ratio` | Last completed June–September monsoon total, and its ratio to the 1990–2015 normal |
| `spi_3`, `spi_6`, `spi_12` | SPI from a mixed gamma fit (Thom approximation) per cell and calendar month, fitted on ≤ 2015 |
| `tmean_anom_3m` | Mean-temperature anomaly over the last 3 months vs the ≤ 2015 monthly normal (°C) |
| `nino34_lag{0,3,6}`, `dmi_lag{0,3,6}` | Index value 1, 4 and 7 months before the campaign month |
| `oracle_rain_h{1,2,4}`, `oracle_rain_ratio_h{…}` | **Hindsight**: rain from the campaign month up to the target campaign. Upper-bound arm only |
| `snap_cum{2,4,8}` | **Control**: the source file's observation-day rainfall, averaged per campaign and summed over 2/4/8 campaigns (prior work's construction) |

Normals (SPI fits, monthly climatology) use ≤ 2015 data only, like a scaler fitted on the
training period. Calibration (2016–18) and test (2019–25) rows never see their own period.

## Sanity checks (`reports/forcing/sanity.json`, `sanity_checks.png`)

| Check | Result | Pass? |
|---|---|---|
| All-India JJAS departures vs IMD-reported departures (10 notable years) | Same sign 10/10. Magnitudes within 0–7 points (our baseline is the 1994–2023 mean of the grid, not IMD's LPA) | ✓ |
| Monsoon recharge (May → Nov water-table rise) vs JJAS rain at the well | Positive per-well correlation at 78 % of 2 396 wells; median r = 0.24; pooled Spearman 0.26. Median rise climbs from 0.4 m at 30 % of normal rain to ≈ 2.6 m at 150 % | ✓ |
| No future information in non-oracle features | Unit tests in `tests/research/test_forcing.py` perturb everything from the campaign month onward | ✓ |
| Coverage of observed manual-well campaigns | 99.98 % have `rain_12m` | ✓ (≥ 95 %) |
| Snapshot control vs real rainfall | Median `snap_cum4` = **3.6 mm** vs median IMD 12-month rain = **1 004 mm**; Spearman 0.22 | Confirms the defect behind prior null results |

## Known limitations

- IMD gridded products interpolate gauge data. Station density varies by year and region, which
  explains the zero-rain blocks and is a source of error in sparse areas.
- Temperature is only 1°, so it is coarse for local evapotranspiration.
- DWLR telemetry wells are not on the campaign grid yet (gap G4). Their forcing will come from the same monthly cells.

## Exit check (re-audited before Phase 5)

- **Per-well coverage:** 5 510 of 5 516 manual wells (99.9 %) have `rain_12m` on ≥ 95 % of their
  campaigns. The six exceptions: two wells whose coordinates fall in Bangladesh (no IMD cell within
  3 rings) and four wells in the NW Rajasthan / Kutch zero-rain block set to missing (§ zero-rain repair).
  SPI-3 is defined for ≥ 95 % of campaigns at 97 % of wells; it is undefined for calendar months that
  are dry in almost every year, where a gamma fit is meaningless.
- **Step 1.4 deliverable** (added in the audit): `data/processed/forcing_monthly.parquet` holds one row
  per IMD cell used by a well and month (987 120 rows, 2 285 cells, 1990–2025), and
  `data/processed/well_rain_cells.parquet` maps each well to its cell. Both are git-ignored and rebuilt
  by `python -m src.research.forcing_features`.
