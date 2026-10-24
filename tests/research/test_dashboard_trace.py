"""
Phase 5 exit check: every number the dashboard shows is traceable to a file in reports/.
Compares frontend/public/data/*.json (written by src.research.export_dashboard) with the report files.
Skipped when the dashboard data or reports have not been generated.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "frontend" / "public" / "data"
REPORTS = ROOT / "reports"

needs = pytest.mark.skipif(not (DATA / "skill.json").exists() or not (REPORTS / "skill" / "bootstrap.json").exists(),
                           reason="run src.research.export_dashboard first")


def load(name):
    return json.loads((DATA / name).read_text())


@needs
def test_skill_matches_bootstrap_report():
    boot = {(b["h"], b["model"]): b for b in json.loads((REPORTS / "skill" / "bootstrap.json").read_text())
            if b["stat"] == "skill_vs_persistence"}
    for row in load("skill.json")["skill"]:
        b = boot[(row["h"], row["arm"])]
        assert row["skill"] == pytest.approx(b["estimate"], abs=6e-4)
        assert row["lo"] == pytest.approx(b["ci"][0], abs=6e-4) and row["hi"] == pytest.approx(b["ci"][1], abs=6e-4)


@needs
def test_gains_match_diebold_mariano_report():
    dm = pd.read_csv(REPORTS / "skill" / "diebold_mariano.csv").set_index(["h", "a", "b"])
    for row in load("skill.json")["gains"]:
        ref = dm.loc[(row["h"], row["a"], row["b"])]
        assert row["mse_reduction"] == pytest.approx(ref["mse_reduction"], abs=6e-5)
        assert row["campaigns_b_better"] == ref["campaigns_b_better"]


@needs
def test_coverage_matches_calibration_report():
    cov = pd.read_csv(REPORTS / "calibration" / "coverage.csv").set_index(["h", "method", "nominal", "group_var", "group"])
    for row in load("calibration.json")["coverage"]:
        ref = cov.loc[(row["h"], row["method"], row["nominal"], row["group_var"], row["group"])]
        assert row["coverage"] == pytest.approx(ref["coverage"], abs=6e-5)
        assert row["n"] == ref["n"]


@needs
def test_value_curves_and_triggers_match_decision_report():
    vc = pd.read_csv(REPORTS / "decision" / "value_curves.csv")
    vc = vc[vc["probability"] == "rolling isotonic"].set_index(["h", "event_id", "arm", "alpha"])
    payload = load("decision.json")
    for row in payload["value"]:
        assert row["value"] == pytest.approx(vc.loc[(row["h"], row["event_id"], row["arm"], row["alpha"]), "value"], abs=6e-5)
    # the dashboard's trigger table must agree with the report's trigger table where they overlap
    trig = pd.read_csv(REPORTS / "decision" / "triggers.csv")
    trig = trig[(trig["probability"] == "rolling isotonic") & (trig["arm"] == "M2 + ENSO/IOD")].set_index(["h", "event_id", "trigger"])
    checked = 0
    for row in payload["triggers"]:
        key = (row["h"], row["event"], round(row["trigger"], 2))
        if key in trig.index:
            assert row["hit_rate"] == pytest.approx(trig.loc[key, "hit_rate"], abs=6e-5)
            assert row["false_alarm_ratio"] == pytest.approx(trig.loc[key, "false_alarm_ratio"], abs=6e-5)
            checked += 1
    assert checked >= 9


@needs
def test_summary_counts_match_processed_data():
    s = load("summary.json")
    cat = pd.read_parquet(ROOT / "data" / "processed" / "station_catalog.parquet")
    assert s["n_stations"] == len(cat) and s["n_obs"] == int(cat["n_obs"].sum())
    assert all(k in s["sources"] for k in ("skill", "calibration", "decision"))
