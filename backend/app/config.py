"""Path resolution and global settings for the AquaSense AI backend."""

from pathlib import Path

# backend/app/config.py -> project root is two levels up (GroundWater/)
APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FEATURE_MATRIX_PARQUET = DATA_PROCESSED_DIR / "feature_matrix.parquet"
FEATURE_MATRIX_CSV = DATA_PROCESSED_DIR / "feature_matrix.csv"

MODELS_DIR = PROJECT_ROOT / "models"
TFT_CHECKPOINT = MODELS_DIR / "tft_checkpoint.pth"
XGBOOST_BASELINE = MODELS_DIR / "xgboost_baseline.joblib"
SCALER_PATH = MODELS_DIR / "scaler.pkl"

REPORTS_DIR = PROJECT_ROOT / "reports"
VSN_IMPORTANCE_CSV = REPORTS_DIR / "vsn_feature_importance.csv"
SHAP_IMPORTANCE_CSV = REPORTS_DIR / "shap_feature_importance.csv"

TARGET_COL = "depth_to_water_m"
EXCLUDE_FEATURE_COLS = frozenset({"well_id", "timestamp", "land_cover_type", TARGET_COL})

DEFAULT_FORECAST_HORIZON_MONTHS = 12
HISTORY_MONTHS_IN_FORECAST = 24
