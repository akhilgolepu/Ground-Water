# 02 — Literature Review

Scope: machine-learning groundwater-level (GWL) forecasting with emphasis on (a) India,
(b) uncertainty, (c) foundation models, (d) decision support. Sources were found with
OpenAlex and web search (abstracts, repositories and preprints). Items marked *preprint*
or *software* are not peer reviewed. "Not found" means no hit in OpenAlex title/abstract
search or web search on 2026-10-24, not proof of absence; re-check in Scopus/WoS before
submission.

## A. The ten papers you supplied

| # | Study | Setting | Method | Uncertainty | Baseline vs naive? | What it leaves open |
|---|---|---|---|---|---|---|
| [1] | Jesse et al. 2025, *Applied Computing & Geosciences* | PRISMA review, 223 papers | ANN/SVM/LSTM/RF dominate; hybrids with PSO/GA/ACO; transformers emerging | Not a focus | — | States outright: feature selection is "one of the most underdeveloped areas"; **"no study systematically compared multiple feature selection strategies"**; tuning is mostly trial-and-error |
| [2] | Davari et al. 2025/26, *Sci. Rep.* | Najafabad plain, Iran, 5 zones | XGBoost / RF / SVM with climatic + abstraction inputs | None | No | Single plain; relies on abstraction data that India lacks; no intervals |
| [3] | Li, Wang & Zhou 2026, *Front. Earth Sci.* | Leizhou Peninsula, China; 2023 snapshot | **AlphaEarth Foundation embeddings** + TabPFN for spatial GWD mapping | 95 % CI on metrics only | No | Spatial snapshot only (one year); authors call it a "preliminary screening tool" — embeddings never used for **temporal** forecasting |
| [4] | Feng, Ghorbani & Radwan 2024, *Front. Environ. Sci.* (105 citations) | Izeh City, Iran | CNN/RNN/SVM/DT/RF/GAN on extraction, rainfall, river flow | None | No | R² = 0.995 on one city with random split — typical of the over-optimistic local studies |
| [5] | Gad et al. 2024, *Heliyon* | El-Menoufia, Egypt, 48 wells | Quality indices + multivariate stats + RNN | None | — | Quality only, no level; no link between quantity and quality |
| [6] | Kanito, Benaafi & Baalousha 2025, *Hydrology* | Ruataniwha, NZ, 6 wells | RF / SVM with seasonal decomposition; 80/20 split | BMA p-/d-factor (87–98 % inside bounds) | No | 6 wells; coverage not compared to a nominal level; no calibration guarantee |
| [7] | Phan, Hoang & de Carvalho 2026, *Acta Sci. Pol.* | Nghe An, Vietnam, 6-well regional mean | **SNaïve, ETS, SARIMA** | Residual diagnostics | **Yes** (SNaïve) | Shows simple statistical models are competitive — most ML papers never test against them |
| [8] | Elmotawakkil et al. 2025, *Front. Remote Sens.* | Feija Basin, Morocco | TabNet / TabTransformer / CatBoost recharge-zone classification, PSO tuning | None | — | Static recharge potential, not time-series forecasting |
| [9] | Chu et al. 2022, *Sustainability* | 2 USA wells, daily | LSTM + partial mutual information + bootstrap; **teleconnections (AO, Niño 3.4, PNA)** | Bootstrap ensemble | No | Two wells; teleconnection idea never tested for monsoon India (ENSO/IOD) |
| [10] | Haider et al. 2023, *Water* | 17 wells, South Korea | **TCN** vs LSTM/ANN at 1-, 3-, 6-month leads | None | No | Small network; no uncertainty; no naive baseline |

**Cross-cutting pattern.** 9 of 10 use ≤ 48 wells, random or single splits, and no naive
baseline. None uses calibrated (distribution-free) intervals or checks coverage against the
nominal level. None evaluates the *decision value* of a forecast.

## B. Wider literature that shapes the gap

### B1. India-scale forecasting
- **Malakar et al. 2021**, *ACS ES&T Engineering* — LSTM/RNN/FNN on 5 367 Indian wells
  (1996–2018); > 84 % of wells r > 0.6. First India-wide DL forecast. No intervals, no forcing study.
  [doi:10.1021/acsestengg.0c00238](https://doi.org/10.1021/acsestengg.0c00238)
- **Alphoenixx 2026** (*software release*, Zenodo, July 2026) — benchmark of persistence,
  seasonal naive, climatology, RF, XGBoost, LSTM, GRU and **Chronos-2 zero-shot** on the
  **same Kaggle "Groundwater India Data" file used here** (6 432 wells, 1994–2023). Includes
  split/Mondrian conformal (by region and history tercile), CRPS, PIT, exceedance risk with
  BSS/AUC, spatial blocked CV, kriging correction, MCS and Diebold–Mariano tests. Random
  Forest best (h1 RMSE 2.27 m); Chronos-2 competitive zero-shot. **Its climate ablation finds
  ≈ 0 % gain — but it builds "rainfall" features by summing the file's single-day rainfall
  snapshots** (see §C1). No journal paper found yet.
  [doi:10.5281/zenodo.21192818](https://doi.org/10.5281/zenodo.21192818)

> **Implication:** a generic "benchmark of ML models on Indian wells" is no longer novel.
> Our paper must cite this release and differentiate on forcing, conditional calibration
> and decision value.

### B2. Global vs local and foundation models
- Heudorfer, Liesch & Broda 2024, *HESS* — entity-aware global model with static features.
- Ohmer & Liesch 2025 (*preprint*) — ~3 000 German wells: no systematic advantage of global over local models.
- Ohmer et al. 2026, *ESSD* — open German benchmark (3 000+ wells, weekly, 32 years).
- German N-HiTS vs TFT (~5 300 wells): **TFT below N-HiTS** (median NSE 0.34 vs 0.50 at 12 weeks).
- **Kim, Park & Park 2026** (*preprint*, ESSOAr) — TimesFM-3, Chronos-2 and Moirai-2 on Korean
  wells: level history alone cuts persistence error by 20–30 %; past weather adds little;
  **known forecast-day weather removes a further 38–44 %**. Forcing, not site-specific
  learning, is the main source of short-horizon skill.
  [doi:10.22541/essoar.15009801/v1](https://doi.org/10.22541/essoar.15009801/v1)
- Park, Park & Kim 2026 (*submitted to WRR*) — groundwater fluctuation equation as a
  physics loss, including LoRA adapters on TimesFM-3.

### B3. Uncertainty
- No peer-reviewed groundwater-**level** paper using conformal prediction was found.
  Closest: a nitrate-concentration conformal benchmark (*SSRN preprint*, 24 wells).
- Water-domain conformal methods note the exchangeability assumption fails under seasonality
  and trend — motivating adaptive/Mondrian variants.

### B4. Forcing, teleconnections, drought
- Teleconnections as GWL predictors: Chu et al. 2022 (USA). **ENSO/IOD-driven groundwater
  prediction for India: not found.**
- Groundwater drought indices (SGI/SWI) for India are diagnostic (Marathwada,
  Indo-Gangetic Plain) or district-scale (Odisha SGI forecasting, 10 wells, EGU 2026 abstract).
- Validation practice: blocked CV gives the most reliable estimates (EGUsphere 2025-3539).

### B5. Decision support and optimisation
- Simulation–optimisation with surrogates + GA/PSO is mature (2024 review; Roy & Datta 2025).
  It needs an abstraction (pumping) variable, which this dataset does not have.
- Energy as an abstraction proxy in India: 4.7–6.0 m³/kWh (Gujarat). No ML forecasting study
  combines DISCOM energy data with Indian GWL.
- **Cost–loss / relative economic value of groundwater forecasts: not found** (standard in
  weather forecasting since Richardson 2000).
- LLM advisories for water: conceptual only; no evidence they improve farmer decisions.

### B6. Remote sensing and geospatial foundation models
- GRACE downscaling for India validated against wells (IITH; 2026 EGUsphere 0.5° product).
- AlphaEarth embeddings: used for CAMELS-US streamflow attributes and for [3]; **not used as
  static descriptors in temporal GWL forecasting** (not found).

## C. Data-specific findings that matter for the literature

1. **The Kaggle file's weather columns are point-in-time.** For manual wells they hold
   rainfall/temperature *on the observation day* (median 3.4 mm summed per well-year).
   Any study that aggregates them as seasonal forcing (e.g. Alphoenixx's `rain_cum4`) measures
   noise. The question "does the monsoon add skill?" is therefore still open for national-scale India.
2. **Mixed sign conventions** (manual positive, DWLR negative) must be harmonised. Alphoenixx
   filters by `|target|`, and its handling of DWLR stations is unclear.
3. **Conditional miscoverage by depth** (our pilot): a single global conformal interval covers
   **88 % for wells < 5 m but 44 % for wells ≥ 40 m**. Alphoenixx's Mondrian conformal is by
   region and history tercile, not by depth class.

## Sources
- User-supplied [1]–[10]: see `references.bib`.
- [Alphoenixx benchmark repo](https://github.com/Alphoenixx/Benchmarking-ML-Models-for-Quarterly-Groundwater-Level-Forecasting-in-India)
- [Malakar et al. (ORNL)](https://impact.ornl.gov/en/publications/deep-learning-based-forecasting-of-groundwater-level-trends-in-in/)
- [Heudorfer et al. HESS 2024](https://hess.copernicus.org/articles/28/4407/2024/)
- [TFT vs N-HiTS Germany (DGGV)](https://www.dggv.de/e-publikationen/advancing-short-term-groundwater-level-forecasting-using-temporal-fusion-transformer-tft-and-neural-hierarchical-interpolation-for-time-series-forecasting-n-hiits/)
- [Validation schemes (EGUsphere 2025-3539)](https://egusphere.copernicus.org/preprints/2025/egusphere-2025-3539/)
- [Conformal nitrate preprint (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7578013)
- [Energy as abstraction proxy (CGIAR)](https://cgspace.cgiar.org/items/7f722fa6-e6d9-437b-8b67-9644d0807efa)
- [Odisha SGI forecasting EGU26](https://meetingorganizer.copernicus.org/EGU26/EGU26-22079.html)
- [CGWB DWLR network](https://cgwb.gov.in/node/1858)
- [ST-GNN groundwater (Sci. Rep. 2024)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11490608/)
- [Simulation–optimisation review](https://www.scientific.net/AEF.47.89)
