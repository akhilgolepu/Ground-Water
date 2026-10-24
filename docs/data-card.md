# Data Card — CGWB groundwater levels ("Groundwater India Data")

## Provenance
- **File:** `data/raw/Groundwater India Data.csv` (35 MB, 416 952 rows, 6 440 stations).
- **Origin:** a public Kaggle compilation of Central Ground Water Board (CGWB) levels as published
  through India-WRIS. The compiler, compilation date and exact download query are **not recorded**.
  Record them before submission, or rebuild from India-WRIS directly (Phase 5.4).
- **Licence:** CGWB/India-WRIS data are released under the Government Open Data Licence – India
  (NDSAP). The Kaggle re-distribution licence must be checked before we re-publish processed data.
- **Companion file:** `gwq_chemical_parameter_manual_cgwb_ap_1961_2025 (1).csv`, with 10 950 CGWB
  water-quality samples for Andhra Pradesh (pH, EC, TDS, major ions, F, NO₃, trace metals). Not yet used.

## Fields used

| Column | Meaning | Notes |
|---|---|---|
| `station_id` | CGWB station code | `CGW…` prefixes are DWLR telemetry stations; numeric IDs are manual wells |
| `datetime` | Observation date | Real dates. The legacy pipeline ignored them |
| `target` | Water level (m) | **Two sign conventions**: manual wells positive m bgl, DWLR wells negative. Harmonised per station by majority sign |
| `latitude`, `longitude` | WGS84 | |
| `wellDepth` | Borehole construction depth (m) | Static per station. **Not a water level**; used only as a static feature |
| `rainfall`, `t  kmnpnn]2m`, `t2m_max`, `t2m_min` | Weather **on the observation day** | Point-in-time values, NASA-POWER-like names; one header is corrupted. Unusable as seasonal forcing for manual wells (median 3.4 mm per well-year) |
| `month` | Calendar month | Redundant with `datetime` |
| `wellAquiferType_encoded`, `State_encoded`, `District_encoded` | Encoded categoricals | Only 2 values each, so the encoding is broken. Not used |

## Sampling
- **Manual network:** 5 518 wells read in four campaigns (January, pre-monsoon May,
  monsoon August, post-monsoon November), 1994–2025. Most records end in 2022–2023.
- **DWLR telemetry:** 922 wells with near-daily readings, mostly 2023–2025.
- Median record length: 10 years. Readings per station range from 1 to 439.

## Known defects and how they are handled

| Defect | Handling (`src/research/ingest.py`) |
|---|---|
| Mixed sign conventions | Station majority sign → positive depth below ground |
| Gross errors (−2014 to +2430 m) | Keep −5 ≤ depth ≤ 250 m (516 rows dropped) |
| Spikes within a station | Robust z-score with MAD > 8 dropped (2 330 rows) |
| Off-campaign months | Mapped to the nearest campaign; duplicates averaged |
| Point-in-time weather | Replaced by IMD gridded forcing (Phase 1, [07-forcing-data.md](07-forcing-data.md)); kept only as the `snap_*` control arm |

## Processed outputs

| File | Content |
|---|---|
| `data/processed/gwl_observations_clean.parquet` | 414 106 cleaned readings with `depth_mbgl` |
| `data/processed/gwl_campaigns.parquet` | 246 887 well-campaign values (manual wells) |
| `data/processed/station_catalog.parquet` | One row per station: network, location, record span, median depth |
| `data/processed/forcing_features.parquet` | 334 068 well-campaign rows of rainfall, SPI, temperature, ENSO/IOD, oracle and snapshot features |
| `data/processed/feature_matrix.*` | **Legacy, invalid** (target = `wellDepth`). Kept for the audit trail only |
