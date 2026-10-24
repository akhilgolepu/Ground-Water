# 11 — Phase 5: Dashboard Integration

The dashboard shows the paper's results and the operational forecasts that follow from them. It is a
static site: the browser reads JSON files from `frontend/public/data/`, and nothing runs on a server.

Reproduce:

```bash
conda activate anpr
python -m src.research.export_dashboard   # writes frontend/public/data/ (~35 s)
cd frontend && npm run build              # static site in frontend/dist/
```

## 1. What is exported (step 5.1)

`src/research/export_dashboard.py` writes six kinds of file, each naming the report it came from:

| File | Content | Source |
|---|---|---|
| `summary.json` | Network counts, trends, operational coverage, India-WRIS status, sources | processed data, `reports/wris_refresh.json` |
| `stations.json` | One record per well: location, state, region, pre-monsoon trend, warning probabilities per horizon | processed data, operational forecasts |
| `wells/<0–63>.json` | Per-well detail in 64 buckets: observed series, 2019–25 test forecasts with and without rainfall, 80 % intervals, per-well errors, operational forecasts and advisories | `skill_predictions.parquet`, `intervals_80.parquet` |
| `skill.json` | Skill by arm with CIs, gains, strata, reference models, robustness | `reports/skill/` |
| `calibration.json` | Conditional coverage by method, drift series, monsoon anomalies | `reports/calibration/`, `reports/forcing/` |
| `decision.json` | Value curves, a trigger table on the value-curve grid, scores, case study | `reports/decision/`, `event_probabilities.parquet` |

**Operational forecasts** start from each manual well's latest campaign (origins from 2019 on, 4 425 wells).
They use the evaluated models unchanged: M0 and M2 are refitted with the tuned Phase 2 settings, and the
export stops if they differ from the Phase 2 test predictions by more than 1 mm. The 80 % intervals use
the depth × region residual pools (Phase 3), and the warning probabilities use the rolling isotonic map of
the most recent eight campaigns (Phase 4).

## 2. What the dashboard shows (steps 5.2–5.3)

- **Network map:** all 6 438 wells, coloured by current warning (at the user's trigger), long-term trend or monitoring type.
- **Decide when to warn:** choose the event (deeper than usual / below 8 m), the horizon and the cost of
  acting as a share of the loss avoided. The panel shows the hit rate, the share of warnings that did not
  verify, the relative value with its 95 % interval and the number of wells flagged at their latest
  forecast, next to the value curves of the memory-only, forcing and oracle models.
- **One well:** search any well; see its readings, 3-month test forecasts with and without rainfall, the
  80 % band, the forecast after the latest reading for each horizon, the warning probabilities, the
  template advisory and that well's own errors with and without rainfall.
- **Findings:** RQ1–RQ3 charts from the reports; **Paper:** the research agenda and the open follow-ups.

## 3. Checks (exit check)

- **Traceability:** `tests/research/test_dashboard_trace.py` compares the dashboard files with the reports:
  skill and CIs with `bootstrap.json`, gains with `diebold_mariano.csv`, coverage with `coverage.csv`,
  value curves and triggers with `value_curves.csv` and `triggers.csv`, counts with the processed data. Pass.
- **Visual QA** in headless Chromium, light and dark at 1360 px and 390 px, on both the dev server and the
  production build served statically (`vite preview`): no console errors, no horizontal overflow.
- **Static:** the API proxy was removed from `vite.config.ts`; the legacy FastAPI backend was moved to
  `legacy/` (step 5.5). The production build is 14 MB including the data.

## 4. India-WRIS refresh (step 5.4)

India-WRIS has no documented API. `src/research/wris_refresh.py` uses the endpoints its own web page calls
(the same ones used by the open-source QGIS plugin “CGWB Groundwater Data Downloader”). What was learned:

- HTTP 406 means "no rows". There is no server-side filter by acquisition mode, so six-hourly telemetry
  rows dominate and the pages must be walked to reach the manual readings.
- The CSV header is shifted relative to the rows, so fields are read by position.
- Districts appear under two spellings (e.g. "Ambala" and "AMBALA") and both are fetched.
- Only some manual station codes match the research snapshot's well IDs (13 of 37 in an Ajmer probe, 0 of 58 in Karnal); unmatched stations are kept in the file but not used for forecasts.

PILOT_RESULTS

The refresh only feeds the dashboard's operational forecasts. The research results (Phases 0–4, the
paper) use the frozen snapshot and are unaffected. **Scheduling:** run the refresh and the export
periodically, e.g. a monthly cron job:

```bash
0 3 1 * * cd /path/to/GroundWater && conda run -n anpr python -m src.research.wris_refresh \
  && conda run -n anpr python -m src.research.export_dashboard && cd frontend && npm run build
```

Requests are paced (1.5 s) and responses cached under `data/external/wris/`; a full refresh of the seven
Atal Bhujal states takes several hours.
