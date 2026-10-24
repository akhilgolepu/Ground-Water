"""Tests for src/research/regions.py and the Phase 2 statistics."""

import numpy as np
import pandas as pd
import pytest

from src.research.regions import assign_region
from src.research.skill_decomposition import (
    ARMS,
    FEATURE_GROUPS,
    campaign_sign_test,
    cluster_bootstrap,
    mae_bootstrap,
    panel_dm,
)


def test_assign_region_reference_points():
    places = {  # (lat, lon) → expected region
        (30.9, 75.85): "Indo-Gangetic plain",  # Ludhiana
        (25.6, 85.1): "Indo-Gangetic plain",  # Patna
        (26.9, 70.9): "Arid north-west",  # Jaisalmer
        (23.25, 69.67): "Arid north-west",  # Bhuj
        (26.14, 91.74): "Himalaya & north-east",  # Guwahati
        (34.08, 74.8): "Himalaya & north-east",  # Srinagar
        (17.38, 78.48): "Peninsular",  # Hyderabad
        (12.97, 77.59): "Peninsular",  # Bengaluru
    }
    lat = pd.Series([p[0] for p in places])
    lon = pd.Series([p[1] for p in places])
    assert list(assign_region(lat, lon)) == list(places.values())


def test_arms_are_nested_and_grouped():
    m0, m1, m2, m3 = (set(ARMS[k]) for k in ["M0 memory", "M1 + past forcing", "M2 + ENSO/IOD", "M3 + oracle rain"])
    assert m0 < m1 < m2 < m3
    grouped = {c for cols in FEATURE_GROUPS.values() for c in cols}
    assert set().union(*map(set, ARMS.values())) <= grouped


def _panel(n_wells=40, n_t=24, noise_b=1.0, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for w in range(n_wells):
        for t in range(n_t):
            y = rng.normal()
            rows.append({"well_id": f"w{w}", "target_idx": t, "y_target": y, "persistence": y + rng.normal(0, 2),
                         "a": y + rng.normal(0, 1.0), "b": y + rng.normal(0, noise_b)})
    return pd.DataFrame(rows)


def test_panel_dm_detects_a_better_model_and_not_a_tie():
    better = panel_dm(_panel(noise_b=0.5), "a", "b")
    assert better["mean_diff"] > 0 and better["p_value"] < 0.01
    tie = panel_dm(_panel(noise_b=1.0, seed=3), "a", "b")
    assert tie["p_value"] > 0.01


def test_cluster_bootstrap_brackets_the_point_estimate():
    df = _panel()
    boot = cluster_bootstrap(df, ["a"], n_boot=300)
    skill = 1 - boot["a"] / boot["persistence"]
    point = 1 - np.mean((df["a"] - df["y_target"]) ** 2) / np.mean((df["persistence"] - df["y_target"]) ** 2)
    assert np.percentile(skill, 2.5) < point < np.percentile(skill, 97.5)
    assert point == pytest.approx(0.75, abs=0.1)


def test_absolute_loss_dm_is_robust_to_one_wild_reading():
    df = _panel(noise_b=0.6, seed=5)
    df.loc[0, "b"] = df.loc[0, "y_target"] + 50.0  # one datum jump (data have 60 m jumps) the better model misses
    assert panel_dm(df, "a", "b", "squared")["p_value"] > 0.05
    assert panel_dm(df, "a", "b", "absolute")["p_value"] < 0.01


def test_sign_test_and_mae_bootstrap():
    df = _panel(noise_b=0.5)
    st = campaign_sign_test(df, "a", "b")
    assert st["campaigns_b_better"] == st["campaigns"] == 24 and st["sign_p_value"] < 1e-5
    lo, hi = mae_bootstrap(df, "a", "b", n_boot=200)
    assert 0 < lo < hi < 1
