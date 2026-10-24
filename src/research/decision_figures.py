"""
Research Pipeline — Phase 4 figures. Reads reports/decision/* and writes PNGs next to them.

  fig_value_curves.png   relative economic value V(C/L) for M0, M2, M3 with 95% CIs (primary probabilities)
  fig_reliability.png    reliability of raw, static-isotonic and rolling-isotonic probabilities (M2, E1)
  fig_triggers.png       hit rate vs false-alarm ratio for triggers 0.2–0.6 (M2, primary probabilities)
"""

import matplotlib
import pandas as pd

from src.research.decision_value import DECISION_REPORTS_DIR, EVENTS, PRIMARY_P, PROB_VARIANTS

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

MONTHS = {1: "3 months", 2: "6 months", 4: "12 months"}
ARM_COLORS = {"M0 memory": "#2a78d6", "M2 + ENSO/IOD": "#1baf7a", "M3 + oracle rain": "#102a33"}
VARIANT_COLORS = {"raw": "#eb6834", "static isotonic": "#9aa8ab", "rolling isotonic": "#2a78d6"}
PRIMARY = PROB_VARIANTS[PRIMARY_P]


def _clean(ax):
    ax.spines[["top", "right"]].set_visible(False)


def fig_value_curves(v: pd.DataFrame, path):
    events = ["E1", "E3"]
    fig, axes = plt.subplots(len(events), 3, figsize=(13, 6.5), sharex=True, sharey="row")
    for i, ev in enumerate(events):
        for j, h in enumerate((1, 2, 4)):
            ax = axes[i, j]
            for arm, col in ARM_COLORS.items():
                g = v[(v["h"] == h) & (v["event_id"] == ev) & (v["arm"] == arm) & (v["probability"] == PRIMARY)]
                ax.fill_between(g["alpha"], g["value_lo"], g["value_hi"], color=col, alpha=0.15, lw=0)
                ax.plot(g["alpha"], g["value"], color=col, lw=1.8, label=arm)
            ax.axhline(0, color="#102a33", lw=0.8)
            ax.set_ylim(-0.1, 0.8)
            if i == 0:
                ax.set_title(MONTHS[h])
            if j == 0:
                ax.set_ylabel(f"{EVENTS[ev]}\nrelative value V")
            if i == len(events) - 1:
                ax.set_xlabel("Cost–loss ratio C/L (act when p ≥ C/L)")
            _clean(ax)
    axes[0, 0].legend(frameon=False, fontsize=8)
    fig.suptitle("Economic value of warnings vs always/never acting (bands: 95% well-clustered CI)")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_reliability(rel: pd.DataFrame, path):
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), sharey=True)
    for ax, h in zip(axes, (1, 2, 4)):
        ax.plot([0, 1], [0, 1], color="#102a33", ls="--", lw=1)
        for variant, col in VARIANT_COLORS.items():
            g = rel[(rel["h"] == h) & (rel["event_id"] == "E1") & (rel["arm"] == "M2 + ENSO/IOD")
                    & (rel["probability"] == variant)]
            ax.plot(g["p_mean"], g["obs_freq"], "o-", color=col, label=variant, ms=5,
                    markeredgecolor="white", markeredgewidth=1)
        ax.set_title(MONTHS[h])
        ax.set_xlabel("Forecast probability")
        _clean(ax)
    axes[0].set_ylabel("Observed frequency")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Reliability of 'deeper than usual' warnings (M2): rolling recalibration tracks the diagonal")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def fig_triggers(t: pd.DataFrame, path):
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), sharey=True)
    colors = {"E1": "#2a78d6", "E2": "#eb6834", "E3": "#1baf7a"}
    for ax, h in zip(axes, (1, 2, 4)):
        for ev, col in colors.items():
            g = t[(t["h"] == h) & (t["event_id"] == ev) & (t["arm"] == "M2 + ENSO/IOD") & (t["probability"] == PRIMARY)]
            ax.plot(g["false_alarm_ratio"], g["hit_rate"], "o-", color=col, label=EVENTS[ev], ms=5)
            for r in g.itertuples():
                if r.trigger in (0.2, 0.3, 0.5):
                    ax.annotate(f"{r.trigger:.1f}", (r.false_alarm_ratio, r.hit_rate), fontsize=7,
                                xytext=(3, 3), textcoords="offset points", color="#435a62")
        ax.set_title(MONTHS[h])
        ax.set_xlabel("False-alarm ratio")
        ax.set_xlim(0, 0.8)
        ax.set_ylim(0, 1)
        _clean(ax)
    axes[0].set_ylabel("Hit rate (share of events warned)")
    axes[0].legend(frameon=False, fontsize=7, loc="lower right")
    fig.suptitle("Trigger trade-off (labels = trigger probability; false-alarm ratio = share of warnings that do not verify)")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run_figures():
    fig_value_curves(pd.read_csv(DECISION_REPORTS_DIR / "value_curves.csv"), DECISION_REPORTS_DIR / "fig_value_curves.png")
    fig_reliability(pd.read_csv(DECISION_REPORTS_DIR / "reliability.csv"), DECISION_REPORTS_DIR / "fig_reliability.png")
    fig_triggers(pd.read_csv(DECISION_REPORTS_DIR / "triggers.csv"), DECISION_REPORTS_DIR / "fig_triggers.png")
    print(f"Saved figures to {DECISION_REPORTS_DIR}/")


if __name__ == "__main__":
    run_figures()
