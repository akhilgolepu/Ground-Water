"""Tests for src/research/forcing_features.py — causality of every non-oracle feature."""

import numpy as np
import pandas as pd
import pytest

from src.research.config import FORCING_FIRST_YEAR, HORIZONS
from src.research.forcing_features import (
    N_MONTHS,
    campaign_month_index,
    compute_origin_features,
    nan_cumsum,
    repair_zero_artefacts,
    snapshot_features,
    spi_from_accumulations,
    uses_fitted_normals,
    window_sum,
)

Y0 = FORCING_FIRST_YEAR


def test_campaign_month_index():
    assert campaign_month_index(np.array([Y0 * 4 + 0]))[0] == 0  # January of the first year
    assert campaign_month_index(np.array([Y0 * 4 + 1]))[0] == 4  # May
    assert campaign_month_index(np.array([(Y0 + 1) * 4 + 3]))[0] == 12 + 10  # November next year


def test_window_sum_and_missing_months():
    monthly = np.array([[1.0, 2.0, np.nan, 4.0, 5.0]])
    cums = nan_cumsum(monthly)
    rows = np.array([0, 0, 0])
    got = window_sum(cums, rows, np.array([2, 4, 5]), np.array([2, 2, 2]))
    assert got[0] == 3.0  # months 0–1
    assert np.isnan(got[1])  # window contains the missing month
    assert got[2] == 9.0  # months 3–4 are unaffected by the earlier gap
    assert np.isnan(window_sum(cums, np.array([0]), np.array([1]), np.array([3]))[0])  # before the record


def _synthetic(seed=0):
    rng = np.random.default_rng(seed)
    rain = rng.gamma(2.0, 30.0, size=(1, N_MONTHS))
    tmean = 25 + rng.normal(0, 1, size=(1, N_MONTHS))
    months = pd.date_range(f"{Y0}-01-01", periods=N_MONTHS, freq="MS")
    indices = pd.DataFrame({"month": months, "nino34": rng.normal(size=N_MONTHS), "dmi": rng.normal(size=N_MONTHS)})
    well_row = pd.Series({"w": 0.0})
    return rain, tmean, indices, well_row


@pytest.mark.parametrize("season", [0, 1, 2, 3])
def test_non_oracle_features_ignore_the_future(season):
    rain, tmean, indices, well_row = _synthetic()
    origin = (2010 * 4) + season
    keys = pd.DataFrame({"well_id": ["w"], "campaign_idx": [origin]})
    base = compute_origin_features(keys, well_row, rain, tmean, well_row, indices).iloc[0]

    t0 = campaign_month_index(np.array([origin]))[0]
    rain2, tmean2, indices2 = rain.copy(), tmean.copy(), indices.copy()
    rain2[:, t0:] *= 10  # change the campaign month and everything after it
    tmean2[:, t0:] += 5
    indices2.loc[t0:, ["nino34", "dmi"]] += 3
    pert = compute_origin_features(keys, well_row, rain2, tmean2, well_row, indices2).iloc[0]

    past_cols = [c for c in base.index if c not in ("well_id", "campaign_idx") and not c.startswith("oracle_")]
    # SPI and *_ratio use normals fitted on ≤ SPI_FIT_END_YEAR (like a scaler fitted on training data),
    # so perturbing 2010+ legitimately moves them; they are tested with a post-fit origin below.
    for col in [c for c in past_cols if not uses_fitted_normals(c)]:
        assert base[col] == pytest.approx(pert[col], nan_ok=True), col
    for h in HORIZONS:
        assert pert[f"oracle_rain_h{h}"] == pytest.approx(10 * base[f"oracle_rain_h{h}"])


def test_fitted_normal_features_use_only_the_fit_window_and_the_past():
    rain, tmean, indices, well_row = _synthetic(1)
    origin = 2020 * 4 + 1  # after the SPI fit period, so the fit is untouched by perturbing 2020+
    keys = pd.DataFrame({"well_id": ["w"], "campaign_idx": [origin]})
    base = compute_origin_features(keys, well_row, rain, tmean, well_row, None).iloc[0]
    t0 = campaign_month_index(np.array([origin]))[0]
    rain2, tmean2 = rain.copy(), tmean.copy()
    rain2[:, t0:] *= 10
    tmean2[:, t0:] += 5
    pert = compute_origin_features(keys, well_row, rain2, tmean2, well_row, None).iloc[0]
    normal_cols = [c for c in base.index if uses_fitted_normals(c) and not c.startswith("oracle_")]
    assert set(normal_cols) == {"spi_3", "spi_6", "spi_12", "jjas_last_ratio", "tmean_anom_3m"}
    for col in normal_cols:
        assert base[col] == pytest.approx(pert[col]), col


def test_rain_windows_and_monsoon_timing():
    rain = np.zeros((1, N_MONTHS))
    for year in range(Y0, Y0 + N_MONTHS // 12):
        m = (year - Y0) * 12
        rain[0, m:m + 12] = np.arange(1, 13)  # January = 1 mm … December = 12 mm
    well_row = pd.Series({"w": 0.0})
    keys = pd.DataFrame({"well_id": ["w"] * 3, "campaign_idx": [2005 * 4 + 1, 2005 * 4 + 2, 2005 * 4 + 3]})
    f = compute_origin_features(keys, well_row, rain, None, None, None).set_index("campaign_idx")
    may, aug, nov = 2005 * 4 + 1, 2005 * 4 + 2, 2005 * 4 + 3
    assert f.loc[may, "rain_since_prev"] == 1 + 2 + 3 + 4  # Jan–Apr
    assert f.loc[aug, "rain_since_prev"] == 5 + 6 + 7  # May–Jul
    assert f.loc[may, "rain_3m"] == 2 + 3 + 4  # Feb–Apr
    jjas = 6 + 7 + 8 + 9
    assert f.loc[nov, "jjas_last_mm"] == jjas  # this year's monsoon is complete by November
    assert f.loc[aug, "jjas_last_mm"] == jjas  # in August, last year's (identical here)
    assert f.loc[nov, "oracle_rain_h1"] == 11 + 12  # Nov–Dec until the January campaign


def test_spi_is_standardised_on_fit_period():
    rng = np.random.default_rng(3)
    acc = rng.gamma(3.0, 50.0, size=(4, 360))
    fit = np.arange(360) < 240
    spi = spi_from_accumulations(acc, fit)
    assert abs(np.nanmean(spi[:, fit])) < 0.1
    assert abs(np.nanstd(spi[:, fit]) - 1) < 0.1


def test_snapshot_features_rolling_sums():
    obs = pd.DataFrame({
        "well_id": "w",
        "timestamp": pd.to_datetime(["2010-01-10", "2010-05-10", "2010-08-10", "2010-11-10"]),
        "rainfall": [1.0, 2.0, 4.0, 8.0],
    })
    keys = pd.DataFrame({"well_id": "w", "campaign_idx": [2010 * 4 + s for s in range(4)]})
    snap = snapshot_features(obs, keys).set_index("campaign_idx")
    assert snap.loc[2010 * 4 + 3, "snap_cum2"] == 12.0
    assert snap.loc[2010 * 4 + 3, "snap_cum4"] == 15.0


def test_repair_zero_artefacts_fills_isolated_dry_cell_years():
    grid = np.full((3, 3, 24), 50.0)  # 600 mm/yr everywhere, two years
    grid[1, 1, 12:24] = 0.0  # centre cell reads 0 mm for the whole second year
    grid[0, 0, :] = np.nan  # sea cell stays missing
    fixed, n, n_masked = repair_zero_artefacts(grid)
    assert (n, n_masked) == (1, 0)
    assert np.allclose(fixed[1, 1, 12:24], 50.0)
    assert np.allclose(fixed[1, 1, :12], 50.0)  # untouched first year
    assert np.isnan(fixed[0, 0, :]).all()

    block = np.zeros((3, 3, 12))  # a block of zero cells cannot be repaired from neighbours → missing
    fixed, n, n_masked = repair_zero_artefacts(block)
    assert (n, n_masked) == (0, 9)
    assert np.isnan(fixed).all()
