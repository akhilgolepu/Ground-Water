"""Tests for src/research/benchmark.py — leakage, split boundaries and statistics."""

import numpy as np
import pandas as pd
import pytest

from src.research.benchmark import (
    FEATURE_COLS,
    add_expanding_climatology,
    assign_split,
    build_supervised,
    complete_grid,
    conformal_quantile,
    depth_class,
    sen_mann_kendall,
)
from src.research.config import CAL_END_YEAR, TRAIN_END_YEAR


def _campaigns(values, start_idx=2000 * 4, well_id="w1"):
    idx = [start_idx + i for i, v in enumerate(values) if v is not None]
    vals = [v for v in values if v is not None]
    return pd.DataFrame({"well_id": well_id, "campaign_idx": idx, "depth_mbgl": vals,
                         "year": [i // 4 for i in idx], "season": [i % 4 for i in idx]})


CATALOG = pd.DataFrame({"well_id": ["w1"], "latitude": [20.0], "longitude": [78.0], "well_depth_m": [50.0]})


def test_complete_grid_inserts_missing_campaigns():
    grid = complete_grid(_campaigns([1.0, None, 3.0]))
    assert len(grid) == 3
    assert np.isnan(grid["depth_mbgl"].iloc[1])
    assert list(grid["season"]) == [0, 1, 2]


def test_expanding_climatology_has_no_look_ahead():
    values = [float(v) for v in range(1, 17)]  # 4 years
    base = add_expanding_climatology(complete_grid(_campaigns(values)))
    changed_vals = values.copy()
    changed_vals[-1] = 999.0  # change only the last campaign
    changed = add_expanding_climatology(complete_grid(_campaigns(changed_vals)))
    cols = [f"clim_s{s}" for s in range(4)]
    pd.testing.assert_frame_equal(base[cols].iloc[:-1], changed[cols].iloc[:-1])
    # season-0 climatology at the 3rd January (row 8) = mean of Jan values 1, 5, 9
    assert base.loc[8, "clim_s0"] == pytest.approx((1 + 5 + 9) / 3)
    # fewer than two values for a season → undefined
    assert np.isnan(base.loc[0, "clim_s0"])


@pytest.mark.parametrize("h", [1, 2, 4])
def test_supervised_features_do_not_see_the_target(h):
    values = [10.0 + 0.1 * i for i in range(24)]
    origin = 12
    base = build_supervised(add_expanding_climatology(complete_grid(_campaigns(values))), CATALOG, h)
    perturbed_vals = values.copy()
    for k in range(origin + 1, len(values)):
        perturbed_vals[k] = 500.0  # everything after the origin changes
    pert = build_supervised(add_expanding_climatology(complete_grid(_campaigns(perturbed_vals))), CATALOG, h)

    row_b = base[base["campaign_idx"] == 2000 * 4 + origin].iloc[0]
    row_p = pert[pert["campaign_idx"] == 2000 * 4 + origin].iloc[0]
    for col in FEATURE_COLS + ["seasonal_naive"]:
        a, b = row_b[col], row_p[col]
        assert (pd.isna(a) and pd.isna(b)) or a == pytest.approx(b), col
    assert row_b["y_target"] == pytest.approx(values[origin + h])
    assert row_p["y_target"] == 500.0


def test_supervised_lags_and_seasonal_naive():
    values = [float(i) for i in range(12)]
    df = build_supervised(add_expanding_climatology(complete_grid(_campaigns(values))), CATALOG, 1)
    row = df[df["campaign_idx"] == 2000 * 4 + 8].iloc[0]
    assert row["y_t"] == 8.0
    assert row["y_lag1"] == 7.0 and row["y_lag4"] == 4.0
    assert row["seasonal_naive"] == 5.0  # target 9 → same season one year earlier = index 5
    assert row["target_season"] == (8 + 1) % 4


def test_split_boundaries_follow_target_year():
    df = pd.DataFrame({"target_year": [TRAIN_END_YEAR, TRAIN_END_YEAR + 1, CAL_END_YEAR, CAL_END_YEAR + 1]})
    assert list(assign_split(df)) == ["train", "cal", "cal", "test"]


def test_conformal_quantile_finite_sample():
    scores = np.arange(1, 10, dtype=float)  # n = 9
    assert conformal_quantile(scores, 0.8) == 8.0  # ceil(10 × 0.8) / 9 → 8th smallest
    assert conformal_quantile(scores, 0.95) == 9.0


def test_depth_class_edges():
    assert list(depth_class(pd.Series([0.0, 4.99, 5.0, 14.99, 15.0, 40.0]))) == [0, 0, 1, 1, 2, 3]


def test_sen_mann_kendall():
    years = np.arange(2000, 2015, dtype=float)
    slope, p = sen_mann_kendall(years, 0.5 * years + 3)
    assert slope == pytest.approx(0.5) and p < 0.001
    slope, p = sen_mann_kendall(years, np.full_like(years, 7.0))
    assert slope == 0.0 and p == pytest.approx(1.0)
