"""
Research Pipeline — Phase 6.1: Publication figures and tables.

Every figure and table in the manuscript is generated here from reports/ and data/processed/, so the
paper cannot drift from the results. Output:
  paper/figures/fig{1..8}.pdf (+ .png previews)
  paper/tables/tab{1..5}.tex
  paper/numbers.tex          \\newcommand macros for every number quoted in the text

Style: 174 mm full width (HESS), 8 pt sans-serif text, validated colour-blind-safe categorical slots.
"""

import json

import matplotlib
import numpy as np
import pandas as pd

from src.research.calibration import CALIBRATION_REPORTS_DIR
from src.research.config import DATA_PROCESSED_DIR, EXTERNAL_DIR, FORCING_REPORTS_DIR, SKILL_REPORTS_DIR, TRAIN_END_YEAR
from src.research.decision_value import DECISION_REPORTS_DIR
from src.research.regions import REGIONS, assign_region

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PAPER = DATA_PROCESSED_DIR.parent.parent / "paper"
FIG, TAB = PAPER / "figures", PAPER / "tables"
MM = 1 / 25.4
FULL, HALF = 174 * MM, 84 * MM
BLUE, ORANGE, AQUA, INK, GREY, LIGHT = "#2a78d6", "#eb6834", "#1baf7a", "#102a33", "#6a7d83", "#c9d2d2"
ARM_COLORS = {"M0 memory": BLUE, "M1 + past forcing": ORANGE, "M2 + ENSO/IOD": AQUA, "M3 + oracle rain": INK,
              "C snapshot control": GREY, "anomaly_persistence": LIGHT}
ARM_LABELS = {"anomaly_persistence": "Anomaly persistence", "C snapshot control": "C: snapshot rainfall",
              "M0 memory": "M0: memory", "M1 + past forcing": "M1: + past forcing",
              "M2 + ENSO/IOD": "M2: + ENSO/IOD", "M3 + oracle rain": "M3: + oracle rain"}
H_LABEL = {1: "3 months", 2: "6 months", 4: "12 months"}

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"], "font.size": 8, "axes.titlesize": 8.5,
    "axes.labelsize": 8, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7.5,
    "axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.6, "xtick.major.width": 0.6,
    "ytick.major.width": 0.6, "savefig.dpi": 300, "pdf.fonttype": 42, "axes.titleweight": "bold",
})


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight", dpi=150)
    plt.close(fig)


def panel(ax, letter):
    ax.text(-0.02, 1.04, f"({letter})", transform=ax.transAxes, fontweight="bold", fontsize=8.5, ha="right", va="bottom")


# ── Figure 1: study area ────────────────────────────────────────────────────

def fig1_study_area():
    from shapely.geometry import shape

    cat = pd.read_parquet(DATA_PROCESSED_DIR / "station_catalog.parquet")
    cat["region"] = assign_region(cat["latitude"], cat["longitude"]).to_numpy()
    camp = pd.read_parquet(DATA_PROCESSED_DIR / "gwl_campaigns.parquet")
    fig, axes = plt.subplots(1, 2, figsize=(FULL, 92 * MM), gridspec_kw={"width_ratios": [1.15, 1]})
    ax = axes[0]
    gj = json.loads((EXTERNAL_DIR / "boundaries" / "geoBoundaries-IND-ADM1_simplified.geojson").read_text())
    for f in gj["features"]:
        g = shape(f["geometry"])
        for poly in getattr(g, "geoms", [g]):
            x, y = poly.exterior.xy
            ax.plot(x, y, color="#9aa8ab", lw=0.3, zorder=1)
    colors = dict(zip(REGIONS, [BLUE, ORANGE, AQUA, "#6250d6"]))
    man = cat[cat["network"] == "manual"]
    for reg in REGIONS:
        s = man[man["region"] == reg]
        ax.scatter(s["longitude"], s["latitude"], s=1.2, color=colors[reg], label=f"{reg} ({len(s):,})", zorder=2, lw=0)
    dw = cat[cat["network"] == "DWLR"]
    ax.scatter(dw["longitude"], dw["latitude"], s=3, marker="x", color=INK, lw=0.4, label=f"DWLR telemetry ({len(dw):,})", zorder=3)
    ax.set_xlim(67.5, 98)
    ax.set_ylim(6.5, 37.5)
    ax.set_aspect(1 / np.cos(np.deg2rad(22)))
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, markerscale=4, frameon=False, fontsize=6.5,
              handletextpad=0.3, columnspacing=0.8)
    panel(ax, "a")

    ax = axes[1]
    camp["year"] = camp["campaign_idx"] // 4
    per_year = camp.groupby("year")["well_id"].nunique()
    ax.bar(per_year.index, per_year.values, color=BLUE, width=0.8, lw=0)
    for y0, y1, lab, c in [(1994, TRAIN_END_YEAR + 0.5, "train", "#e8eded"), (TRAIN_END_YEAR + 0.5, 2018.5, "calibrate", "#d6dfde"),
                           (2018.5, 2025.5, "test", "#f3d9cc")]:
        ax.axvspan(y0, y1, color=c, zorder=0, lw=0)
        ax.text((y0 + y1) / 2, per_year.max() * 1.04, lab, ha="center", fontsize=7, color=INK)
    ax.set_ylim(0, per_year.max() * 1.12)
    ax.set_xlabel("Target year")
    ax.set_ylabel("Manual wells with a campaign reading")
    panel(ax, "b")
    fig.tight_layout()
    save(fig, "fig1")


# ── Figure 2: forcing data checks ───────────────────────────────────────────

def fig2_forcing_checks():
    rep = json.loads((FORCING_REPORTS_DIR / "sanity.json").read_text())
    feats = pd.read_parquet(DATA_PROCESSED_DIR / "forcing_features.parquet")
    camp = pd.read_parquet(DATA_PROCESSED_DIR / "gwl_campaigns.parquet")
    fig, axes = plt.subplots(1, 3, figsize=(FULL, 58 * MM))

    ax = axes[0]
    chk = rep["jjas_departure_check"]
    yrs = sorted(chk)
    x = np.arange(len(yrs))
    ax.bar(x - 0.2, [chk[y]["ours_pct"] for y in yrs], 0.38, color=BLUE, label="IMD grid (this study)", lw=0)
    ax.bar(x + 0.2, [chk[y]["imd_pct"] for y in yrs], 0.38, color=ORANGE, label="IMD reported", lw=0)
    ax.axhline(0, color=INK, lw=0.6)
    ax.set_xticks(x, [y[2:] for y in yrs])
    ax.set_xlabel("Year (20xx)")
    ax.set_ylabel("All-India JJAS departure (%)")
    ax.legend(frameon=False, fontsize=6.5, loc="upper left")
    panel(ax, "a")

    ax = axes[1]
    may = camp[camp["season"] == 1].set_index(["well_id", "year"])["depth_mbgl"]
    nov = camp[camp["season"] == 3].set_index(["well_id", "year"])["depth_mbgl"]
    rise = (may - nov).dropna().rename("rise").reset_index()
    jj = feats[feats["campaign_idx"] % 4 == 3][["well_id", "campaign_idx", "jjas_last_ratio"]].copy()
    jj["year"] = jj["campaign_idx"] // 4
    d = rise.merge(jj, on=["well_id", "year"]).dropna()
    d = d[(d["rise"].abs() < 20) & (d["jjas_last_ratio"] < 2.5)]
    ax.hexbin(d["jjas_last_ratio"], d["rise"], gridsize=40, cmap="Blues", mincnt=1, bins="log", lw=0)
    med = d.groupby(pd.cut(d["jjas_last_ratio"], np.arange(0.2, 2.01, 0.1)), observed=True)["rise"].median()
    ax.plot([i.mid for i in med.index], med.values, color=ORANGE, lw=1.6, label="Median")
    ax.axhline(0, color=INK, lw=0.6)
    ax.set_xlabel("JJAS rain at the well / normal")
    ax.set_ylabel("Water-table rise, May → Nov (m)")
    ax.legend(frameon=False, loc="upper left")
    panel(ax, "b")

    ax = axes[2]
    s = feats[["snap_cum4", "rain_12m"]].dropna().sample(40000, random_state=0)
    ax.scatter(s["rain_12m"], s["snap_cum4"] + 0.1, s=0.5, color=BLUE, alpha=0.25, lw=0)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("IMD rain, last 12 months (mm)")
    ax.set_ylabel("Source-file 'rainfall', summed\nover 4 campaigns (mm + 0.1)")
    snap = rep["snapshot_vs_imd_12m"]
    ax.text(0.03, 0.97, f"Spearman ρ = {snap['spearman']:.2f}\nmedians {snap['median_snap_cum4_mm']:.1f} vs "
            f"{snap['median_imd_rain_12m_mm']:,.0f} mm", transform=ax.transAxes, va="top", fontsize=6.5)
    panel(ax, "c")
    fig.tight_layout()
    save(fig, "fig2")


# ── Figure 3: skill decomposition ───────────────────────────────────────────

def fig3_skill():
    boot = [b for b in json.loads((SKILL_REPORTS_DIR / "bootstrap.json").read_text()) if b["stat"] == "skill_vs_persistence"]
    df = pd.DataFrame(boot)
    order = ["anomaly_persistence", "C snapshot control", "M0 memory", "M1 + past forcing", "M2 + ENSO/IOD", "M3 + oracle rain"]
    fig, ax = plt.subplots(figsize=(FULL, 62 * MM))
    w = 0.13
    for i, m in enumerate(order):
        s = df[df["model"] == m].set_index("h").reindex([1, 2, 4])
        x = np.arange(3) + (i - 2.5) * w
        lo = s["estimate"] - s["ci"].map(lambda c: c[0])
        hi = s["ci"].map(lambda c: c[1]) - s["estimate"]
        ax.bar(x, s["estimate"], w * 0.9, color=ARM_COLORS[m], label=ARM_LABELS[m], yerr=[lo, hi], capsize=1.5,
               error_kw={"elinewidth": 0.6, "ecolor": INK, "capthick": 0.6}, lw=0)
    ax.axhline(0, color=INK, lw=0.6)
    ax.set_xticks(range(3), [H_LABEL[h] for h in (1, 2, 4)])
    ax.set_ylabel("MSE skill vs persistence")
    ax.legend(frameon=False, ncol=6, loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=7, columnspacing=1.0)
    fig.tight_layout()
    save(fig, "fig3")


# ── Figure 4: where forcing helps ───────────────────────────────────────────

def fig4_strata():
    st = pd.read_csv(SKILL_REPORTS_DIR / "strata.csv")
    arms = ["M2 + ENSO/IOD", "M3 + oracle rain"]
    blocks = {"target_season": ["Jan", "May", "Aug", "Nov"], "depth_class": ["< 5 m", "5–15 m", "15–40 m", "≥ 40 m"],
              "region": REGIONS}
    titles = {"target_season": "(a) Target campaign", "depth_class": "(b) Depth at origin", "region": "(c) Region"}
    cols = [(a, h) for a in arms for h in (1, 2, 4)]
    fig, axes = plt.subplots(3, 1, figsize=(FULL * 0.8, 140 * MM), gridspec_kw={"hspace": 0.75})
    for ax, (k, vals) in zip(axes, blocks.items()):
        mat = np.array([[st[(st["stratum"] == k) & (st["value"] == v) & (st["arm"] == a) & (st["h"] == h)]["mse_reduction_vs_M0"].mean()
                         for a, h in cols] for v in vals]) * 100
        im = ax.imshow(mat, cmap="RdBu", vmin=-28, vmax=28, aspect="auto")
        ax.set_yticks(range(len(vals)), vals)
        ax.set_xticks(range(len(cols)), [f"{a.split()[0]}\n{H_LABEL[h]}" for a, h in cols], fontsize=7)
        for (i, j), v in np.ndenumerate(mat):
            ax.text(j, i, f"{round(v):+d}", ha="center", va="center", fontsize=7, color="white" if abs(v) > 15 else INK)
        ax.set_title(titles[k], loc="left", fontsize=8)
        ax.spines[:].set_visible(False)
        ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=axes, shrink=0.6, pad=0.02)
    cb.set_label("MSE reduction vs M0 (%)")
    save(fig, "fig4")


# ── Figure 5: conditional coverage ──────────────────────────────────────────

def fig5_coverage():
    cov = pd.read_csv(CALIBRATION_REPORTS_DIR / "coverage.csv")
    methods = {"Split conformal": ORANGE, "Mondrian D×R": GREY, "CQR": "#6250d6", "Mondrian D×R + recal + ACI": BLUE}
    depths = ["< 5 m", "5–15 m", "15–40 m", "≥ 40 m"]
    regions = REGIONS
    fig, axes = plt.subplots(2, 3, figsize=(FULL, 96 * MM), sharey="row")
    for col, h in enumerate((1, 2, 4)):
        for row, (gv, groups) in enumerate((("Depth", depths), ("Region", regions))):
            ax = axes[row, col]
            sub = cov[(cov["h"] == h) & (cov["nominal"] == 0.8) & (cov["group_var"] == gv)]
            ax.axhspan(77, 83, color="#e8eded", lw=0, zorder=0)
            ax.axhline(80, color=INK, lw=0.6, ls="--")
            for i, (m, c) in enumerate(methods.items()):
                v = [sub[(sub["method"] == m) & (sub["group"] == g)]["coverage"].mean() * 100 for g in groups]
                ax.plot(np.arange(len(groups)) + (i - 1.5) * 0.07, v, "o-", color=c, ms=3, lw=0.9, label=m if col == 0 and row == 0 else None)
            ax.set_xticks(range(len(groups)), [g.replace("Indo-Gangetic plain", "IGP").replace("Himalaya & north-east", "Him. & NE")
                                                .replace("Arid north-west", "Arid NW") for g in groups], fontsize=6.8)
            if row == 0:
                ax.set_title(H_LABEL[h])
            if col == 0:
                ax.set_ylabel(f"80 % coverage by {gv.lower()} (%)")
    axes[0, 0].legend(frameon=False, fontsize=6.5, loc="lower left")
    fig.tight_layout()
    save(fig, "fig5")


# ── Figure 6: drift ─────────────────────────────────────────────────────────

def fig6_drift():
    p = pd.read_parquet(DATA_PROCESSED_DIR / "skill_predictions.parquet")
    p = p[p["split"].isin(["cal", "test"])].copy()
    p["r"] = p["y_target"] - p["M2 + ENSO/IOD"]
    p["year"] = p["target_idx"] // 4
    jjas = {int(k): v for k, v in json.loads((FORCING_REPORTS_DIR / "sanity.json").read_text())["all_india_jjas_mm"].items()}
    base = np.mean([v for y, v in jjas.items() if 1994 <= y <= TRAIN_END_YEAR])
    fig, ax = plt.subplots(figsize=(HALF * 1.25, 62 * MM))
    yrs = list(range(2016, 2025))
    ax2 = ax.twinx()
    ax2.bar(yrs, [(jjas[y] / base - 1) * 100 for y in yrs], color="#e8eded", width=0.65, lw=0)
    ax2.set_ylim(-16, 16)
    ax2.set_ylabel("All-India JJAS rain vs 1994–2015 (%, bars)")
    ax2.spines["right"].set_visible(True)
    for h, c in zip((1, 2, 4), (BLUE, ORANGE, AQUA)):
        med = p[(p["h"] == h) & p["year"].isin(yrs)].groupby("year")["r"].median()
        ax.plot(med.index, med.values, "o-", color=c, ms=3, lw=1.1, label=H_LABEL[h])
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)
    ax.axhline(0, color=INK, lw=0.6)
    ax.axvline(2018.5, color=GREY, lw=0.6, ls=":")
    ax.set_ylim(-0.8, 0.8)
    ax.set_ylabel("Median residual, observed − forecast (m)")
    ax.legend(frameon=False, loc="lower left", fontsize=6.5)
    ax.text(2017, 0.68, "calibration", ha="center", fontsize=6.5, color=GREY)
    ax.text(2021.5, 0.68, "test", ha="center", fontsize=6.5, color=GREY)
    fig.tight_layout()
    save(fig, "fig6")


# ── Figure 7: reliability ───────────────────────────────────────────────────

def fig7_reliability():
    rel = pd.read_csv(DECISION_REPORTS_DIR / "reliability.csv")
    rel = rel[(rel["arm"] == "M2 + ENSO/IOD") & (rel["n"] >= 30)]
    fig, axes = plt.subplots(1, 3, figsize=(FULL, 58 * MM), sharey=True)
    variants = {"raw": ORANGE, "static isotonic": GREY, "rolling isotonic": BLUE}
    for ax, h in zip(axes, (1, 2, 4)):
        ax.plot([0, 1], [0, 1], color=INK, lw=0.6, ls="--")
        for v, c in variants.items():
            s = rel[(rel["h"] == h) & (rel["event_id"] == "E1") & (rel["probability"] == v)]
            ax.plot(s["p_mean"], s["obs_freq"], "o-", color=c, ms=3, lw=1, label=v)
        ax.set_title(H_LABEL[h])
        ax.set_xlabel("Forecast probability")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    axes[0].set_ylabel("Observed frequency")
    axes[0].legend(frameon=False, loc="upper left")
    fig.tight_layout()
    save(fig, "fig7")


# ── Figure 8: economic value ────────────────────────────────────────────────

def fig8_value():
    v = pd.read_csv(DECISION_REPORTS_DIR / "value_curves.csv")
    v = v[v["probability"] == "rolling isotonic"]
    arms = {"M0 memory": BLUE, "M2 + ENSO/IOD": AQUA, "M3 + oracle rain": INK}
    events = {"E1": "Deeper than usual (E1)", "E3": "Below 8 m (E3)"}
    fig, axes = plt.subplots(2, 3, figsize=(FULL, 96 * MM), sharex=True, sharey=True)
    for row, (ev, name) in enumerate(events.items()):
        for col, h in enumerate((1, 2, 4)):
            ax = axes[row, col]
            for a, c in arms.items():
                s = v[(v["h"] == h) & (v["event_id"] == ev) & (v["arm"] == a)]
                ax.fill_between(s["alpha"], s["value_lo"], s["value_hi"], color=c, alpha=0.18, lw=0)
                ax.plot(s["alpha"], s["value"], color=c, lw=1, label=ARM_LABELS[a])
            ax.axhline(0, color=INK, lw=0.6)
            ax.set_ylim(-0.15, 0.8)
            if row == 0:
                ax.set_title(H_LABEL[h])
            if row == 1:
                ax.set_xlabel("Cost–loss ratio C/L")
            if col == 0:
                ax.set_ylabel(f"{name}\nrelative value V")
    axes[0, 0].legend(frameon=False, loc="upper right", fontsize=6.5)
    fig.tight_layout()
    save(fig, "fig8")


# ── Tables ──────────────────────────────────────────────────────────────────

def tex_table(path, caption, label, header, rows, colspec, note=None):
    lines = [r"\begin{table*}[t]", r"\caption{" + caption + "}", r"\label{" + label + "}", r"\centering\small",
             r"\begin{adjustbox}{max width=\textwidth}", r"\begin{tabular}{" + colspec + "}", r"\toprule",
             " & ".join(header) + r" \\", r"\midrule"]
    lines += [" & ".join(r) + r" \\" for r in rows]
    lines += [r"\bottomrule", r"\end{tabular}", r"\end{adjustbox}"]
    if note:
        lines += [r"\par\smallskip\begin{minipage}{0.95\textwidth}\footnotesize " + note + r"\end{minipage}"]
    lines += [r"\end{table*}"]
    TAB.mkdir(parents=True, exist_ok=True)
    (TAB / path).write_text("\n".join(lines) + "\n")


def f(x, d=3, signed=False):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "--"
    s = f"{x:+.{d}f}" if signed else f"{x:.{d}f}"
    return s.replace("-", "$-$")


def pc(x, d=1, signed=True):
    return (f"{x * 100:+.{d}f}" if signed else f"{x * 100:.{d}f}").replace("-", "$-$")


def tables():
    cat = pd.read_parquet(DATA_PROCESSED_DIR / "station_catalog.parquet")
    camp = pd.read_parquet(DATA_PROCESSED_DIR / "gwl_campaigns.parquet")
    obs_n = int(cat["n_obs"].sum())
    metrics = pd.read_csv(SKILL_REPORTS_DIR / "metrics.csv")
    boot = {(b["h"], b["model"]): b for b in json.loads((SKILL_REPORTS_DIR / "bootstrap.json").read_text())
            if b["stat"] == "skill_vs_persistence"}

    # Table 1: data
    rows = [["Stations (manual / DWLR)", f"{len(cat):,} ({(cat['network'] == 'manual').sum():,} / {(cat['network'] == 'DWLR').sum():,})"],
            ["Readings after quality control", f"{obs_n:,}"],
            ["Period", f"{cat['first_obs'].min():%Y}--{cat['last_obs'].max():%Y}"],
            ["Manual-well campaign values (Jan, May, Aug, Nov)", f"{len(camp):,} from {camp['well_id'].nunique():,} wells"],
            ["Split by target year", f"train $\\le$ {TRAIN_END_YEAR}; calibration 2016--2018; test 2019--2025"],
            ["Rainfall forcing", "IMD 0.25$^\\circ$ daily gridded, 1990--2025"],
            ["Temperature forcing", "IMD 1$^\\circ$ daily Tmax/Tmin, 1990--2025"],
            ["Teleconnections", "Ni\\~no 3.4 and DMI (HadISST, NOAA PSL), lags 0/3/6 months"]]
    tex_table("tab1.tex", "Data used in this study.", "tab:data", ["Item", "Value"], rows, "ll")

    # Table 2: point skill
    rows = []
    for m in ["persistence", "anomaly_persistence", "C snapshot control", "M0 memory", "M1 + past forcing", "M2 + ENSO/IOD", "M3 + oracle rain"]:
        r = [ARM_LABELS.get(m, "Persistence")]
        for h in (1, 2, 4):
            mm = metrics[(metrics["h"] == h) & (metrics["model"] == m)].iloc[0]
            if m == "persistence":
                r += [f(mm["rmse"], 2), "0"]
            else:
                b = boot[(h, m)]
                r += [f(mm["rmse"], 2), f"{f(b['estimate'])} [{f(b['ci'][0])}, {f(b['ci'][1])}]"]
        rows.append(r)
    n = {h: metrics[(metrics["h"] == h)].iloc[0] for h in (1, 2, 4)}
    tex_table("tab2.tex", "Test-period (2019--2025) point skill on identical rows: RMSE (m) and MSE skill against persistence with "
              "95\\,\\% well-clustered bootstrap intervals.", "tab:skill",
              ["Model", "RMSE 3 mo", "Skill 3 mo", "RMSE 6 mo", "Skill 6 mo", "RMSE 12 mo", "Skill 12 mo"], rows, "lrrrrrr",
              note=f"Rows: {int(n[1]['n']):,} / {int(n[2]['n']):,} / {int(n[4]['n']):,} forecasts at 3 / 6 / 12 months.")

    # Table 3: gains and robustness
    dm = pd.read_csv(SKILL_REPORTS_DIR / "diebold_mariano.csv")
    rob = pd.read_csv(SKILL_REPORTS_DIR / "robustness.csv")
    rows = []
    pairs = [("M0 memory", "M1 + past forcing", "M1 vs M0"), ("M0 memory", "M2 + ENSO/IOD", "M2 vs M0"),
             ("M2 + ENSO/IOD", "M3 + oracle rain", "M3 vs M2"), ("M0 memory", "C snapshot control", "C vs M0")]
    for a, b, lab in pairs:
        for h in (1, 2, 4):
            d = dm[(dm["h"] == h) & (dm["a"] == a) & (dm["b"] == b)].iloc[0]
            ci = json.loads(d["mae_reduction_ci"]) if isinstance(d["mae_reduction_ci"], str) else d["mae_reduction_ci"]
            r = [lab if h == 1 else "", H_LABEL[h], pc(d["mse_reduction"]), f"{pc(d['mae_reduction'])} [{pc(ci[0])}, {pc(ci[1])}]",
                 f"{int(d['campaigns_b_better'])}/{int(d['campaigns'])}",
                 "$<$0.001" if d["sign_p_value"] < 0.001 else f(d["sign_p_value"], 3)]
            for setting in ("Split: train ≤2017, test 2020–25", "Spatial blocks (unseen regions)"):
                q = rob[(rob["setting"] == setting) & (rob["h"] == h) & (rob["a"] == a) & (rob["b"] == b)]
                r.append(pc(q["mse_reduction"].iloc[0]) if len(q) else "--")
            rows.append(r)
    tex_table("tab3.tex", "Skill added between nested arms. MSE and MAE reduction (\\%, MAE with 95\\,\\% well-clustered interval), test "
              "campaigns in which the richer arm has lower MAE with a two-sided sign test, and MSE reduction under an alternative "
              "split and spatially blocked validation.", "tab:gains",
              ["Comparison", "Horizon", "MSE", "MAE", "Campaigns", "Sign $p$", "Alt. split", "Unseen regions"], rows, "llrrrrrr")

    # Table 4: calibration
    cov = pd.read_csv(CALIBRATION_REPORTS_DIR / "coverage.csv")
    rows = []
    for m in ["Gaussian", "Split conformal", "Mondrian D×S", "Mondrian D×R", "Normalised", "CQR", "Mondrian D×R + recal",
              "Mondrian D×R + recal + ACI", "Mondrian D×R×S + recal + ACI", "Normalised D×R×S + recal + ACI"]:
        r = [m.replace("×", r"$\times$") + (r"$^\dagger$" if "×S + recal" in m else "")]
        for h in (1, 2, 4):
            al = cov[(cov["method"] == m) & (cov["h"] == h) & (cov["nominal"] == 0.8) & (cov["group_var"] == "All")].iloc[0]
            g = cov[(cov["method"] == m) & (cov["h"] == h) & cov["nominal"].isin([0.8, 0.9]) & cov["group_var"].isin(["Depth", "Region"])]
            r += [f(al["coverage"] * 100, 1), f((g["coverage"] - g["nominal"]).abs().max() * 100, 1), f(al["winkler"], 2)]
        rows.append(r)
    tex_table("tab4.tex", "Interval calibration in the test period: overall coverage of the 80\\,\\% interval (\\%), the worst absolute "
              "deviation from nominal over depth and region classes at 80\\,\\% and 90\\,\\% (points), and the Winkler score (m).",
              "tab:calib", ["Method", "Cov.", "Worst", "Winkler", "Cov.", "Worst", "Winkler", "Cov.", "Worst", "Winkler"], rows,
              "lrrrrrrrrr", note="Column groups: 3, 6 and 12 months. $^\\dagger$ Added after inspecting results (post hoc).")

    # Table 5: decision value
    sc = pd.read_json(DECISION_REPORTS_DIR / "scores.json")
    sc = sc[(sc["probability"] == "rolling isotonic") & (sc["arm"] == "M2 + ENSO/IOD")]
    vc = pd.read_csv(DECISION_REPORTS_DIR / "value_curves.csv")
    vc = vc[(vc["probability"] == "rolling isotonic") & (vc["arm"] == "M2 + ENSO/IOD")]
    rows = []
    names = {"E1": "Deeper than usual", "E2": "SGI $<-1$", "E3": "Below 8 m"}
    for ev in ("E1", "E2", "E3"):
        for h in (1, 2, 4):
            s = sc[(sc["event_id"] == ev) & (sc["h"] == h)].iloc[0]
            v = vc[(vc["event_id"] == ev) & (vc["h"] == h)]
            vmax = v.loc[v["value"].idxmax()]
            rows.append([names[ev] if h == 1 else "", H_LABEL[h], f(s["event_rate"], 2), f"{f(s['bss'])} [{f(s['bss_ci'][0])}, {f(s['bss_ci'][1])}]",
                         f(s["roc_auc"], 2), f(vmax["value"], 2), f(vmax["alpha"], 2),
                         f"{v[v['value'] > 0]['alpha'].min():.2f}--{v[v['value'] > 0]['alpha'].max():.2f}"])
    tex_table("tab5.tex", "Warning skill and value for model M2 with rolling-isotonic probabilities: event base rate, Brier skill score "
              "against each well's climatology (95\\,\\% interval), ROC AUC, peak relative economic value and the cost--loss ratio at "
              "which it occurs, and the range of cost--loss ratios with positive value.", "tab:value",
              ["Event", "Horizon", "Base rate", "BSS", "AUC", "$V_{\\max}$", "at $C/L$", "$V>0$ for $C/L$"], rows, "llrrrrrr")


# ── Numbers quoted in the text ──────────────────────────────────────────────

def numbers():
    cat = pd.read_parquet(DATA_PROCESSED_DIR / "station_catalog.parquet")
    camp = pd.read_parquet(DATA_PROCESSED_DIR / "gwl_campaigns.parquet")
    dm = pd.read_csv(SKILL_REPORTS_DIR / "diebold_mariano.csv").set_index(["h", "a", "b"])
    cov = pd.read_csv(CALIBRATION_REPORTS_DIR / "coverage.csv")
    vc = pd.read_csv(DECISION_REPORTS_DIR / "value_curves.csv")
    vc = vc[vc["probability"] == "rolling isotonic"]
    trig = pd.read_csv(DECISION_REPORTS_DIR / "triggers.csv")
    trig = trig[(trig["probability"] == "rolling isotonic") & (trig["arm"] == "M2 + ENSO/IOD")]
    sanity = json.loads((FORCING_REPORTS_DIR / "sanity.json").read_text())
    boot = {(b["h"], b["model"]): b for b in json.loads((SKILL_REPORTS_DIR / "bootstrap.json").read_text()) if b["stat"] == "skill_vs_persistence"}

    def split_cov(group, h=1):
        return cov[(cov["method"] == "Split conformal") & (cov["h"] == h) & (cov["nominal"] == 0.8) & (cov["group"] == group)]["coverage"].iloc[0]

    aci = cov[(cov["method"] == "Mondrian D×R + recal + ACI") & cov["nominal"].isin([0.8, 0.9]) & cov["group_var"].isin(["Depth", "Region"])]
    aci_worst = {h: (g["coverage"] - g["nominal"]).abs().max() * 100 for h, g in aci.groupby("h")}
    v = lambda h, ev, a, al: vc[(vc["h"] == h) & (vc["event_id"] == ev) & (vc["arm"] == a) & (vc["alpha"] == al)].iloc[0]  # noqa: E731
    t = lambda h, ev, tr: trig[(trig["h"] == h) & (trig["event_id"] == ev) & (trig["trigger"] == tr)].iloc[0]  # noqa: E731
    g6 = dm.loc[(2, "M0 memory", "M2 + ENSO/IOD")]
    vmax = lambda ev, h: vc[(vc["event_id"] == ev) & (vc["h"] == h) & (vc["arm"] == "M2 + ENSO/IOD")]["value"].max()  # noqa: E731
    oracle = [dm.loc[(h, "M2 + ENSO/IOD", "M3 + oracle rain")]["mse_reduction"] * 100 for h in (1, 2, 4)]
    N = {
        "nStations": f"{len(cat):,}", "nManual": f"{(cat['network'] == 'manual').sum():,}",
        "nDWLR": f"{(cat['network'] == 'DWLR').sum():,}", "nObs": f"{int(cat['n_obs'].sum()):,}",
        "nCampaigns": f"{len(camp):,}", "nCampaignWells": f"{camp['well_id'].nunique():,}",
        "snapMedian": f"{sanity['snapshot_vs_imd_12m']['median_snap_cum4_mm']:.1f}",
        "imdMedian": f"{sanity['snapshot_vs_imd_12m']['median_imd_rain_12m_mm']:,.0f}",
        "rechargeShare": f"{sanity['recharge_vs_jjas']['share_positive'] * 100:.0f}",
        "skillMzeroThree": f"{boot[(1, 'M0 memory')]['estimate']:.2f}", "skillMzeroSix": f"{boot[(2, 'M0 memory')]['estimate']:.2f}",
        "skillMzeroTwelve": f"{boot[(4, 'M0 memory')]['estimate']:.2f}",
        "gainSixMSE": f"{g6['mse_reduction'] * 100:.1f}", "gainSixMAE": f"{g6['mae_reduction'] * 100:.1f}",
        "gainSixWins": f"{int(g6['campaigns_b_better'])}", "gainSixCampaigns": f"{int(g6['campaigns'])}",
        "oracleMin": f"{min(oracle):.1f}", "oracleMax": f"{max(oracle):.1f}",  # main split only
        "oracleRobustMin": f"{min(o * 100 for o in pd.read_csv(SKILL_REPORTS_DIR / 'robustness.csv').query('a == \"M2 + ENSO/IOD\" and b == \"M3 + oracle rain\"')['mse_reduction']):.1f}",
        "splitShallow": f"{split_cov('< 5 m') * 100:.0f}", "splitDeep": f"{split_cov('≥ 40 m') * 100:.0f}",
        "aciWorstThree": f"{aci_worst[1]:.1f}", "aciWorstSix": f"{aci_worst[2]:.1f}", "aciWorstTwelve": f"{aci_worst[4]:.2f}",
        "vmaxEoneThree": f"{vmax('E1', 1):.2f}", "vmaxEthreeSix": f"{vmax('E3', 2):.2f}",
        "valEoneThreeTrig": f"{v(1, 'E1', 'M2 + ENSO/IOD', 0.3)['value']:.2f}",
        "hitEoneThree": f"{t(1, 'E1', 0.3)['hit_rate'] * 100:.0f}", "farEoneThree": f"{t(1, 'E1', 0.3)['false_alarm_ratio'] * 100:.0f}",
        "hitEthreeSix": f"{t(2, 'E3', 0.2)['hit_rate'] * 100:.0f}", "farEthreeSix": f"{t(2, 'E3', 0.2)['false_alarm_ratio'] * 100:.0f}",
        "valEthreeSixTrig": f"{v(2, 'E3', 'M2 + ENSO/IOD', 0.2)['value']:.2f}",
    }
    PAPER.mkdir(parents=True, exist_ok=True)
    lines = ["% Generated by src/research/paper_figures.py — do not edit by hand."]
    lines += [f"\\newcommand{{\\{k}}}{{{val}}}" for k, val in N.items()]
    (PAPER / "numbers.tex").write_text("\n".join(lines) + "\n")
    return N


def run_paper_figures():
    print("=== Phase 6.1: publication figures and tables ===")
    for fn in (fig1_study_area, fig2_forcing_checks, fig3_skill, fig4_strata, fig5_coverage, fig6_drift, fig7_reliability, fig8_value):
        fn()
        print(f"  {fn.__name__}")
    tables()
    N = numbers()
    print(f"Saved 8 figures, 5 tables and {len(N)} number macros to {PAPER}/")


if __name__ == "__main__":
    run_paper_figures()
