"""Community-recap reports: executive summary, stat tiles, category
leaderboards, awards, correlation analysis and relationship charts — built
from our own comp data, modeled on community-style Egg Day recaps.

Unlike the multi-year recaps some community tools produce, this DB only
holds a single before/after snapshot for the current competition — there is
no cross-year historical comparison here.
"""

import math
import textwrap

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import FancyBboxPatch

from reports.final import _competitor_scores, _save, _ORANGE, _OUT_DIR
from web.filters import fmt_mag as _format_se

# Approximate Egg Inc Earnings-Bonus role ladder: each named tier spans 3
# powers of ten (I/II/III sub-tiers), Farmer=rank 0 up through Venda. This is
# derived purely from EB magnitude (floor(log10(eb)), //3 for tier, %3 for
# sub-tier) since the exact in-game breakpoints aren't stored in our schema —
# it lines up with known examples (e.g. Giga II -> Wecca II = +21 sub-tiers).
_ROLE_TIER_NAMES = ["Farmer", "Kilo", "Mega", "Giga", "Tera", "Peta", "Exa",
                    "Zetta", "Yotta", "Xenna", "Wecca", "Venda"]
_SUB_LABELS = ["I", "II", "III"]


def _role_rank_index(eb) -> int:
    if eb is None or pd.isna(eb) or eb <= 0:
        return 0
    return max(0, int(np.floor(np.log10(eb))))


def _role_label(eb) -> str:
    idx = _role_rank_index(eb)
    major = min(idx // 3, len(_ROLE_TIER_NAMES) - 1)
    sub = idx % 3
    return f"{_ROLE_TIER_NAMES[major]} {_SUB_LABELS[sub]}"


def _gini(values: pd.Series) -> float:
    """Standard discrete Gini coefficient; negative values clipped to 0
    (can't hold a negative share of gains)."""
    x = np.sort(values.clip(lower=0).to_numpy(dtype=float))
    n = len(x)
    total = x.sum()
    if n == 0 or total == 0:
        return 0.0
    idx = np.arange(1, n + 1)
    return float((2 * np.sum(idx * x) - (n + 1) * total) / (n * total))


def _prepped() -> pd.DataFrame:
    """Registered competitors with role tiers + advancement attached."""
    scores = _competitor_scores()
    if scores.empty:
        return scores
    scores = scores.copy()
    scores["role_start_rank"] = scores["eb_start"].apply(_role_rank_index)
    scores["role_end_rank"] = scores["eb_end"].apply(_role_rank_index)
    scores["role_advance"] = scores["role_end_rank"] - scores["role_start_rank"]
    scores["role_start_label"] = scores["eb_start"].apply(_role_label)
    scores["role_end_label"] = scores["eb_end"].apply(_role_label)
    scores["role_major_start"] = (scores["role_start_rank"] // 3).clip(
        upper=len(_ROLE_TIER_NAMES) - 1)
    return scores


def _table_image(display: pd.DataFrame, title: str, path: str) -> str:
    sns.set(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, max(3, len(display) * 0.4 + 1.2)))
    fig.patch.set_visible(False)
    ax.axis("off")
    ax.set_title(title, fontsize=16, weight="bold", pad=20)

    table = ax.table(cellText=display.values, colLabels=display.columns,
                      cellLoc="center", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)

    cell_dict = table.get_celld()
    for i, col in enumerate(display.columns):
        max_len = max(display[col].astype(str).map(len).max(), len(col))
        for j in range(len(display) + 1):
            cell_dict[j, i].set_width(0.05 + 0.012 * max_len)

    for (i, j), cell in cell_dict.items():
        cell.set_edgecolor("black")
        if i == 0:
            cell.set_text_props(weight="bold", color="white")
            cell.set_facecolor(_ORANGE)
        else:
            cell.set_facecolor("#F9EBC8" if i % 2 == 0 else "#FFF4EB")

    return _save(fig, path)


def _tile_grid(tiles: list[tuple[str, str]], title: str, path: str) -> str:
    cols = 4
    rows = math.ceil(len(tiles) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(3.2 * cols, 2.2 * rows + 1))
    fig.suptitle(title, fontsize=18, weight="bold", y=0.98)
    axes = np.array(axes).reshape(rows, cols)
    palette = sns.color_palette("husl", len(tiles))

    for ax, (value, label), color in zip(axes.flat, tiles, palette):
        ax.axis("off")
        ax.add_patch(FancyBboxPatch((0.03, 0.08), 0.94, 0.84, boxstyle="round,pad=0.02",
                                    linewidth=1, edgecolor="#ddd", facecolor="#FAFAFA",
                                    transform=ax.transAxes))
        ax.text(0.5, 0.62, value, ha="center", va="center", fontsize=19,
                weight="bold", color=color, transform=ax.transAxes)
        ax.text(0.5, 0.28, label, ha="center", va="center", fontsize=9.5,
                color="#555", transform=ax.transAxes)
    for ax in axes.flat[len(tiles):]:
        ax.axis("off")

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    return _save(fig, path)


def _award_grid(awards: list[tuple[str, str, str]], path: str) -> str:
    cols = 2
    rows = math.ceil(len(awards) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(6.5 * cols, 1.9 * rows + 1))
    fig.suptitle("Community Awards", fontsize=18, weight="bold", y=0.99)
    axes = np.array(axes).reshape(rows, cols)

    for ax, (title, name, blurb) in zip(axes.flat, awards):
        ax.axis("off")
        ax.add_patch(FancyBboxPatch((0.02, 0.06), 0.96, 0.88, boxstyle="round,pad=0.02",
                                    linewidth=1, edgecolor="#ddd", facecolor="#FAFAFA",
                                    transform=ax.transAxes))
        ax.text(0.06, 0.82, title, fontsize=13, weight="bold", color=_ORANGE,
                transform=ax.transAxes, va="top")
        ax.text(0.06, 0.60, name, fontsize=12, weight="bold",
                transform=ax.transAxes, va="top")
        wrapped = "\n".join(textwrap.wrap(blurb, width=50))
        ax.text(0.06, 0.44, wrapped, fontsize=9.5, color="#444",
                transform=ax.transAxes, va="top")
    for ax in axes.flat[len(awards):]:
        ax.axis("off")

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return _save(fig, path)


def generate_stats_tiles_image(path: str | None = None) -> str | None:
    scores = _prepped()
    if scores.empty:
        print("[report] no competitor data — skipping stats tiles image")
        return None
    active = scores[scores["prestiges_gain"] > 0]

    tiles = [
        (f"{len(active):,}", "Active Players"),
        (_format_se(active["se_gain"].sum()) if not active.empty else "—", "Soul Eggs Gained"),
        (f"{int(active['prestiges_gain'].sum()):,}" if not active.empty else "0", "Total Prestiges"),
        (f"{int((scores['role_advance'] > 0).sum()):,}", "Promotions"),
        (f"{active['se_gain_pct'].median():.1f}%" if not active.empty else "—", "Median SE Growth"),
        (f"{int(active['prestiges_gain'].median())}" if not active.empty else "—", "Median Prestiges"),
        (f"{int(active['te_gain'].sum()):,}" if not active.empty else "0", "Truth Eggs Earned"),
        (f"{_gini(active['se_gain']):.2f}" if not active.empty else "—", "Gini (Inequality)"),
    ]
    return _tile_grid(tiles, "Competition Stats", path or f"{_OUT_DIR}/community_stats_tiles.png")


def generate_exec_summary_image(path: str | None = None) -> str | None:
    scores = _prepped()
    if scores.empty:
        print("[report] no competitor data — skipping exec summary image")
        return None
    active = scores[scores["prestiges_gain"] > 0]
    if active.empty:
        print("[report] no active players — skipping exec summary image")
        return None

    tracked = len(scores)
    n_active = len(active)
    turnout = n_active / tracked * 100 if tracked else 0
    se_gained = active["se_gain"].sum()
    total_start = active["se_start"].sum()
    total_end = active["se_end"].sum()
    pool_mult = total_end / total_start if total_start else float("nan")
    gini = _gini(active["se_gain"])

    top_gain = active.sort_values("se_gain", ascending=False).iloc[0]
    top_prestige = active.sort_values("prestiges_gain", ascending=False).iloc[0]
    top_climb = scores.sort_values("role_advance", ascending=False).iloc[0]

    sorted_gain = active["se_gain"].clip(lower=0).sort_values(ascending=False)
    total_gain_pos = sorted_gain.sum()

    def _top_pct_share(pct: float) -> float:
        k = max(1, int(len(sorted_gain) * pct))
        return sorted_gain.iloc[:k].sum() / total_gain_pos * 100 if total_gain_pos else 0.0

    top5, top10 = _top_pct_share(0.05), _top_pct_share(0.10)

    summary = (
        f"The competition tracked {tracked:,} registered players; {n_active:,} ({turnout:.0f}%) "
        f"gained at least one prestige. Together they added {_format_se(se_gained)} Soul Eggs. "
        f"The typical active player finished with a {active['se_gain_pct'].median():.0f}% gain "
        f"over {int(active['prestiges_gain'].median())} prestiges. Gains were concentrated: the "
        f"top 5% of active players accounted for {top5:.0f}% of all Soul Eggs gained, and the top "
        f"10% accounted for {top10:.0f}% (Gini {gini:.2f})."
    )

    highlights = [
        ("Community SE gained", _format_se(se_gained)),
        ("Active-player SE pool grew", f"{pool_mult:.2f}x ({_format_se(total_start)} -> {_format_se(total_end)})"),
        ("Biggest single gain", f"{top_gain['ei_name']}, +{_format_se(top_gain['se_gain'])} SE"),
        ("Most prestiges", f"{top_prestige['ei_name']}, {int(top_prestige['prestiges_gain'])} prestiges"),
        ("Biggest role advancement",
         f"{top_climb['ei_name']}, +{int(top_climb['role_advance'])} tiers "
         f"({top_climb['role_start_label']} -> {top_climb['role_end_label']})"),
        ("Truth Eggs earned",
         f"{int(active['te_gain'].sum()):,} across {int((active['te_gain'] > 0).sum())} players"),
        ("Concentration", f"top 5% = {top5:.0f}%, top 10% = {top10:.0f}% of all gains"),
    ]

    sns.set(style="whitegrid")
    fig = plt.figure(figsize=(9.5, 2.6 + 0.5 * len(highlights)))
    fig.suptitle("Executive Summary", fontsize=16, weight="bold", x=0.02, ha="left", y=0.98)
    wrapped = "\n".join(textwrap.wrap(summary, width=100))
    fig.text(0.02, 0.90, wrapped, fontsize=10, va="top")

    ax = fig.add_axes([0.02, 0.03, 0.96, 0.45])
    ax.axis("off")
    table = ax.table(cellText=highlights, colLabels=["Metric", "Result"],
                      cellLoc="left", loc="center", colWidths=[0.32, 0.68])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.7)
    for (i, j), cell in table.get_celld().items():
        cell.set_edgecolor("black")
        if i == 0:
            cell.set_text_props(weight="bold", color="white")
            cell.set_facecolor(_ORANGE)
        else:
            cell.set_facecolor("#F9EBC8" if i % 2 == 0 else "#FFF4EB")
            if j == 0:
                cell.set_text_props(weight="bold")

    return _save(fig, path or f"{_OUT_DIR}/community_exec_summary.png")


def generate_leaderboard_categories(limit: int = 12) -> list[str]:
    scores = _prepped()
    if scores.empty:
        print("[report] no competitor data — skipping category leaderboards")
        return []
    active = scores[scores["prestiges_gain"] > 0].copy()
    paths = []

    top_gain = active.sort_values("se_gain", ascending=False).head(limit)
    if not top_gain.empty:
        disp = pd.DataFrame({
            "#": range(1, len(top_gain) + 1),
            "Player": top_gain["ei_name"],
            "SE Gained": top_gain["se_gain"].apply(_format_se),
            "Prestiges": top_gain["prestiges_gain"].astype(int),
        })
        paths.append(_table_image(disp, "Largest Total Soul Egg Gain",
                                  f"{_OUT_DIR}/community_top_se_gain.png"))

    top_prestige = active.sort_values("prestiges_gain", ascending=False).head(limit)
    if not top_prestige.empty:
        disp = pd.DataFrame({
            "#": range(1, len(top_prestige) + 1),
            "Player": top_prestige["ei_name"],
            "Prestiges": top_prestige["prestiges_gain"].astype(int),
            "SE Gained": top_prestige["se_gain"].apply(_format_se),
        })
        paths.append(_table_image(disp, "Most Prestiges",
                                  f"{_OUT_DIR}/community_top_prestiges.png"))

    eff = active[active["prestiges_gain"] > 0].copy()
    eff["gain_per_prestige"] = eff["se_gain"] / eff["prestiges_gain"]
    eff = eff.sort_values("gain_per_prestige", ascending=False).head(limit)
    if not eff.empty:
        disp = pd.DataFrame({
            "#": range(1, len(eff) + 1),
            "Player": eff["ei_name"],
            "SE / Prestige": eff["gain_per_prestige"].apply(_format_se),
            "Prestiges": eff["prestiges_gain"].astype(int),
        })
        paths.append(_table_image(disp, "Highest Gain Per Prestige (Efficiency)",
                                  f"{_OUT_DIR}/community_efficiency.png"))

    te = scores[scores["te_gain"] > 0].sort_values("te_gain", ascending=False).head(limit)
    if not te.empty:
        disp = pd.DataFrame({
            "#": range(1, len(te) + 1),
            "Player": te["ei_name"],
            "Truth Eggs": te["te_gain"].astype(int),
            "Prestiges": te["prestiges_gain"].astype(int),
        })
        paths.append(_table_image(disp, "Most Truth Eggs Earned",
                                  f"{_OUT_DIR}/community_top_truth_eggs.png"))

    growth = active[active["se_start"] > 0].sort_values("se_gain_pct", ascending=False).head(limit)
    if not growth.empty:
        disp = pd.DataFrame({
            "#": range(1, len(growth) + 1),
            "Player": growth["ei_name"],
            "Growth %": growth["se_gain_pct"].apply(lambda v: f"{v:,.1f}%"),
            "SE Start -> End": growth.apply(
                lambda r: f"{_format_se(r['se_start'])} -> {_format_se(r['se_end'])}", axis=1),
        })
        paths.append(_table_image(disp, "Largest Percentage Growth",
                                  f"{_OUT_DIR}/community_top_growth_pct.png"))

    return paths


def generate_awards_image(path: str | None = None) -> str | None:
    scores = _prepped()
    if scores.empty:
        print("[report] no competitor data — skipping awards image")
        return None
    active = scores[scores["prestiges_gain"] > 0].copy()
    if active.empty:
        print("[report] no active players — skipping awards image")
        return None

    eff = active[active["prestiges_gain"] > 0].copy()
    eff["gain_per_prestige"] = eff["se_gain"] / eff["prestiges_gain"]

    titan = active.sort_values("se_gain", ascending=False).iloc[0]
    machine = active.sort_values("prestiges_gain", ascending=False).iloc[0]
    leap = active.sort_values("se_gain_pct", ascending=False).iloc[0]
    efficiency = eff.sort_values("gain_per_prestige", ascending=False).iloc[0]
    climber = scores.sort_values("role_advance", ascending=False).iloc[0]
    truth = scores.sort_values("te_gain", ascending=False).iloc[0]

    low_cut = max(1, eff["prestiges_gain"].quantile(0.25))
    hidden_pool = eff[eff["prestiges_gain"] <= low_cut]
    hidden_gem = (hidden_pool.sort_values("gain_per_prestige", ascending=False).iloc[0]
                 if not hidden_pool.empty else efficiency)

    backslide = scores[scores["se_gain"] < 0].sort_values("se_gain")

    awards = [
        ("Soul Egg Titan", titan["ei_name"],
         f"Added {_format_se(titan['se_gain'])} SE, the largest single gain in the competition."),
        ("Prestige Machine", machine["ei_name"],
         f"{int(machine['prestiges_gain'])} prestiges completed, the most of anyone."),
        ("Biggest Leap", leap["ei_name"],
         f"+{leap['se_gain_pct']:,.0f}% growth ({_format_se(leap['se_start'])} -> {_format_se(leap['se_end'])})."),
        ("Efficiency King", efficiency["ei_name"],
         f"{_format_se(efficiency['gain_per_prestige'])} SE per prestige over "
         f"{int(efficiency['prestiges_gain'])} prestiges."),
        ("Role Climber", climber["ei_name"],
         f"+{int(climber['role_advance'])} role tiers "
         f"({climber['role_start_label']} -> {climber['role_end_label']})."),
        ("Hidden Gem", hidden_gem["ei_name"],
         f"{_format_se(hidden_gem['gain_per_prestige'])} SE per prestige from just "
         f"{int(hidden_gem['prestiges_gain'])} prestiges."),
        ("Most Truth Eggs", truth["ei_name"], f"+{int(truth['te_gain'])} Truth Eggs earned."),
    ]
    if not backslide.empty:
        b = backslide.iloc[0]
        awards.append(("Biggest Surprise", b["ei_name"],
                       f"Finished down {_format_se(abs(b['se_gain']))} SE."))

    return _award_grid(awards, path or f"{_OUT_DIR}/community_awards.png")


def generate_correlation_image(path: str | None = None) -> str | None:
    scores = _prepped()
    if scores.empty:
        print("[report] no competitor data — skipping correlation image")
        return None

    df = pd.DataFrame({
        "log_se_start": np.log10(scores["se_start"].clip(lower=1)),
        "log_se_gain": np.log10(scores["se_gain"].clip(lower=1)),
        "growth_pct": scores["se_gain_pct"],
        "prestiges": scores["prestiges_gain"],
        "eb_gain_pct": scores["eb_gain_pct"],
        "te_gain": scores["te_gain"],
        "mer_gain": scores["mer_gain"],
        "role_advance": scores["role_advance"],
    })
    corr = df.corr(numeric_only=True)

    sns.set(style="white")
    fig, ax = plt.subplots(figsize=(9, 7))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0,
               vmin=-1, vmax=1, ax=ax, cbar_kws={"label": "Pearson r"})
    ax.set_title("Correlation Matrix", fontsize=16, weight="bold")
    fig.tight_layout()

    return _save(fig, path or f"{_OUT_DIR}/community_correlation.png")


def generate_relationship_charts() -> list[str]:
    scores = _prepped()
    if scores.empty:
        print("[report] no competitor data — skipping relationship charts")
        return []
    paths = []

    sns.set(style="whitegrid")
    fig, ax = plt.subplots(figsize=(8, 7))
    sc = ax.scatter(scores["se_start"].clip(lower=1), scores["se_end"].clip(lower=1),
                    c=scores["prestiges_gain"], cmap="viridis", s=20, alpha=0.75)
    lo = min(scores["se_start"].clip(lower=1).min(), scores["se_end"].clip(lower=1).min())
    hi = max(scores["se_start"].max(), scores["se_end"].max())
    ax.plot([lo, hi], [lo, hi], "--", color="grey", linewidth=1, label="y = x (no change)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Starting Soul Eggs (log scale)")
    ax.set_ylabel("Ending Soul Eggs (log scale)")
    ax.set_title("Starting vs Ending Soul Eggs", fontsize=16, weight="bold")
    ax.legend(loc="upper left")
    fig.colorbar(sc, ax=ax, label="Prestiges completed")
    paths.append(_save(fig, f"{_OUT_DIR}/community_start_vs_end.png"))

    active = scores[scores["prestiges_gain"] > 0]
    if not active.empty:
        fig, ax = plt.subplots(figsize=(8, 6))
        x = active["prestiges_gain"].to_numpy(dtype=float)
        y = active["se_gain"].clip(lower=1).to_numpy(dtype=float)
        ax.scatter(x, y, s=15, alpha=0.6, color=_ORANGE)
        ax.set_yscale("log")
        log_y = np.log10(y)
        r = np.corrcoef(x, log_y)[0, 1] if len(x) > 1 else 0.0
        if len(x) > 1:
            coeffs = np.polyfit(x, log_y, 1)
            xs = np.linspace(x.min(), x.max(), 100)
            ax.plot(xs, 10 ** (coeffs[0] * xs + coeffs[1]), color="crimson",
                   label=f"Regression (r = {r:.2f})")
            ax.legend()
        ax.set_xlabel("Prestiges completed")
        ax.set_ylabel("Soul Eggs gained (log scale)")
        ax.set_title("Prestiges vs Soul Egg Gain", fontsize=16, weight="bold")
        paths.append(_save(fig, f"{_OUT_DIR}/community_prestiges_vs_gain.png"))

    gains = active["se_gain"].clip(lower=0).sort_values().to_numpy(dtype=float)
    if gains.sum() > 0:
        cum = np.cumsum(gains) / gains.sum() * 100
        pct_players = np.linspace(0, 100, len(cum))
        fig, ax = plt.subplots(figsize=(8, 7))
        ax.plot(pct_players, cum, color="seagreen", linewidth=2, label="Lorenz curve (SE gains)")
        ax.plot([0, 100], [0, 100], "--", color="grey", label="Perfect equality")
        ax.fill_between(pct_players, cum, alpha=0.15, color="seagreen")
        ax.set_xlabel("Cumulative % of players (poorest -> richest gain)")
        ax.set_ylabel("Cumulative % of total SE gained")
        ax.set_title(f"Concentration of Gains (Gini = {_gini(active['se_gain']):.2f})",
                    fontsize=16, weight="bold")
        ax.legend(loc="upper left")
        paths.append(_save(fig, f"{_OUT_DIR}/community_lorenz.png"))

    if not active.empty:
        role_df = active.copy()
        role_df["tier_name"] = role_df["role_major_start"].apply(
            lambda i: _ROLE_TIER_NAMES[int(i)])
        order = [t for t in _ROLE_TIER_NAMES if t in role_df["tier_name"].unique()]
        if order:
            fig, ax = plt.subplots(figsize=(9, 6))
            sns.boxplot(x=role_df["tier_name"], y=role_df["se_gain"].clip(lower=1),
                       order=order, hue=role_df["tier_name"], palette="husl",
                       legend=False, ax=ax)
            ax.set_yscale("log")
            ax.set_xlabel("Starting role tier")
            ax.set_ylabel("Soul Eggs gained (log scale)")
            ax.set_title("Soul Egg Gains by Starting Role Tier", fontsize=16, weight="bold")
            paths.append(_save(fig, f"{_OUT_DIR}/community_role_boxplot.png"))

    return paths


def generate_all() -> list[str]:
    paths = []
    for p in (generate_stats_tiles_image(), generate_exec_summary_image()):
        if p:
            paths.append(p)
    paths += generate_leaderboard_categories()
    p = generate_awards_image()
    if p:
        paths.append(p)
    p = generate_correlation_image()
    if p:
        paths.append(p)
    paths += generate_relationship_charts()
    return paths
