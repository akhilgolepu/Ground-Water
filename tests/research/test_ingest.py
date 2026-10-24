"""Tests for src/research/ingest.py — the steps the legacy pipeline got wrong."""

import numpy as np
import pandas as pd

from src.research.ingest import build_campaign_series, classify_networks, harmonise_depth, remove_outliers


def _obs(well_id, dates, values):
    return pd.DataFrame({"well_id": well_id, "timestamp": pd.to_datetime(dates), "water_level_raw": values})


def test_harmonise_depth_flips_negative_stations_only():
    df = pd.concat([
        _obs("dwlr", ["2023-01-01", "2023-01-02", "2023-01-03"], [-10.0, -10.5, 0.2]),
        _obs("manual", ["2010-01-15", "2010-05-15"], [5.0, 7.0]),
    ])
    out = harmonise_depth(df).set_index(["well_id", "timestamp"])["depth_mbgl"]
    assert list(out.loc["dwlr"]) == [10.0, 10.5, -0.2]  # majority negative → flip all, incl. artesian reading
    assert list(out.loc["manual"]) == [5.0, 7.0]


def test_classify_networks_by_sampling_interval():
    daily = _obs("d", pd.date_range("2023-01-01", periods=30, freq="D"), 1.0)
    quarterly = _obs("q", ["2010-01-15", "2010-05-15", "2010-08-15", "2010-11-15"], 1.0)
    single = _obs("s", ["2010-01-15"], 1.0)
    nets = classify_networks(pd.concat([daily, quarterly, single]))
    assert nets["d"] == "DWLR"
    assert nets["q"] == "manual"
    assert nets["s"] == "manual"


def test_remove_outliers_drops_range_and_mad_violations():
    values = [5.0, 5.2, 4.9, 5.1, 5.0, 60.0, 300.0]
    df = _obs("w", pd.date_range("2000-01-01", periods=len(values), freq="90D"), values)
    df["depth_mbgl"] = df["water_level_raw"]
    kept, qc = remove_outliers(df)
    assert qc["dropped_range"] == 1  # 300 m
    assert qc["dropped_mad"] == 1  # 60 m in a ~5 m well
    assert sorted(kept["depth_mbgl"]) == [4.9, 5.0, 5.0, 5.1, 5.2]


def test_campaign_mapping_december_counts_toward_next_january():
    df = _obs("w", ["2010-12-20", "2011-01-10", "2011-04-28", "2011-11-02"], [6.0, 8.0, 9.0, 4.0])
    df["depth_mbgl"] = df["water_level_raw"]
    camp = build_campaign_series(df).set_index("campaign_idx")
    jan_2011 = 2011 * 4 + 0
    assert camp.loc[jan_2011, "depth_mbgl"] == 7.0  # Dec 2010 and Jan 2011 averaged
    assert camp.loc[jan_2011, "n_raw"] == 2
    assert camp.loc[2011 * 4 + 1, "season"] == 1  # April → May (pre-monsoon)
    assert camp.loc[2011 * 4 + 3, "season"] == 3  # November → post-monsoon
    assert np.isclose(camp["depth_mbgl"].sum(), 7.0 + 9.0 + 4.0)
