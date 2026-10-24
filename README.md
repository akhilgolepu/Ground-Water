# ML-Based Groundwater Level Forecasting for Sustainable Water Resource Management

> **Status (2026-10-24).** The Phase 1–5 results below came from a pipeline that trained on
> `wellDepth` (borehole depth, constant per well) instead of the water level, so they are
> **withdrawn** (see [docs/01-project-audit.md](docs/01-project-audit.md)). The current research
> pipeline is in `src/research/`, and the research plan, literature review and pilot results are in
> [docs/](docs/README.md). Reproduce with:
>
> ```bash
> conda activate anpr
> python -m src.research.ingest && python -m src.research.benchmark
> cd frontend && npm install && npm run dev
> ```

An end-to-end, artificial intelligence-driven hydrological decision support system that ingests spatio-temporal groundwater records, performs multi-horizon probabilistic predictions using a **Temporal Fusion Transformer (TFT)**, provides local/global model explainability (**XAI** via VSN and TreeSHAP), and optimizes agricultural tube-well pumping quotas using **Metaheuristic Algorithms (GA & PSO)**.

---

## 📌 System Architecture & Pipeline Overview

```text
[ Historical & Environmental Data ]
               │
               ▼
 [ Data Cleaning & Preprocessing ] (Spline + Kalman Imputation, Ordinary Kriging)
               │
               ▼
 [ Feature Engineering Pipeline  ] (Lags, Rolling Stats, API, SPEI, Cyclic Encodings)
               │
   ┌───────────┴───────────┐
   │ Temporal Fusion Trans.│ ◄── Multi-Quantile Loss (q ∈ {0.1, 0.5, 0.9})
   └───────────┬───────────┘
               │
 ┌─────────────┼──────────────────────────────┐
 ▼             ▼                              ▼
[ TFT VSN &   [ Probabilistic Intervals ]   [ Natural Language Policy ]
 TreeSHAP XAI ]  (PICP_80 = 99.87%)            (NLG Explanation Layer)
 └─────────────┬──────────────────────────────┘
               ▼
 [ Metaheuristic Optimization  ] (GA / PSO Safe Quota Solver Q_pump)
               │
               ▼
 [ Policy Briefs & Decision Support ]
```

---

## 📂 Repository Structure

```text
GroundWater/
├── data/
│   ├── raw/
│   │   └── Groundwater India Data.csv          # Raw CGWB / India-WRIS records
│   └── processed/
│       ├── feature_matrix.parquet              # 410,512 x 27 engineered matrix
│       └── feature_matrix.csv                  # CSV fallback
├── models/
│   ├── tft_checkpoint.pth                      # Trained TFT model weights
│   ├── xgboost_baseline.joblib                 # Trained XGBoost model
│   ├── scaler.pkl                              # StandardScaler artifact
│   └── phase3_benchmark_metrics.json           # Model evaluation results
├── reports/
│   ├── vsn_feature_importance.csv              # Global TFT VSN importance
│   ├── shap_feature_importance.csv             # TreeSHAP driver importance
│   └── optimal_pumping_quotas.csv              # Phase 5 optimization schedules
├── src/
│   ├── data/
│   │   ├── preprocessing.py                    # Spline, Kalman & Kriging routines
│   │   ├── spatial_resampling.py               # Monthly 'MS' temporal alignment
│   │   ├── feature_engineering.py             # Lag, rolling, SPEI, API features
│   │   └── data_preprocessing_pipeline.py      # Master Phase 2 execution pipeline
│   ├── models/
│   │   ├── baselines.py                        # XGBoost & PyTorch LSTM baselines
│   │   ├── tft_model.py                        # TFT architecture & Quantile Loss
│   │   └── train.py                            # Chronological split & trainer driver
│   ├── explainability/
│   │   └── explain.py                          # Phase 4 XAI & NLG policy brief generator
│   └── optimization/
│       └── metaheuristic_solver.py             # Phase 5 GA & PSO policy solver
└── README.md
```

---

## 🔬 Execution Summary & Phase Results

### 🔹 Phase 1 & 2: Data Cleaning, Alignment & Feature Engineering

- **Raw Data Ingestion**: Ingested `416,952` historical records across `6,440` CGWB/India-WRIS groundwater monitoring stations.
- **Missing Value Handling**: Applied 3rd-order **Cubic Spline Interpolation** and state-space **Kalman Smoothing** to eliminate temporal gaps.
- **Spatial Interpolation**: Performed **Spatial Ordinary Kriging** across unmonitored zones, generating a spatial grid surface of shape `(244, 274)`.
- **Temporal Alignment**: Resampled continuous water table series to uniform monthly intervals (`'MS'`).
- **Feature Construction (27 Total Features)**:
  - *Target Variable*: `depth_to_water_m` (depth to water table in meters below ground level, $\text{m bgl}$).
  - *Static Metadata*: Elevation, soil hydraulic conductivity, soil porosity, land cover type.
  - *Known Future Inputs*: Trigonometric cyclical transformations ($\sin/\cos$) for month and day of year.
  - *Observed Past Inputs*: Historical autoregressive lags ($k \in \{1, 2, 3, 6, 12\}$ months), rolling window dynamics (3, 6, 12 months $\mu$ and $\sigma$), Antecedent Precipitation Index (API with decay factor $k=0.90$), and Standardized Precipitation Evapotranspiration Index (SPEI-3, SPEI-6).
- **Final Feature Matrix**: **`410,512` sequence rows $\times$ `27` predictor features** saved to `data/processed/feature_matrix.parquet`.

---

### 🔹 Phase 3: Predictive Modeling & Benchmarking (TFT Engine)

- **Dataset Splitting**: Chronological station-level train/validation/test split (**70% Train / 15% Validation / 15% Test**) with zero temporal data leakage:
  - **Train Set**: `284,860` rows
  - **Validation Set**: `59,021` rows
  - **Test Set**: `66,631` rows
- **Loss Function**: Multi-Quantile Pinball Loss over target quantiles $q \in \{0.1, 0.5, 0.9\}$:
  $$\mathcal{L}_{\text{Quantile}}(y, \hat{y}) = \sum_{q \in \{0.1, 0.5, 0.9\}} \max\left(q(y - \hat{y}_q), (q - 1)(y - \hat{y}_q)\right)$$
- **Evaluation Benchmark Matrix**:

| Model Architecture | RMSE ($\text{m}$) | MAE ($\text{m}$) | $R^2$ Score | $\text{PICP}_{80}$ Coverage | Probabilistic Bounds |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **XGBoost Baseline** | $0.9308$ | $0.3601$ | $0.9998$ | N/A | Point Forecast |
| **PyTorch LSTM Baseline** | $5.8145$ | $0.5366$ | $0.9926$ | N/A | Point Forecast |
| **Temporal Fusion Transformer (TFT)** | **$2.9085$** | **$0.2566$** | **$0.9981$** | **$99.87\%$** | **Quantiles ($q_{0.1}, q_{0.5}, q_{0.9}$)** |

> **Key Finding**: TFT achieved the lowest Mean Absolute Error (**$0.2566\text{ m}$** / $\approx 25.6\text{ cm}$) and maintained **$99.87\%$ empirical coverage** within its $80\%$ prediction intervals ($q_{0.1} - q_{0.9}$).

---

### 🔹 Phase 4: Model Interpretability & Natural Language Explanation (XAI)

#### 1. Global Feature Importance (TFT VSN vs. TreeSHAP)

| Feature Name | TFT VSN Weight | TreeSHAP Mean $|\text{SHAP}|$ | Hydrological Interpretation |
| :--- | :---: | :---: | :--- |
| `depth_to_water_m_lag_3` | **0.3478 - 0.3733** | 0.0520 | Long-term memory capturing quarterly seasonal cycles |
| `depth_to_water_m_roll_mean_12` | **0.2676 - 0.2888** | 0.0120 | Annual baseline moving average filtering short noise |
| `depth_to_water_m_lag_1` | 0.0600 - 0.0630 | **38.7610 - 39.3530** | Immediate step autoregressive momentum driver |
| `depth_to_water_m_roll_mean_3` | 0.0638 - 0.0658 | **10.9192 - 11.0826** | Short-term 3-month seasonal trend indicator |

#### 2. Sample Natural Language Generation (NLG) Policy Brief

```text
============================================================
POLICY BRIEF FOR MONITORING WELL [184135083184001]:
• Current Water Depth : 10.20 m bgl
• Predicted Forecast  : 10.10 m bgl (Median)
• Projected Change    : Expected increase (recharge) of 0.10 meters over the next horizon.
• Confidence Interval : 80% probability depth remains between 9.74 m and 10.58 m bgl.
• Primary Drivers     : Depth To Water M Lag 1 (supporting recharge), 
                        Depth To Water M Roll Mean 3 (supporting recharge).
• Advisory Action     : STABLE CONDITIONS — Maintain standard seasonal extraction quotas.
============================================================
```

---

### 🔹 Phase 5: Metaheuristic Policy Optimization Engine

- **Mathematical Problem Formulation**:
  $$\max_{\mathbf{Q}_{\text{pump}}} \sum_{i=1}^{N} Q_{\text{agri}, i} - \lambda \sum_{i=1}^{N} \max\left(0, W_{\text{predicted}, i}(\mathbf{Q}_{\text{pump}}) - W_{\text{safe}, i}\right)^2$$
  where $W_{\text{predicted}}$ is inferred via the trained TFT model, $W_{\text{safe}}$ is the critical drawdown threshold, and $\lambda = 10^4$ enforces hard safety limits.

- **Optimization Results (Target Station `optima-239`)**:
  - Current Depth: $104.00\text{ m bgl}$
  - Critical Safety Threshold ($W_{\text{safe}}$): $15.00\text{ m bgl}$
  - **Genetic Algorithm (GA) Convergence**: Optimal Pumping Quota Factor ($\alpha$) = **$0.0\%$**
  - **Particle Swarm Optimization (PSO) Convergence**: Optimal Pumping Quota Factor ($\alpha$) = **$0.0\%$**
  - Predicted Post-Pumping Table Depth: $104.05\text{ m bgl}$

> **Policy Insight**: For severely depleted aquifers where depth ($104.00\text{ m bgl}$) exceeds safety bounds ($15.00\text{ m bgl}$), the solver enforces a total abstraction shutdown ($\alpha = 0.0\%$) to prevent critical collapse.

---

## 🚀 Execution Instructions

### 1. Environment Setup

```bash
git clone https://github.com/YourUsername/GroundWater.git
cd GroundWater
conda create -n groundwater python=3.12 -y
conda activate groundwater
pip install -r requirements.txt
```

### 2. Pipeline Execution Commands

```bash
# Phase 2: Data Cleaning, Imputation & Feature Engineering Matrix
python -m src.data.data_preprocessing_pipeline

# Phase 3: Train TFT, XGBoost, and LSTM Models
python -m src.models.train

# Phase 4: Extract XAI Feature Attributions & Generate Policy Briefs
python -m src.explainability.explain

# Phase 5: Run Metaheuristic Policy Optimization Solver (GA & PSO)
python -m src.optimization.metaheuristic_solver
```

---

## 🔮 Roadmap & Upcoming Features

- [x] **Phase 1**: Ingestion Pipelines for In-situ Wells & Grids
- [x] **Phase 2**: Spline/Kalman Imputation, Kriging & Feature Matrix Construction
- [x] **Phase 3**: Multi-Horizon TFT Forecasting with Quantile Loss
- [x] **Phase 4**: TFT VSN, TreeSHAP Attributions & Natural Language Briefs
- [x] **Phase 5**: Metaheuristic Policy Optimization Engine (GA/PSO)
- [ ] **Phase 6**: Interactive Decision Support Dashboard (`Streamlit` / `Plotly`)
- [ ] **Phase 7**: Automated Risk Thresholding & Dispatch Notifier (`Twilio` / `Email API`)