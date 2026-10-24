"""
Research Pipeline — Shared Configuration
Single source of truth for paths, split years, horizons and seeds used by every research step.
Change values here, never inline, so experiments stay comparable.
"""

from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────────────
DATA_RAW = Path("data/raw/Groundwater India Data.csv")
DATA_PROCESSED_DIR = Path("data/processed")
EXTERNAL_DIR = Path("data/external")  # git-ignored third-party downloads
REPORTS_DIR = Path("reports/benchmark")
FORCING_REPORTS_DIR = Path("reports/forcing")
SKILL_REPORTS_DIR = Path("reports/skill")
FRONTEND_DATA_DIR = Path("frontend/public/data")

# ── Time-blocked split (by forecast *target* year) ──────────────────────────
TRAIN_END_YEAR = 2015
CAL_END_YEAR = 2018  # calibration = TRAIN_END_YEAR+1 … CAL_END_YEAR; test = after

# ── Forecasting task ────────────────────────────────────────────────────────
HORIZONS = [1, 2, 4]  # campaigns ahead (≈ 3, 6, 12 months)
NOMINAL_LEVELS = [0.5, 0.8, 0.9, 0.95]
EXCEEDANCE_PERCENTILE = 0.8
RANDOM_SEED = 42

# ── Forcing data (Phase 1) ──────────────────────────────────────────────────
FORCING_FIRST_YEAR = 1990  # four spare years before the first well reading for 12-month windows and SPI
FORCING_LAST_YEAR = 2025
SPI_FIT_END_YEAR = TRAIN_END_YEAR  # SPI gamma parameters are fitted on ≤ this year only (no leakage)
INDEX_LAGS_MONTHS = [0, 3, 6]
