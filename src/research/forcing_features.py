"""
Research Pipeline — Phase 1.4–1.8: Forcing Features
Turns IMD gridded rainfall/temperature and NOAA climate indices into per-(well, campaign)
features for the skill-decomposition experiments, plus the oracle and snapshot-control arms
and the Phase 1 sanity checks.

Causality rule: a campaign reading can be taken early in its month, so every *past* window
ends the month **before** the campaign month. Only `oracle_*` columns look past the origin.
Normals (SPI gamma fits, monthly climatology for *_ratio) are fitted on ≤ SPI_FIT_END_YEAR only,
like a scaler fitted on training data, so calibration and test rows never see their own period.

Column families
  rain_*            rainfall totals over past windows (mm)
  spi_*             Standardised Precipitation Index (gamma fitted on ≤ SPI_FIT_END_YEAR only)
  jjas_*            last completed June–September monsoon total and its ratio to normal
  tmean_anom_3m     mean-temperature anomaly over the last 3 months (°C)
  nino34_lag*, dmi_lag*  teleconnection indices at 0/3/6-month lags
  oracle_*          rainfall between origin and target (hindsight; upper-bound arm only)
  snap_*            the source file's single-day rainfall snapshots (control arm reproducing prior work)
"""

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.research.forcing_download import imd_file
from src.research.config import (
    DATA_PROCESSED_DIR,
    EXTERNAL_DIR,
    FORCING_FIRST_YEAR,
    FORCING_LAST_YEAR,
    FORCING_REPORTS_DIR,
    HORIZONS,
    INDEX_LAGS_MONTHS,
    SPI_FIT_END_YEAR,
)

IMD_DIR = EXTERNAL_DIR / "imd"
CAMPAIGN_MONTH = {0: 1, 1: 5, 2: 8, 3: 11}  # season → calendar month of the campaign
SPI_SCALES = [3, 6, 12]
RAIN_WINDOWS = [3, 6, 12]
N_MONTHS = (FORCING_LAST_YEAR - FORCING_FIRST_YEAR + 1) * 12


def uses_fitted_normals(col: str) -> bool:
    """Columns standardised against normals fitted on ≤ SPI_FIT_END_YEAR."""
    return col.startswith(("spi_", "tmean_anom")) or col.endswith("_ratio")


# ── Month indexing ──────────────────────────────────────────────────────────

def campaign_month_index(campaign_idx: np.ndarray) -> np.ndarray:
    """Campaign index (year·4 + season) → months since Jan FORCING_FIRST_YEAR of the campaign month."""
    campaign_idx = np.asarray(campaign_idx)
    year, season = campaign_idx // 4, campaign_idx % 4
    month = np.vectorize(CAMPAIGN_MONTH.get)(season)
    return (year - FORCING_FIRST_YEAR) * 12 + (month - 1)


def nan_cumsum(monthly: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Cumulative sums with a leading zero column: (sums of values, counts of missing months).
    cums[0][:, t] = sum of months < t, so any window is two lookups.
    """
    zeros = np.zeros((monthly.shape[0], 1))
    filled = np.where(np.isnan(monthly), 0.0, monthly)
    return (np.concatenate([zeros, np.cumsum(filled, axis=1)], axis=1),
            np.concatenate([zeros, np.cumsum(np.isnan(monthly), axis=1)], axis=1))


def window_sum(cums: tuple[np.ndarray, np.ndarray], rows: np.ndarray, end_excl: np.ndarray, k) -> np.ndarray:
    """
    Sum of monthly values over months [end_excl − k, end_excl) for each (row, end) pair.
    NaN if the window leaves the record or contains any missing month.
    """
    cs, bad = cums
    k = np.broadcast_to(np.asarray(k), np.shape(end_excl))
    start = end_excl - k
    ok = (start >= 0) & (end_excl <= cs.shape[1] - 1) & (k > 0)
    out = np.full(len(rows), np.nan)
    r, e, b = rows[ok], end_excl[ok], start[ok]
    vals = cs[r, e] - cs[r, b]
    vals[(bad[r, e] - bad[r, b]) > 0] = np.nan
    out[ok] = vals
    return out


# ── Gridded data → per-cell monthly matrices ────────────────────────────────

def nearest_valid_cells(lats, lons, grid_lat, grid_lon, valid: np.ndarray, max_ring: int = 3):
    """Maps points to the nearest grid cell that has data (coastal wells often fall in sea cells)."""
    dlat, dlon = grid_lat[1] - grid_lat[0], grid_lon[1] - grid_lon[0]
    out = np.full(len(lats), -1, dtype=np.int64)
    n_lat, n_lon = valid.shape
    for i, (la, lo) in enumerate(zip(lats, lons)):
        ci, cj = int(round((la - grid_lat[0]) / dlat)), int(round((lo - grid_lon[0]) / dlon))
        best, best_d = -1, np.inf
        for r in range(max_ring + 1):
            for a in range(ci - r, ci + r + 1):
                for b in range(cj - r, cj + r + 1):
                    if 0 <= a < n_lat and 0 <= b < n_lon and valid[a, b]:
                        d = (grid_lat[a] - la) ** 2 + (grid_lon[b] - lo) ** 2
                        if d < best_d:
                            best, best_d = a * n_lon + b, d
            if best >= 0:
                break
        out[i] = best
    return out


def load_imd_monthly(var: str, how: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[int]]:
    """
    Reads every yearly IMD grid for `var` and returns monthly aggregates on the full grid:
    (monthly[lat, lon, month], grid_lat, grid_lon, years_loaded). `how` is "sum" or "mean".
    """
    import imdlib

    monthly, years, grid_lat, grid_lon = None, [], None, None
    for year in range(FORCING_FIRST_YEAR, FORCING_LAST_YEAR + 1):
        if imd_file(var, year) is None:
            continue
        ds = imdlib.open_data(var, year, year, fn_format="yearwise", file_dir=str(IMD_DIR)).get_xarray()
        da = ds[var].where(ds[var] > -90)  # IMD missing codes (-999, -99.9) → NaN
        if var != "rain":
            da = da.where(da < 90)  # temperature fill value 99.9
        agg = da.resample(time="MS").sum(min_count=20) if how == "sum" else da.resample(time="MS").mean()
        if monthly is None:
            grid_lat, grid_lon = ds["lat"].values, ds["lon"].values
            monthly = np.full((len(grid_lat), len(grid_lon), N_MONTHS), np.nan)
        for t, ts in enumerate(pd.to_datetime(agg["time"].values)):
            m = (ts.year - FORCING_FIRST_YEAR) * 12 + ts.month - 1
            monthly[:, :, m] = agg.isel(time=t).transpose("lat", "lon").values
        years.append(year)
    if monthly is None:
        raise FileNotFoundError(f"No IMD {var} files in {IMD_DIR / var}. Run src.research.forcing_download first.")
    return monthly, grid_lat, grid_lon, years


def _neighbour_stack(a: np.ndarray) -> np.ndarray:
    """[lat, lon, …] → [8, lat, lon, …] values of the 8 neighbours (NaN beyond the edge)."""
    p = np.pad(a, [(1, 1), (1, 1)] + [(0, 0)] * (a.ndim - 2), constant_values=np.nan)
    n_lat, n_lon = a.shape[:2]
    return np.stack([p[1 + di:1 + di + n_lat, 1 + dj:1 + dj + n_lon] for di in (-1, 0, 1) for dj in (-1, 0, 1)
                     if (di, dj) != (0, 0)])


def repair_zero_artefacts(monthly: np.ndarray, min_neighbour_mm: float = 100.0) -> tuple[np.ndarray, int, int]:
    """
    The IMD rain grid has cell-years stored as 0 mm all year. An isolated one (neighbours receive
    > min_neighbour_mm) is replaced by its neighbours' monthly mean; a block of them (e.g. NW
    Rajasthan 1998–2002, where gauges were sparse) is set to missing, since no part of India gets
    zero rain in a year. Returns (grid, repaired cell-years, masked cell-years).
    """
    out = monthly.copy()
    n_years = monthly.shape[2] // 12
    annual = monthly[:, :, : n_years * 12].reshape(*monthly.shape[:2], n_years, 12).sum(axis=3, where=~np.isnan(
        monthly[:, :, : n_years * 12].reshape(*monthly.shape[:2], n_years, 12)))
    annual[np.isnan(monthly[:, :, : n_years * 12].reshape(*monthly.shape[:2], n_years, 12)).all(axis=3)] = np.nan
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        neigh_median = np.nanmedian(_neighbour_stack(annual), axis=0)
        neigh_monthly = np.nanmean(_neighbour_stack(monthly), axis=0)
    zero = annual == 0
    artefact = zero & (neigh_median > min_neighbour_mm)
    masked = zero & ~artefact
    for y in range(n_years):
        sl = slice(y * 12, (y + 1) * 12)
        block = out[:, :, sl]
        if artefact[:, :, y].any():
            block[artefact[:, :, y]] = neigh_monthly[:, :, sl][artefact[:, :, y]]
        if masked[:, :, y].any():
            block[masked[:, :, y]] = np.nan
        out[:, :, sl] = block
    return out, int(artefact.sum()), int(masked.sum())


# ── SPI (Thom's gamma approximation, McKee et al. 1993) ─────────────────────

def spi_from_accumulations(acc: np.ndarray, fit_mask: np.ndarray) -> np.ndarray:
    """
    acc: [cells, months] k-month accumulations. For each cell and calendar end-month, fits a
    mixed gamma (zero probability + gamma on positives) on the `fit_mask` months only, then
    maps every month to a standard normal quantile.
    """
    spi = np.full_like(acc, np.nan)
    months = np.arange(acc.shape[1]) % 12
    for cal in range(12):
        cols = months == cal
        fit_cols = cols & fit_mask
        x_fit = acc[:, fit_cols]
        pos = np.where(x_fit > 0, x_fit, np.nan)
        n_valid = np.sum(~np.isnan(x_fit), axis=1)
        q0 = np.where(n_valid > 0, np.sum(x_fit == 0, axis=1) / np.maximum(n_valid, 1), np.nan)
        mean = np.nanmean(pos, axis=1)
        A = np.log(mean) - np.nanmean(np.log(pos), axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            alpha = (1 + np.sqrt(1 + 4 * A / 3)) / (4 * A)
            beta = mean / alpha
        enough = (np.sum(~np.isnan(pos), axis=1) >= 10) & np.isfinite(alpha) & (alpha > 0)
        x = acc[:, cols]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # degenerate cells are masked below
            g = stats.gamma.cdf(np.where(x > 0, x, 0.0), a=alpha[:, None], scale=beta[:, None])
        p = q0[:, None] + (1 - q0[:, None]) * g
        p = np.clip(p, 1e-6, 1 - 1e-6)
        z = stats.norm.ppf(p)
        z[~enough] = np.nan
        z[np.isnan(x)] = np.nan
        spi[:, cols] = np.clip(z, -3.5, 3.5)
    return spi


# ── Feature assembly ────────────────────────────────────────────────────────

def compute_origin_features(
    keys: pd.DataFrame,
    well_row: pd.Series,
    rain: np.ndarray,
    tmean: np.ndarray | None,
    well_row_t: pd.Series | None,
    indices: pd.DataFrame | None,
) -> pd.DataFrame:
    """
    keys: rows of (well_id, campaign_idx). well_row maps well → row in `rain` [cells, months].
    Returns one feature row per key. Pure function of its inputs (unit-tested for leakage).
    """
    out = keys[["well_id", "campaign_idx"]].copy().reset_index(drop=True)
    rows = well_row.reindex(out["well_id"]).to_numpy()
    has = ~np.isnan(rows.astype(float))
    rows = np.where(has, rows, 0).astype(np.int64)
    t0 = campaign_month_index(out["campaign_idx"].to_numpy())  # first month NOT available at origin
    cs = nan_cumsum(rain)
    months = np.arange(rain.shape[1])
    fit_mask = (FORCING_FIRST_YEAR + months // 12) <= SPI_FIT_END_YEAR

    def _mask(v):
        v = np.asarray(v, dtype=float)
        v[~has] = np.nan
        return v

    # Rain since the previous campaign: from the previous campaign month up to the origin month
    season = out["campaign_idx"].to_numpy() % 4
    gap = np.select([season == 0, season == 1, season == 2, season == 3], [2, 4, 3, 3])
    out["rain_since_prev"] = _mask(window_sum(cs, rows, t0, gap))
    for k in RAIN_WINDOWS:
        out[f"rain_{k}m"] = _mask(window_sum(cs, rows, t0, k))

    # Monthly climatology (≤ SPI_FIT_END_YEAR) for normalising windows
    clim_month = np.stack([np.nanmean(rain[:, (months % 12 == c) & fit_mask], axis=1) for c in range(12)], axis=1)

    # Last completed JJAS monsoon (June–September ends before the November campaign)
    year = out["campaign_idx"].to_numpy() // 4
    jjas_year = np.where(season == 3, year, year - 1)
    jjas_end = (jjas_year - FORCING_FIRST_YEAR) * 12 + 9  # exclusive end = October index
    jjas = window_sum(cs, rows, jjas_end, 4)
    jjas_norm = clim_month[rows, 5:9].sum(axis=1)
    out["jjas_last_mm"] = _mask(jjas)
    with np.errstate(divide="ignore", invalid="ignore"):
        out["jjas_last_ratio"] = _mask(jjas / jjas_norm)

    # SPI at the month before the origin
    for k in SPI_SCALES:
        # k-month accumulation ending at (and including) month t = window [t − k + 1, t + 1)
        acc = np.full_like(rain, np.nan)
        acc[:, k - 1:] = cs[0][:, k:] - cs[0][:, : rain.shape[1] + 1 - k]
        acc[:, k - 1:][(cs[1][:, k:] - cs[1][:, : rain.shape[1] + 1 - k]) > 0] = np.nan
        spi = spi_from_accumulations(acc, fit_mask)
        idx = t0 - 1
        ok = (idx >= 0) & (idx < rain.shape[1])
        v = np.full(len(out), np.nan)
        v[ok] = spi[rows[ok], idx[ok]]
        out[f"spi_{k}"] = _mask(v)

    # Temperature anomaly over the last three months
    if tmean is not None and well_row_t is not None:
        rows_t = well_row_t.reindex(out["well_id"]).to_numpy()
        has_t = ~np.isnan(rows_t.astype(float))
        rows_t = np.where(has_t, rows_t, 0).astype(np.int64)
        clim_t = np.stack([np.nanmean(tmean[:, (months % 12 == c) & fit_mask], axis=1) for c in range(12)], axis=1)
        anom = tmean - clim_t[:, months % 12]
        cs_t = nan_cumsum(anom)
        v = window_sum(cs_t, rows_t, t0, 3) / 3
        v[~has_t] = np.nan
        out["tmean_anom_3m"] = v

    # Teleconnections at lags (index month = origin month − 1 − lag)
    if indices is not None:
        idx_month = indices.set_index("month")
        for name in ("nino34", "dmi"):
            series = np.full(rain.shape[1], np.nan)
            for ts, val in idx_month[name].items():
                m = (ts.year - FORCING_FIRST_YEAR) * 12 + ts.month - 1
                if 0 <= m < len(series):
                    series[m] = val
            for lag in INDEX_LAGS_MONTHS:
                pos = t0 - 1 - lag
                ok = (pos >= 0) & (pos < len(series))
                v = np.full(len(out), np.nan)
                v[ok] = series[pos[ok]]
                out[f"{name}_lag{lag}"] = v

    # Oracle arm: rain that falls between the origin and each target campaign (hindsight only)
    for h in HORIZONS:
        t1 = campaign_month_index(out["campaign_idx"].to_numpy() + h)
        rain_h = window_sum(cs, rows, t1, t1 - t0)
        cal = (t0[:, None] + np.arange(12)[None, :]) % 12
        within = np.arange(12)[None, :] < (t1 - t0)[:, None]
        norm_h = np.where(within, clim_month[rows[:, None], cal], 0.0).sum(axis=1)
        out[f"oracle_rain_h{h}"] = _mask(rain_h)
        with np.errstate(divide="ignore", invalid="ignore"):
            out[f"oracle_rain_ratio_h{h}"] = _mask(rain_h / norm_h)
    return out


def snapshot_features(observations: pd.DataFrame, campaigns_grid: pd.DataFrame) -> pd.DataFrame:
    """
    Control arm: the source file's observation-day rainfall, averaged per campaign and summed
    over 2/4/8 campaigns (the construction used by prior work on this file).
    """
    obs = observations.copy()
    month = obs["timestamp"].dt.month
    year = obs["timestamp"].dt.year + (month == 12).astype(int)
    season = month.map({12: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3})
    obs["campaign_idx"] = year * 4 + season
    snap = obs.groupby(["well_id", "campaign_idx"])["rainfall"].mean().rename("snap_rain")
    g = campaigns_grid[["well_id", "campaign_idx"]].merge(snap.reset_index(), how="left")
    g = g.sort_values(["well_id", "campaign_idx"])
    by = g.groupby("well_id")["snap_rain"]
    for k in (2, 4, 8):
        g[f"snap_cum{k}"] = by.transform(lambda s: s.rolling(k, min_periods=1).sum())
    return g


# ── Sanity checks (Phase 1.8) ───────────────────────────────────────────────

# IMD-reported all-India JJAS departures from the long-period average (%), for sign agreement.
IMD_REPORTED_DEPARTURE = {2002: -19, 2004: -13, 2009: -22, 2014: -12, 2015: -14, 2019: 10, 2020: 9, 2022: 6, 2023: -6, 2024: 8}


def all_india_jjas(rain_grid: np.ndarray, grid_lat: np.ndarray) -> pd.Series:
    """Area-weighted (cos latitude) all-India JJAS total per year over cells with data."""
    w = np.cos(np.deg2rad(grid_lat))[:, None] * np.ones(rain_grid.shape[1])[None, :]
    out = {}
    for year in range(FORCING_FIRST_YEAR, FORCING_LAST_YEAR + 1):
        m0 = (year - FORCING_FIRST_YEAR) * 12 + 5
        jjas = rain_grid[:, :, m0:m0 + 4]
        if np.isnan(jjas).all():
            continue
        tot = jjas.sum(axis=2)
        valid = ~np.isnan(tot)
        if valid.sum() < 1000:
            continue
        out[year] = float(np.sum(tot[valid] * w[valid]) / np.sum(w[valid]))
    return pd.Series(out)


def recharge_correlation(campaigns: pd.DataFrame, jjas_by_well_year: pd.DataFrame) -> dict:
    """Per-well correlation between monsoon recharge (May → Nov rise) and the well's JJAS rain."""
    may = campaigns[campaigns["season"] == 1].set_index(["well_id", "year"])["depth_mbgl"]
    nov = campaigns[campaigns["season"] == 3].set_index(["well_id", "year"])["depth_mbgl"]
    rise = (may - nov).dropna().rename("rise").reset_index()
    df = rise.merge(jjas_by_well_year, on=["well_id", "year"]).dropna()
    corrs = df.groupby("well_id").apply(
        lambda g: g["rise"].corr(g["jjas_mm"]) if len(g) >= 8 else np.nan, include_groups=False
    ).dropna()
    pooled = stats.spearmanr(df["rise"], df["jjas_mm"]).statistic
    return {"n_wells": int(len(corrs)), "median_r": float(corrs.median()), "share_positive": float((corrs > 0).mean()),
            "pooled_spearman": float(pooled), "n_pairs": int(len(df))}


def plot_sanity(report: dict, campaigns: pd.DataFrame, feats: pd.DataFrame, path: Path):
    """Figure for Phase 1.8: JJAS departures vs IMD, and monsoon recharge vs JJAS rain."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    chk = report["jjas_departure_check"]
    years = sorted(chk)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    x, w = np.arange(len(years)), 0.38
    ax[0].bar(x - w / 2, [chk[y]["ours_pct"] for y in years], w, label="IMD grid (this study)", color="#2a78d6")
    ax[0].bar(x + w / 2, [chk[y]["imd_pct"] for y in years], w, label="IMD reported", color="#eb6834")
    ax[0].axhline(0, color="#333", lw=0.8)
    ax[0].set_xticks(x, years, rotation=45)
    ax[0].set_ylabel("JJAS departure (%)")
    ax[0].legend(frameon=False)
    ax[0].set_title("All-India monsoon departures")

    may = campaigns[campaigns["season"] == 1].set_index(["well_id", "year"])["depth_mbgl"]
    nov = campaigns[campaigns["season"] == 3].set_index(["well_id", "year"])["depth_mbgl"]
    rise = (may - nov).dropna().rename("rise").reset_index()
    jj = feats[feats["campaign_idx"] % 4 == 3][["well_id", "campaign_idx", "jjas_last_ratio"]].copy()
    jj["year"] = jj["campaign_idx"] // 4
    d = rise.merge(jj, on=["well_id", "year"]).dropna()
    d = d[(d["rise"].abs() < 20) & (d["jjas_last_ratio"] < 3)]
    ax[1].hexbin(d["jjas_last_ratio"], d["rise"], gridsize=45, cmap="Blues", mincnt=1, bins="log")
    med = d.groupby(pd.cut(d["jjas_last_ratio"], np.arange(0.2, 2.01, 0.1)), observed=True)["rise"].median()
    ax[1].plot([i.mid for i in med.index], med.values, color="#eb6834", lw=2, label="median rise")
    ax[1].axhline(0, color="#333", lw=0.8)
    ax[1].set_xlabel("JJAS rain at the well (ratio to normal)")
    ax[1].set_ylabel("Water-table rise May→Nov (m)")
    ax[1].legend(frameon=False)
    ax[1].set_title("Monsoon recharge responds to rainfall")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return {str(i.mid.round(2)): round(float(v), 2) for i, v in med.items()}


def save_monthly_table(rain: np.ndarray, used: np.ndarray, glat: np.ndarray, glon: np.ndarray, catalog: pd.DataFrame):
    """Step 1.4 deliverable: one row per (IMD cell used by a well, month) and the well → cell map."""
    n_lon = len(glon)
    months = pd.date_range(f"{FORCING_FIRST_YEAR}-01-01", periods=rain.shape[1], freq="MS")
    table = pd.DataFrame({
        "cell": np.repeat(used, len(months)),
        "lat": np.repeat(glat[used // n_lon], len(months)),
        "lon": np.repeat(glon[used % n_lon], len(months)),
        "month": np.tile(months, len(used)),
        "rain_mm": rain.reshape(-1),
    })
    table.to_parquet(DATA_PROCESSED_DIR / "forcing_monthly.parquet", index=False)
    catalog[["well_id", "rain_cell"]].rename(columns={"rain_cell": "cell"}).to_parquet(
        DATA_PROCESSED_DIR / "well_rain_cells.parquet", index=False)


# ── Driver ──────────────────────────────────────────────────────────────────

def run_forcing_features():
    print("=== Phase 1: Forcing Features ===")
    catalog = pd.read_parquet(DATA_PROCESSED_DIR / "station_catalog.parquet")
    campaigns = pd.read_parquet(DATA_PROCESSED_DIR / "gwl_campaigns.parquet")
    observations = pd.read_parquet(DATA_PROCESSED_DIR / "gwl_observations_clean.parquet")

    print("Loading IMD rainfall (monthly totals) ...")
    rain_grid, glat, glon, rain_years = load_imd_monthly("rain", "sum")
    rain_grid, n_repaired, n_masked = repair_zero_artefacts(rain_grid)
    print(f"  years {rain_years[0]}–{rain_years[-1]} ({len(rain_years)}), grid {rain_grid.shape[:2]}; "
          f"zero-rain cell-years: {n_repaired} repaired from neighbours, {n_masked} set to missing")
    valid = ~np.isnan(np.nanmean(rain_grid, axis=2))
    cells = nearest_valid_cells(catalog["latitude"].to_numpy(), catalog["longitude"].to_numpy(), glat, glon, valid)
    catalog["rain_cell"] = cells
    used = np.unique(cells[cells >= 0])
    cell_pos = {c: i for i, c in enumerate(used)}
    rain = rain_grid.reshape(-1, N_MONTHS)[used]  # [used cells, months]
    well_row = catalog.set_index("well_id")["rain_cell"].map(cell_pos).astype(float)
    print(f"  {len(used)} distinct rain cells for {int((cells >= 0).sum())}/{len(cells)} wells")
    save_monthly_table(rain, used, glat, glon, catalog)

    tmean, well_row_t = None, None
    try:
        tmax, tlat, tlon, _ = load_imd_monthly("tmax", "mean")
        tmin, _, _, _ = load_imd_monthly("tmin", "mean")
        tgrid = (tmax + tmin) / 2
        tvalid = ~np.isnan(np.nanmean(tgrid, axis=2))
        tcells = nearest_valid_cells(catalog["latitude"].to_numpy(), catalog["longitude"].to_numpy(), tlat, tlon, tvalid)
        tused = np.unique(tcells[tcells >= 0])
        tpos = {c: i for i, c in enumerate(tused)}
        tmean = tgrid.reshape(-1, N_MONTHS)[tused]
        well_row_t = pd.Series(tcells, index=catalog["well_id"]).map(tpos).astype(float)
        print(f"  temperature: {len(tused)} distinct 1° cells")
    except FileNotFoundError as exc:
        print(f"  temperature skipped: {exc}")

    indices_path = EXTERNAL_DIR / "climate_indices.parquet"
    indices = pd.read_parquet(indices_path) if indices_path.exists() else None

    span = campaigns.groupby("well_id")["campaign_idx"].agg(["min", "max"])
    keys = pd.DataFrame({
        "well_id": np.repeat(span.index.values, (span["max"] - span["min"] + 1).values),
        "campaign_idx": np.concatenate([np.arange(a, b + 1) for a, b in zip(span["min"], span["max"])]),
    })
    feats = compute_origin_features(keys, well_row, rain, tmean, well_row_t, indices)
    snap = snapshot_features(observations, keys)
    feats = feats.merge(snap.drop(columns=["snap_rain"]), on=["well_id", "campaign_idx"], how="left")
    feats.to_parquet(DATA_PROCESSED_DIR / "forcing_features.parquet", index=False)
    print(f"Saved forcing_features.parquet: {feats.shape[0]:,} rows × {feats.shape[1]} columns")

    # ── Sanity checks ──
    FORCING_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = {"zero_rain_cell_years_repaired": n_repaired, "zero_rain_cell_years_masked": n_masked}
    observed = keys.merge(campaigns[["well_id", "campaign_idx"]], how="inner")
    obs_feats = feats.merge(observed, how="inner")
    in_range = obs_feats["campaign_idx"] // 4 <= max(rain_years)
    cov = obs_feats.loc[in_range, "rain_12m"].notna().mean()
    report["coverage_rain_12m_observed_campaigns"] = float(cov)

    jjas = all_india_jjas(rain_grid, glat)
    base = jjas.loc[(jjas.index >= 1994) & (jjas.index <= 2023)].mean()
    departures = ((jjas / base - 1) * 100).round(1)
    agree = {y: {"ours_pct": float(departures.get(y, np.nan)), "imd_pct": d,
                 "same_sign": bool(np.sign(departures.get(y, np.nan)) == np.sign(d))}
             for y, d in IMD_REPORTED_DEPARTURE.items() if y in departures.index}
    report["all_india_jjas_mm"] = {int(k): round(v, 1) for k, v in jjas.items()}
    report["jjas_departure_check"] = agree
    report["jjas_sign_agreement"] = float(np.mean([a["same_sign"] for a in agree.values()])) if agree else None

    jj = feats[["well_id", "campaign_idx", "jjas_last_mm"]].copy()
    jj = jj[jj["campaign_idx"] % 4 == 3]  # November origin → that year's JJAS
    jj["year"] = jj["campaign_idx"] // 4
    report["recharge_vs_jjas"] = recharge_correlation(campaigns, jj.rename(columns={"jjas_last_mm": "jjas_mm"})[["well_id", "year", "jjas_mm"]])

    snap_vs_true = feats[["snap_cum4", "rain_12m"]].dropna()
    report["snapshot_vs_imd_12m"] = {
        "spearman": float(stats.spearmanr(snap_vs_true["snap_cum4"], snap_vs_true["rain_12m"]).statistic),
        "median_snap_cum4_mm": float(snap_vs_true["snap_cum4"].median()),
        "median_imd_rain_12m_mm": float(snap_vs_true["rain_12m"].median()),
    }
    report["unmapped_manual_wells"] = sorted(
        set(catalog.loc[(catalog["network"] == "manual") & (catalog["rain_cell"] < 0), "well_id"]))
    report["median_rise_by_jjas_ratio"] = plot_sanity(report, campaigns, feats, FORCING_REPORTS_DIR / "sanity_checks.png")
    with open(FORCING_REPORTS_DIR / "sanity.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"Coverage (rain_12m on observed campaigns ≤ {max(rain_years)}): {cov:.1%}")
    print(f"JJAS sign agreement with IMD-reported departures: {report['jjas_sign_agreement']:.0%}")
    for y, a in agree.items():
        print(f"  {y}: ours {a['ours_pct']:+.1f}%  IMD {a['imd_pct']:+d}%")
    print(f"Recharge vs JJAS: {report['recharge_vs_jjas']}")
    print(f"Snapshot vs IMD: {report['snapshot_vs_imd_12m']}")
    print(f"Saved {FORCING_REPORTS_DIR / 'sanity.json'}")


if __name__ == "__main__":
    run_forcing_features()
