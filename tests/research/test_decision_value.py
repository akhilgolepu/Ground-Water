"""Tests for src/research/decision_value.py (Phase 4)."""

import re

import numpy as np
import pandas as pd
import pytest

from src.research.decision_value import (
    advisory,
    contingency,
    online_exceedance,
    plotting_position_quantile,
    relative_value,
)


def test_relative_value_reference_cases():
    # 100 cases, base rate s = 0.2
    assert relative_value(20, 0, 0, 80, 0.3) == pytest.approx(1.0)  # perfect forecast
    assert relative_value(20, 80, 0, 0, 0.1) == pytest.approx(0.0)  # always act, α < s: same as climatology
    assert relative_value(0, 0, 20, 80, 0.5) == pytest.approx(0.0)  # never act, α > s: same as climatology
    assert relative_value(0, 80, 20, 0, 0.3) < 0  # warns only on the wrong cases
    # vectorised over α
    v = relative_value(15, 10, 5, 70, np.array([0.1, 0.2, 0.4]))
    assert v.shape == (3,) and np.all(v < 1)


def test_contingency_counts():
    p = np.array([0.9, 0.6, 0.2, 0.1])
    o = np.array([True, False, True, False])
    assert contingency(p, o, 0.5) == (1, 1, 1, 1)


def test_plotting_position_quantile():
    x = np.arange(1, 20, dtype=float)  # positions i/20
    assert plotting_position_quantile(x, 0.5) == pytest.approx(10.0)
    assert np.isnan(plotting_position_quantile(x[:3], 0.8413))  # beyond the largest position


def test_online_exceedance_uses_only_observed_residuals():
    h = 1
    cal = pd.DataFrame({"depth_name": "a", "region": "r", "score": np.tile([-1.0, 1.0], 50)})
    test = pd.DataFrame({"depth_name": "a", "region": "r", "target_idx": np.repeat(np.arange(6), 10),
                         "yhat": 0.0, "score": 0.0})
    test.loc[test["target_idx"] == 2, "score"] = 50.0  # extreme outcomes at T = 2
    p = online_exceedance(cal, test, h, np.full(len(test), 5.0))
    t = test["target_idx"].to_numpy()
    assert np.all(p[t <= 2] == 0)  # nothing above 5 m was observable yet
    assert np.all(p[t >= 3] > 0)  # after T = 2 is observed, the pool contains it


def test_advisory_numbers_match_the_record():
    text = advisory("W1", 2023 * 4 + 3, 12.345, 10.9, 14.12, 0.637, 13.0, 0.3)
    assert "November (post-monsoon) 2023" in text
    nums = re.findall(r"\d+\.\d|\d+%", text)
    assert nums == ["12.3", "80%", "10.9", "14.1", "13.0", "64%"]  # "80%" is the range label
    assert text.endswith("plan for a deeper-than-usual water level.")
    assert "No warning" in advisory("W1", 2023 * 4, 5.0, 4.0, 6.0, 0.1, 7.0, 0.3)


def test_rolling_isotonic_ignores_unobserved_outcomes():
    from src.research.decision_value import rolling_isotonic

    cal = pd.DataFrame({"target_idx": np.repeat([0, 1, 2], 50), "p": np.tile(np.linspace(0, 1, 50), 3)})
    cal["o"] = cal["p"] > 0.5
    test = pd.DataFrame({"target_idx": np.repeat([3, 4, 5], 50), "p": np.tile(np.linspace(0, 1, 50), 3)})
    test["o"] = test["target_idx"] >= 4  # regime change at T = 4: everything becomes an event
    out = rolling_isotonic(cal, test, h=1)
    t = test["target_idx"].to_numpy()
    assert np.all(out[(t == 3) & (test["p"] < 0.4).to_numpy()] == 0)  # learned only from calibration
    assert np.all(out[(t == 4) & (test["p"] < 0.4).to_numpy()] == 0)  # T = 4 outcomes not yet observed
    assert out[(t == 5)].min() > 0  # after T = 4 is observed, low probabilities are revised upward
