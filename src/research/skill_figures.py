"""
Research Pipeline — Phase 2.5: Figures for the skill decomposition.
Reads reports/skill/* and writes PNG figures next to them.

  fig_skill_by_horizon.png   skill vs persistence per arm, with 95% well-clustered CIs
  fig_gain_by_stratum.png    MSE reduction over M0 for M1/M2/M3 by depth, region and target season
  fig_shap_groups.png        share of attribution per feature group (M2 and M3)
"""

import json

import matplotlib
import numpy as np
import pandas as pd

from src.research.config import SKILL_REPORTS_DIR

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ARM_STYLE = {  # validated categorical slots (dataviz palette) + neutral greys for baselines
    "anomaly_persistence": ("Anomaly persistence", "#9aa8ab"),
    "C snapshot control": ("C snapshot control", "#6a7d83"),
    "M0 memory": ("M0 memory", "#2a78d6"),
    "M1 + past forcing": ("M1 + past forcing", "#eb6834"),
    "M2 + ENSO/IOD": ("M2 + ENSO/IOD", "#1baf7a"),
    "M3 + oracle rain": ("M3 + oracle rain", "#102a33"),
}
MONTHS = {1: "3 months", 2: "6 months", 4: "12 months"}


def fig_skill_by_horizon(boot: list[dict], path):
    rows = pd.DataFrame([r for r in boot if r["stat"] == "skill_vs_persistence"])
    fig, ax = plt.subplots(figsize=(8, 4.2))
    hs = sorted(rows["h"].unique())
    width = 0.13
    for i, (key, (label, color)) in enumerate(ARM_STYLE.items()):
        sub = rows[rows["model"] == key].set_index("h").reindex(hs)
        x = np.arange(len(hs)) + (i - (len(ARM_STYLE) - 1) / 2) * width
        lo = sub["estimate"] - sub["ci"].map(lambda c: c[0])
        hi = sub["ci"].map(lambda c: c[1]) - sub["estimate"]
        ax.bar(x, sub["estimate"], width * 0.92, color=color, label=label, yerr=[lo, hi], capsize=2,
               error_kw={"elinewidth": 1, "ecolor": "#333"})
    ax.axhline(0, color="#333", lw=0.8)
    ax.set_xticks(np.arange(len(hs)), [MONTHS[h] for h in hs])
    ax.set_ylabel("MSE skill vs persistence")
    ax.set_title("Test 2019–2025, identical rows per horizon; bars = 95% well-clustered CI")
    ax.legend(frameon=False, ncol=3, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.1))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_gain_by_stratum(strata: pd.DataFrame, path):
    arms = ["M1 + past forcing", "M2 + ENSO/IOD", "M3 + oracle rain"]
    order = {"depth_class": ["< 5 m", "5–15 m", "15–40 m", "≥ 40 m"],
             "region": ["Indo-Gangetic plain", "Peninsular", "Arid north-west", "Himalaya & north-east"],
             "target_season": ["Jan", "May", "Aug", "Nov"]}
    titles = {"depth_class": "Depth at origin", "region": "Region", "target_season": "Target campaign"}
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4), gridspec_kw={"wspace": 0.55})
    for ax, (stratum, values) in zip(axes, order.items()):
        sub = strata[(strata["stratum"] == stratum) & strata["arm"].isin(arms)]
        mat = np.array([[sub[(sub["value"] == v) & (sub["arm"] == a) & (sub["h"] == h)]["mse_reduction_vs_M0"].mean()
                         for a in arms for h in (1, 2, 4)] for v in values]) * 100
        im = ax.imshow(mat, cmap="RdBu", vmin=-15, vmax=15, aspect="auto")
        ax.set_yticks(range(len(values)), [v.replace(" & ", " &\n").replace("-Gangetic ", "-Gangetic\n")
                                           .replace("Arid ", "Arid\n") for v in values])
        ax.set_xticks(range(9), [f"{a.split()[0]}\n{MONTHS[h].split()[0]}m" for a in arms for h in (1, 2, 4)], fontsize=8)
        for (i, j), v in np.ndenumerate(mat):
            ax.text(j, i, f"{v:+.0f}", ha="center", va="center", fontsize=7.5,
                    color="white" if abs(v) > 9 else "#102a33")
        ax.set_title(titles[stratum])
    fig.colorbar(im, ax=axes, shrink=0.8, label="MSE reduction vs M0 (%)")
    fig.suptitle("Where forcing helps: gain over the memory-only model (test 2019–2025)")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def fig_shap_groups(shap: pd.DataFrame, path):
    shap = shap.copy()
    shap["share"] = shap["mean_abs_shap_m"] / shap.groupby(["h", "arm"])["mean_abs_shap_m"].transform("sum")
    groups = ["Groundwater memory", "Season & climatology", "Past rainfall & temperature", "ENSO/IOD",
              "Future rainfall (oracle)", "Location & borehole"]
    colors = ["#2a78d6", "#9aa8ab", "#eb6834", "#1baf7a", "#102a33", "#d6dfde"]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    left = None
    combos = [(a, h) for a in ("M2 + ENSO/IOD", "M3 + oracle rain") for h in (1, 2, 4)]
    for g, c in zip(groups, colors):
        vals = np.array([shap[(shap["arm"] == a) & (shap["h"] == h) & (shap["group"] == g)]["share"].sum() for a, h in combos])
        ax.barh(range(len(combos)), vals * 100, left=None if left is None else left, color=c, label=g, height=0.7,
                edgecolor="white", linewidth=1)
        left = vals * 100 if left is None else left + vals * 100
    ax.set_yticks(range(len(combos)), [f"{a.split()[0]}, {MONTHS[h]}" for a, h in combos])
    ax.invert_yaxis()
    ax.set_xlabel("Share of mean |TreeSHAP| (%)")
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def run_figures():
    with open(SKILL_REPORTS_DIR / "bootstrap.json") as f:
        boot = json.load(f)
    fig_skill_by_horizon(boot, SKILL_REPORTS_DIR / "fig_skill_by_horizon.png")
    fig_gain_by_stratum(pd.read_csv(SKILL_REPORTS_DIR / "strata.csv"), SKILL_REPORTS_DIR / "fig_gain_by_stratum.png")
    fig_shap_groups(pd.read_csv(SKILL_REPORTS_DIR / "shap_groups.csv"), SKILL_REPORTS_DIR / "fig_shap_groups.png")
    print(f"Saved figures to {SKILL_REPORTS_DIR}/")


if __name__ == "__main__":
    run_figures()
