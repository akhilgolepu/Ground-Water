# AquaSense — Research Documentation

Living documentation for the groundwater-forecasting research project. Update
[00-process-journal.md](00-process-journal.md) at every step.

| Doc | What it holds |
|---|---|
| [00-process-journal.md](00-process-journal.md) | **Start here.** Chronological record of every request, step, finding, decision and commit since the first review |
| [01-project-audit.md](01-project-audit.md) | Verified defects in the legacy Phase 1–5 pipeline and the data facts behind them |
| [02-literature-review.md](02-literature-review.md) | The 10 supplied papers + positioning literature, with what each leaves open |
| [03-research-gaps.md](03-research-gaps.md) | Ranked gaps, recommended paper (P1), follow-ups, ideas beyond the project |
| [04-methodology-and-pilot-results.md](04-methodology-and-pilot-results.md) | Corrected pipeline, benchmark design, pilot numbers, next experiments |
| [05-worklog.md](05-worklog.md) | Original short log of Stages 2–4 (frozen; see 00) |
| [06-phase-plan.md](06-phase-plan.md) | Phases 0–6 with steps, deliverables and exit checks |
| [07-forcing-data.md](07-forcing-data.md) | IMD rainfall/temperature and ENSO/IOD forcing: sources, processing, sanity checks |
| [08-skill-decomposition.md](08-skill-decomposition.md) | Phase 2: does monsoon forcing add skill? Arms M0–M3, reference models, robustness, answer to RQ1 |
| [09-uncertainty-calibration.md](09-uncertainty-calibration.md) | Phase 3: interval methods, conditional coverage by depth/region/season, drift, answer to RQ2 |
| [10-decision-value.md](10-decision-value.md) | Phase 4: warning events, probability calibration, economic value, trigger rule, 2023–24 case study, answer to RQ3 |
| [data-card.md](data-card.md) | Provenance, fields, sign conventions and defects of the CGWB source file |
| [references.bib](references.bib) | BibTeX for everything cited |

## Status at a glance

- Legacy results (R² 0.9998 etc.) — **invalid**, do not cite.
- Research pipeline — `src/research/` — **pilot complete** (memory-only).
- Phase 0 (foundations) — **done**: config, pinned env, 25 unit tests, `scripts/reproduce.sh`.
- Phase 1 (forcing data) — **done**: IMD 1990–2025 + Niño 3.4/DMI → `forcing_features.parquet`; all sanity checks pass.
- Phase 2 (skill decomposition) — **done**: forcing adds a small robust gain (best +5 % MSE at 6 months); oracle headroom 2.5–9.6 %. See [08](08-skill-decomposition.md).
- Phase 3 (uncertainty calibration) — **done**: rolling recalibration + ACI keeps every depth and region class within ~3 points; drift traced to the 2019–22 strong monsoons. See [09](09-uncertainty-calibration.md).
- Phase 4 (decision value) — **done**: warnings worth acting on (peak V 0.43 at 3 months; 0.69 for the suction-limit event) once probabilities are recalibrated on a rolling window; trigger = p ≥ C/L. See [10](10-decision-value.md).
- Phase 5 (dashboard integration) — **next**.
- Dashboard — `frontend/` — reads `frontend/public/data/*.json` produced by the benchmark.

## Reproduce

```bash
conda activate anpr                 # project Python env (pip install -r requirements-research.txt)
bash scripts/reproduce.sh --forcing # tests → forcing download/features → ingest → benchmark → check
cd frontend && npm run dev          # http://localhost:5173
```

Data caveat: most manual-well records in the source file end in 2022–2023, so dashboard
forecasts start from each well's last reading. Refreshing from India-WRIS would make them current.
