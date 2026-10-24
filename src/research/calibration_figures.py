"""
Research Pipeline — Phase 3 figures. Reads reports/calibration/* and writes PNGs next to them.

  fig_coverage_by_depth.png   80 % coverage per depth class for four methods, per horizon
  fig_frontier.png            sharpness (Winkler score) vs worst conditional miss, per method
  fig_drift.png               median residual by target year vs all-India monsoon anomaly
  fig_pit.png                 PIT histograms of the static methods (12-month horizon)
"""

import json

import matplotlib
import numpy as np
import pandas as pd

from src.research.calibration import CALIBRATION_REPORTS_DIR, POINT_ARM
from src.research.config import DATA_PROCESSED_DIR, FORCING_REPORTS_DIR, TRAIN_END_YEAR

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

MONTHS = {1: "3 months", 2: "6 months", 4: "12 months"}
DEPTHS = ["< 5 m", "5–15 m", "15–40 m", "≥ 40 m"]
SHOWN = {  # validated categorical slots + one neutral
    "Split conformal": "#9aa8ab",
    "Mondrian D×R": "#eb6834",
    "Mondrian D×R + recal + ACI": "#2a78d6",
    "Normalised D×R×S + recal + ACI": "#1baf7a",
}


def _clean(ax):
    ax.spines[["top", "right"]].set_visible(False)


def fig_coverage_by_depth(cov: pd.DataFrame, path):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8), sharey=True)
    for ax, h in zip(axes, (1, 2, 4)):
        sub = cov[(cov["h"] == h) & (cov["nominal"] == 0.8) & (cov["group_var"] == "Depth")]
        ax.axhspan(77, 83, color="#d6dfde", alpha=0.6, lw=0)
        ax.axhline(80, color="#102a33", lw=1, ls="--")
        for i, (m, col) in enumerate(SHOWN.items()):
            vals = [sub[(sub["method"] == m) & (sub["group"] == d)]["coverage"].mean() * 100 for d in DEPTHS]
            ax.plot(np.arange(4) + (i - 1.5) * 0.08, vals, "o-", color=col, lw=1.5, ms=6, label=m,
                    markeredgecolor="white", markeredgewidth=1.2)
        ax.set_xticks(range(4), DEPTHS)
        ax.set_title(MONTHS[h])
        _clean(ax)
    axes[0].set_ylabel("Coverage of 80 % interval (%)")
    axes[0].legend(frameon=False, fontsize=8, loc="lower left")
    fig.suptitle("Coverage by depth class (grey band = ±3 points of the target)")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_frontier(cov: pd.DataFrame, path):
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
    groups = cov[(cov["group_var"] != "All") & (cov["nominal"] == 0.8)].copy()
    groups["dev"] = (groups["coverage"] - groups["nominal"]).abs() * 100
    for ax, h in zip(axes, (1, 2, 4)):
        worst = groups[groups["h"] == h].groupby("method")["dev"].max()
        wk = cov[(cov["h"] == h) & (cov["nominal"] == 0.8) & (cov["group_var"] == "All")].set_index("method")["winkler"]
        for m in worst.index:
            col = SHOWN.get(m, "#435a62")
            ax.scatter(wk[m], worst[m], s=55, color=col, edgecolor="white", linewidth=1.2, zorder=3)
            ax.annotate(m, (wk[m], worst[m]), fontsize=7, xytext=(4, 3), textcoords="offset points", color="#102a33")
        ax.axhline(3, color="#102a33", ls="--", lw=1)
        ax.set_yscale("log")
        ax.set_title(MONTHS[h])
        ax.set_xlabel("Winkler score at 80 % (m, lower = sharper)")
        _clean(ax)
    axes[0].set_ylabel("Worst miss over depth, region, season,\nrecord classes (points, log)")
    fig.suptitle("No method wins on both axes; dashed line = 3-point tolerance")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_drift(path):
    p = pd.read_parquet(DATA_PROCESSED_DIR / "skill_predictions.parquet")
    p = p[p["split"].isin(["cal", "test"])].copy()
    p["r"] = p["y_target"] - p[POINT_ARM]
    p["year"] = p["target_idx"] // 4
    with open(FORCING_REPORTS_DIR / "sanity.json") as f:
        jjas = {int(k): v for k, v in json.load(f)["all_india_jjas_mm"].items()}
    base = np.mean([v for y, v in jjas.items() if 1994 <= y <= TRAIN_END_YEAR])
    fig, ax = plt.subplots(figsize=(8, 4))
    for h, col in zip((1, 2, 4), ("#2a78d6", "#eb6834", "#1baf7a")):
        med = p[p["h"] == h].groupby("year")["r"].median()
        med = med[med.index <= 2024]
        ax.plot(med.index, med.values, "o-", color=col, label=f"Median residual, {MONTHS[h]}")
    ax2 = ax.twinx()
    years = sorted(y for y in jjas if 2016 <= y <= 2024)
    ax2.bar(years, [(jjas[y] / base - 1) * 100 for y in years], color="#d6dfde", width=0.6, zorder=0)
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)
    ax.axhline(0, color="#102a33", lw=0.8)
    ax.set_ylim(-0.8, 0.8)  # both axes centred on zero so the bars and lines share a baseline
    ax2.set_ylim(-16, 16)
    ax.axvspan(2015.5, 2018.5, color="#f4f6f5", zorder=-1)
    ax.text(2017, ax.get_ylim()[1] * 0.85, "calibration", ha="center", fontsize=9, color="#435a62")
    ax.set_ylabel("Observed − forecast depth (m)\n(< 0: water shallower than forecast)")
    ax2.set_ylabel("All-India JJAS rain vs 1994–2015 (%, bars)")
    ax.set_title("Strong 2019–2022 monsoons left water shallower than forecast")
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_pit(path):
    with open(CALIBRATION_REPORTS_DIR / "pit.json") as f:
        pit = [r for r in json.load(f) if r["h"] == 4]
    fig, axes = plt.subplots(1, len(pit), figsize=(13, 2.8), sharey=True)
    for ax, r in zip(axes, pit):
        ax.bar(np.arange(10) / 10 + 0.05, r["pit_hist"], width=0.09, color="#2a78d6")
        ax.axhline(0.1, color="#102a33", ls="--", lw=1)
        ax.set_title(r["method"], fontsize=9)
        ax.set_xticks([0, 0.5, 1])
        _clean(ax)
    axes[0].set_ylabel("Share")
    fig.suptitle("PIT histograms, 12 months (flat = calibrated; left-heavy = test water shallower than calibration implied)")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run_figures():
    cov = pd.read_csv(CALIBRATION_REPORTS_DIR / "coverage.csv")
    fig_coverage_by_depth(cov, CALIBRATION_REPORTS_DIR / "fig_coverage_by_depth.png")
    fig_frontier(cov, CALIBRATION_REPORTS_DIR / "fig_frontier.png")
    fig_drift(CALIBRATION_REPORTS_DIR / "fig_drift.png")
    fig_pit(CALIBRATION_REPORTS_DIR / "fig_pit.png")
    print(f"Saved figures to {CALIBRATION_REPORTS_DIR}/")


if __name__ == "__main__":
    run_figures()
