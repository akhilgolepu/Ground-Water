"""
Research Pipeline — Step 1: Corrected Ingestion
Reads 'Groundwater India Data.csv' using the real water-level column (`target`) and
real observation dates, harmonises the two sign conventions in the CGWB data, removes
gross outliers, and builds a per-station seasonal "campaign" series.

Why this module exists (see docs/01-project-audit.md):
the legacy Phase 2 pipeline keyword-matched `wellDepth` (static borehole depth) as the
target and fabricated monthly timestamps, which made every downstream metric invalid.

Conventions
-----------
- depth_mbgl : depth to water level in metres below ground level (positive = below ground).
- Manual CGWB wells report positive m bgl; DWLR telemetry wells report negative values.
  The station's majority sign decides the conversion.
- CGWB manual monitoring happens in four campaigns: January, pre-monsoon (May),
  monsoon (August) and post-monsoon (November). Off-month readings are mapped to the
  nearest campaign so every station lives on one quarterly grid.
"""

import warnings
from pathlib import Path
import numpy as np
import pandas as pd

from src.research.config import DATA_PROCESSED_DIR, DATA_RAW

# Calendar month -> campaign season index (0=Jan, 1=May/pre-monsoon, 2=Aug, 3=Nov/post-monsoon)
MONTH_TO_SEASON = {12: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3}
SEASON_NAMES = ["Jan", "May (pre-monsoon)", "Aug (monsoon)", "Nov (post-monsoon)"]

TELEMETRY_MAX_MEDIAN_GAP_DAYS = 7
DEPTH_MIN_M, DEPTH_MAX_M = -5.0, 250.0  # allow slight artesian heads; drop gross errors
MAD_LIMIT = 8.0


def load_raw_observations(filepath: Path = DATA_RAW) -> pd.DataFrame:
    """Loads raw rows with real timestamps and the real water-level column."""
    df = pd.read_csv(filepath, low_memory=False)
    df = df.rename(columns={
        "station_id": "well_id",
        "datetime": "timestamp",
        "target": "water_level_raw",
        "wellDepth": "well_depth_m",
    })
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp", "water_level_raw"])
    return df[["well_id", "timestamp", "water_level_raw", "latitude", "longitude", "well_depth_m", "rainfall"]]


def classify_networks(df: pd.DataFrame) -> pd.Series:
    """Labels each station 'DWLR' (telemetry, near-daily) or 'manual' (seasonal campaigns)."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)  # single-reading stations
        median_gap = df.sort_values("timestamp").groupby("well_id")["timestamp"].apply(
            lambda s: s.diff().dt.days.median()
        )
    return pd.Series(
        np.where(median_gap.fillna(np.inf) <= TELEMETRY_MAX_MEDIAN_GAP_DAYS, "DWLR", "manual"),
        index=median_gap.index,
        name="network",
    )


def harmonise_depth(df: pd.DataFrame) -> pd.DataFrame:
    """Converts raw readings to positive depth below ground using each station's majority sign."""
    df = df.copy()
    neg_share = df.groupby("well_id")["water_level_raw"].transform(lambda s: (s < 0).mean())
    df["depth_mbgl"] = np.where(neg_share > 0.5, -df["water_level_raw"], df["water_level_raw"])
    return df


def remove_outliers(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Drops physically implausible depths and per-station robust (MAD) outliers."""
    n0 = len(df)
    df = df[(df["depth_mbgl"] >= DEPTH_MIN_M) & (df["depth_mbgl"] <= DEPTH_MAX_M)]
    n_range = n0 - len(df)

    med = df.groupby("well_id")["depth_mbgl"].transform("median")
    mad = df.groupby("well_id")["depth_mbgl"].transform(lambda s: (s - s.median()).abs().median())
    robust_z = (df["depth_mbgl"] - med).abs() / (1.4826 * mad.clip(lower=0.25))
    keep = robust_z <= MAD_LIMIT
    n_mad = int((~keep).sum())
    df = df[keep]

    return df, {"rows_in": n0, "dropped_range": int(n_range), "dropped_mad": n_mad, "rows_out": len(df)}


def build_campaign_series(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates observations onto the quarterly CGWB campaign grid.
    campaign_idx = year * 4 + season; a December reading counts toward the next January.
    """
    df = df.copy()
    month = df["timestamp"].dt.month
    year = df["timestamp"].dt.year + (month == 12).astype(int)
    df["season"] = month.map(MONTH_TO_SEASON)
    df["year"] = year
    df["campaign_idx"] = df["year"] * 4 + df["season"]

    camp = (
        df.groupby(["well_id", "campaign_idx"])
        .agg(depth_mbgl=("depth_mbgl", "mean"), n_raw=("depth_mbgl", "size"),
             year=("year", "first"), season=("season", "first"))
        .reset_index()
    )
    return camp


def build_station_catalog(df: pd.DataFrame, networks: pd.Series) -> pd.DataFrame:
    """Per-station metadata used by the benchmark and the dashboard."""
    cat = df.groupby("well_id").agg(
        latitude=("latitude", "first"),
        longitude=("longitude", "first"),
        well_depth_m=("well_depth_m", "first"),
        n_obs=("depth_mbgl", "size"),
        first_obs=("timestamp", "min"),
        last_obs=("timestamp", "max"),
        median_depth_m=("depth_mbgl", "median"),
    )
    cat["network"] = networks.reindex(cat.index)
    cat["record_years"] = (cat["last_obs"] - cat["first_obs"]).dt.days / 365.25
    return cat.reset_index()


def run_ingestion() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    print("=== Research Step 1: Corrected Ingestion ===")
    raw = load_raw_observations()
    print(f"Loaded {len(raw):,} rows across {raw['well_id'].nunique():,} stations "
          f"({raw['timestamp'].min():%Y-%m-%d} → {raw['timestamp'].max():%Y-%m-%d}).")

    networks = classify_networks(raw)
    print(f"Networks: {networks.value_counts().to_dict()}")

    obs = harmonise_depth(raw)
    obs, qc = remove_outliers(obs)
    print(f"Quality control: {qc}")

    catalog = build_station_catalog(obs, networks)
    manual_ids = catalog.loc[catalog["network"] == "manual", "well_id"]
    campaigns = build_campaign_series(obs[obs["well_id"].isin(manual_ids)])
    print(f"Campaign series: {len(campaigns):,} station-campaigns from {campaigns['well_id'].nunique():,} manual wells.")

    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    obs.to_parquet(DATA_PROCESSED_DIR / "gwl_observations_clean.parquet", index=False)
    campaigns.to_parquet(DATA_PROCESSED_DIR / "gwl_campaigns.parquet", index=False)
    catalog.to_parquet(DATA_PROCESSED_DIR / "station_catalog.parquet", index=False)
    print("Saved gwl_observations_clean / gwl_campaigns / station_catalog parquet files.")
    return obs, campaigns, catalog


if __name__ == "__main__":
    run_ingestion()
