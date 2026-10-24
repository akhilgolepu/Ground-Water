# AquaSense — groundwater-level forecasting for India

Research code, results and dashboard for the paper
**“Monsoon forcing, depth-aware calibration and decision value in national-scale groundwater
forecasting for India”** (draft: [paper/main.pdf](paper/main.pdf)).

Using 414 106 quality-controlled readings from 6 438 Central Ground Water Board wells (1994–2025),
gridded IMD rainfall and temperature, and ENSO / Indian Ocean Dipole indices, it asks three questions:

| Question | Answer (test period 2019–2025) | Details |
|---|---|---|
| **RQ1** Does monsoon forcing add skill to groundwater memory? | A small, robust gain, largest at 6 months: 5.0 % less squared error, better in 22 of 24 test campaigns, also in unseen regions. A perfect rainfall forecast would add 5.5–9.6 % more. The rainfall column of the public data file is a one-day snapshot and adds nothing. | [docs/08](docs/08-skill-decomposition.md) |
| **RQ2** Can intervals be trusted for shallow and deep wells alike? | One interval width covers 88 % of shallow-well readings but 46 % in wells ≥ 40 m. Pools by depth × region, updated online with adaptive conformal inference, keep every depth and region class within 1.6 / 1.7 / 3.0 points of nominal at 3 / 6 / 12 months. | [docs/09](docs/09-uncertainty-calibration.md) |
| **RQ3** Are the warnings worth acting on? | Yes, once probabilities are recalibrated on a rolling window: peak relative economic value 0.43 (deeper than usual, 3 months) and 0.69 (water below an 8 m pump-suction limit, 6 months). Rule: warn when p ≥ cost/loss. | [docs/10](docs/10-decision-value.md) |

## Repository

| Path | Content |
|---|---|
| `src/research/` | The pipeline: ingestion, forcing, skill decomposition, calibration, decision value, dashboard export, paper figures |
| `tests/research/` | 56 tests, including leakage tests on synthetic data and an end-to-end look-ahead test on the real data |
| `reports/` | Every result table and figure (CSV / JSON / PNG) |
| `paper/` | Manuscript (`main.tex`, `main.pdf`), generated figures, tables and `numbers.tex` |
| `frontend/` | Static dashboard (React + Vite) reading `frontend/public/data/` |
| `docs/` | Process journal, audit, literature review, research gaps, phase plan, one document per phase |
| `legacy/` | The original pipeline, retired because it trained on borehole depth instead of water level ([why](docs/01-project-audit.md)) |

## Reproduce

```bash
conda activate anpr                         # Python 3.12; pip install -r requirements-research.txt
bash scripts/reproduce.sh --forcing --phase2 --phase3 --phase4
python -m src.research.export_dashboard     # dashboard data
python -m src.research.paper_figures        # paper figures, tables, numbers
cd paper && latexmk -pdf main.tex
```

`reproduce.sh` downloads the public forcing data (IMD via `imdlib`, NOAA PSL indices), rebuilds every
result from `data/raw/` and asserts reference values at each phase. Phase 2 runs Chronos-2 on a GPU if
one is available (about 45 minutes in total on 16 cores).

Dashboard:

```bash
cd frontend && npm install
npm run dev        # http://localhost:5173
npm run build      # static site in frontend/dist/, deployable to any static host
```

Optional: refresh manual-well readings from India-WRIS for the dashboard's operational forecasts
(the research results are not affected): `python -m src.research.wris_refresh --states Rajasthan`.

## Data

Groundwater levels: a public compilation of CGWB monitoring data (`data/raw/`, see the
[data card](docs/data-card.md)). Rainfall and temperature: IMD gridded data (Pai et al., 2014;
Srivastava et al., 2009). Niño 3.4 and DMI: NOAA PSL (HadISST). State boundaries: geoBoundaries.
Redistribution terms of the groundwater compilation are being confirmed before processed data are archived.

## Citation and licence

See [CITATION.cff](CITATION.cff). The licence for code and outputs is still to be chosen by the author
before the public release.

## How this project got here

The original version of this repository reported R² = 0.9998 from a Temporal Fusion Transformer with
GA/PSO pumping optimisation. An audit found that the model was trained on each borehole's constant
depth instead of its water level, so those results were withdrawn. The full record of the audit, the
literature survey, the choice of research gaps and every phase since is in
[docs/00-process-journal.md](docs/00-process-journal.md).
