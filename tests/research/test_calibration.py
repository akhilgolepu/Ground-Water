"""Tests for src/research/calibration.py (Phase 3)."""

import numpy as np
import pandas as pd
import pytest

from src.research.calibration import (
    aci_update,
    crps_from_quantiles,
    hierarchical_pools,
    holm,
    lookup,
    online_mondrian,
    signed_offsets,
    winkler,
)


def test_signed_offsets_finite_sample_ranks():
    r = np.arange(1, 20, dtype=float)  # n = 19
    lo, hi = signed_offsets(r, 0.2)  # ranks ⌊20·0.1⌋ = 2 and ⌈20·0.9⌉ = 18
    assert (lo, hi) == (2.0, 18.0)
    lo, hi = signed_offsets(r[:5], 0.05)  # too few residuals for 95 % → infinite
    assert lo == -np.inf and hi == np.inf


def test_signed_offsets_achieve_coverage_on_exchangeable_data():
    rng = np.random.default_rng(0)
    hits = []
    for _ in range(400):
        x = rng.standard_t(3, size=101)
        lo, hi = signed_offsets(x[:100], 0.2)
        hits.append(lo <= x[100] <= hi)
    assert 0.76 <= np.mean(hits) <= 0.88


def test_hierarchical_pools_fall_back_to_parent():
    pool = pd.DataFrame({"a": ["x"] * 60 + ["y"] * 10, "b": ["p"] * 30 + ["q"] * 30 + ["p"] * 10, "score": np.arange(70.0)})
    pools = hierarchical_pools(pool, ["a", "b"], min_cell=20)
    assert len(lookup(pools, ("x", "p"))) == 30  # own cell
    assert len(lookup(pools, ("y", "p"))) == 70  # y has 10 rows → global pool
    assert len(lookup(pools, ("x", "r"))) == 60  # unseen sub-cell → parent "x"


def test_aci_moves_alpha_against_miscoverage():
    assert aci_update(0.2, 0.2, 0.5, 0.05) < 0.2  # under-covering → smaller α → wider intervals
    assert aci_update(0.2, 0.2, 0.0, 0.05) > 0.2
    assert aci_update(0.001, 0.2, 1.0, 0.5) == pytest.approx(1e-4)


def test_online_mondrian_never_uses_unobserved_residuals():
    """A huge residual at target T must not widen any interval issued for targets < T + h."""
    h = 2
    cal = pd.DataFrame({"c": "k", "score": np.tile([-1.0, 1.0], 50)})
    test = pd.DataFrame({"c": "k", "target_idx": np.repeat(np.arange(10), 20), "yhat": 0.0})
    test["y_target"] = 0.0
    test["score"] = 0.0
    test.loc[test["target_idx"] == 3, ["score", "y_target"]] = 1000.0
    lo, hi = online_mondrian(cal, test, ["c"], 0.2, h)
    early = test["target_idx"].to_numpy() < 3 + h
    assert np.all(hi[early] <= 1.0)
    assert np.all(np.isfinite(hi))


def test_winkler_and_crps():
    assert winkler(np.array([0.0]), np.array([-1.0]), np.array([1.0]), 0.2)[0] == 2.0
    assert winkler(np.array([2.0]), np.array([-1.0]), np.array([1.0]), 0.2)[0] == pytest.approx(2.0 + 10.0)
    taus = np.array([0.25, 0.5, 0.75])
    perfect = crps_from_quantiles(np.array([0.0]), np.zeros((1, 3)), taus)
    worse = crps_from_quantiles(np.array([0.0]), np.ones((1, 3)), taus)
    assert perfect[0] == 0 and worse[0] > 0


def test_holm_adjustment():
    adj = holm(pd.Series({"a": 0.01, "b": 0.04, "c": 0.03}))
    assert adj["a"] == pytest.approx(0.03) and adj["c"] == pytest.approx(0.06) and adj["b"] == pytest.approx(0.06)


def test_online_mondrian_scales_offsets_by_sigma():
    cal = pd.DataFrame({"c": "k", "score": np.tile([-1.0, 1.0], 50)})
    test = pd.DataFrame({"c": "k", "target_idx": np.repeat(np.arange(4), 10), "yhat": 0.0, "y_target": 0.0, "score": 0.0})
    sig = np.where(np.arange(40) % 2 == 0, 1.0, 3.0)
    lo, hi = online_mondrian(cal, test, ["c"], 0.2, 1, scale_cal=np.ones(100), scale_test=sig)
    assert np.allclose(hi, sig) and np.allclose(lo, -sig)
