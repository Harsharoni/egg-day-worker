"""Final-results reports: Discord-postable PNGs for guild standings, the
overall leaderboard, and the guild score race, generated once the
competition is over."""

import os

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from config import COMP_START_UTC, COMP_END_UTC, FAIR_POWER, GUILD_FAIR_POWER, REPORT_LIMIT
from db import load_start_snapshot, load_participants, load_history, snapshot_at
from processors.guilds import compute_guild_standings, guild_key
from processors.participants import apply_participants
from processors.scoring import compute_scores
from web.filters import fmt_mag as _format_se

_ORANGE = "#F28A02"
_OUT_DIR = "gains"


def _final_scores() -> pd.DataFrame:
    """Every tracked player scored against the frozen comp-end snapshot,
    guild attached where registered (guild="" otherwise)."""
    start = load_start_snapshot()
    end = snapshot_at(COMP_END_UTC)
    scores = compute_scores(start, end)
    return apply_participants(scores, load_participants(), filter_unmatched=False)


def _competitor_scores() -> pd.DataFrame:
    """Registered comp participants only (matched to a leaderboard row),
    re-ranked — the actual competition population, for summary stats."""
    start = load_start_snapshot()
    end = snapshot_at(COMP_END_UTC)
    scores = compute_scores(start, end)
    return apply_participants(scores, load_participants(), filter_unmatched=True)


def _save(fig, path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, bbox_inches="tight", dpi=90)
    plt.close(fig)
    print(f"[report] saved {path}")
    return path


def generate_guild_standings_image(path: str | None = None) -> str | None:
    """Ranked horizontal bar chart of final guild scores."""
    guilds = compute_guild_standings(_final_scores())
    if guilds.empty:
        print("[report] no guild data — skipping guild standings image")
        return None

    guilds = guilds.sort_values("guild_score", ascending=True)

    sns.set(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, max(4, len(guilds) * 0.5 + 1)))
    bars = ax.barh(guilds["guild"], guilds["guild_score"], color=_ORANGE)
    ax.bar_label(bars, labels=[f"{v:,}" for v in guilds["guild_score"]], padding=4)
    ax.set_xlabel("Guild Score")
    ax.set_title("Final Guild Standings", fontsize=16, weight="bold")
    ax.margins(x=0.12)
    fig.tight_layout()

    return _save(fig, path or f"{_OUT_DIR}/final_guild_standings.png")


def generate_leaderboard_image(limit: int = REPORT_LIMIT, path: str | None = None) -> str | None:
    """Ranked table image of the top `limit` players by final score."""
    scores = _final_scores().head(limit)
    if scores.empty:
        print("[report] no score data — skipping leaderboard image")
        return None

    display = pd.DataFrame({
        "#":        scores["rank"],
        "Player":   scores["ei_name"],
        "Guild":    scores["guild"].replace("", "—"),
        "Start SE": scores["se_start"].apply(_format_se),
        "End SE":   scores["se_end"].apply(_format_se),
        "SE Gain":  scores["se_gain"].apply(_format_se),
        "Score":    scores["score"].apply(lambda v: f"{int(v):,}"),
    })

    sns.set(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, max(4, len(display) * 0.35 + 1)))
    fig.patch.set_visible(False)
    ax.axis("off")
    ax.set_title("Final Leaderboard", fontsize=16, weight="bold", pad=20)

    table = ax.table(cellText=display.values, colLabels=display.columns,
                      cellLoc="center", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)

    cell_dict = table.get_celld()
    for i, col in enumerate(display.columns):
        max_len = max(display[col].astype(str).map(len).max(), len(col))
        for j in range(len(display) + 1):
            cell_dict[j, i].set_width(0.06 + 0.012 * max_len)

    for (i, j), cell in cell_dict.items():
        cell.set_edgecolor("black")
        if i == 0:
            cell.set_text_props(weight="bold", color="white")
            cell.set_facecolor(_ORANGE)
        else:
            cell.set_facecolor("#F9EBC8" if i % 2 == 0 else "#FFF4EB")

    return _save(fig, path or f"{_OUT_DIR}/final_leaderboard.png")


def _guild_score_history() -> pd.DataFrame:
    """Per-poll, per-player score across the comp with guild attached —
    same math as web/service.py get_score_history, standalone so reports/
    doesn't depend on web/."""
    hist = load_history(COMP_START_UTC, COMP_END_UTC)
    start = load_start_snapshot()
    if hist.empty or start.empty:
        return pd.DataFrame(columns=["timestamp", "discord_id", "ei_name", "guild", "score"])

    hist = hist.copy()
    hist["timestamp"] = pd.to_datetime(hist["timestamp"], utc=True)

    base = start[["discord_id", "ei_name", "soul_eggs", "earnings_bonus"]]
    base = base.rename(columns={"soul_eggs": "se_start", "earnings_bonus": "eb_start"})
    max_eb = start["earnings_bonus"].max()

    df = hist.merge(base, on=["discord_id", "ei_name"], how="inner")
    avg_eb = (df["eb_start"] + df["earnings_bonus"]) / 2
    avg_eb = avg_eb.where(df["earnings_bonus"] != 0, df["eb_start"])
    fair = (max_eb / avg_eb) ** FAIR_POWER
    df["score"] = ((df["soul_eggs"] - df["se_start"]) * fair / 1e18).round()

    guilds = _final_scores()[["discord_id", "ei_name", "guild"]].copy()
    guilds["ei_l"] = guilds["ei_name"].str.lower()
    df["ei_l"] = df["ei_name"].str.lower()
    df = df.merge(guilds[["discord_id", "ei_l", "guild"]], on=["discord_id", "ei_l"], how="left")
    df["guild"] = df["guild"].fillna("")
    df = df[df["guild"].map(guild_key) != ""]
    return df[["timestamp", "discord_id", "ei_name", "guild", "score"]]


def _guild_score_over_time(member_scores: pd.DataFrame) -> pd.Series:
    """member_scores: index=timestamp, columns=(discord_id, ei_name) -> score,
    for a single guild's members."""
    active = (member_scores > 0).sum(axis=1)
    n = active.where(active > 0, member_scores.notna().sum(axis=1)).clip(lower=1)
    return (member_scores.sum(axis=1) / n ** GUILD_FAIR_POWER).round()


def generate_score_race_image(path: str | None = None) -> str | None:
    """Static line chart: guild score over time, one line per guild —
    frozen recap of the live site's guild race chart."""
    df = _guild_score_history()
    standings = compute_guild_standings(_final_scores())
    if df.empty or standings.empty:
        print("[report] no guild history — skipping score race image")
        return None

    df = df.assign(gkey=df["guild"].map(guild_key))

    sns.set(style="whitegrid")
    fig, ax = plt.subplots(figsize=(11, 6))
    palette = sns.color_palette("husl", len(standings))

    for color, g in zip(palette, standings.itertuples()):
        rows = df[df["gkey"] == g.guild_key]
        if rows.empty:
            continue
        pivot = rows.pivot_table(index="timestamp", values="score",
                                 columns=["discord_id", "ei_name"]).ffill()
        series = _guild_score_over_time(pivot)
        ax.plot(series.index, series.values, label=g.guild, color=color, linewidth=2)

    ax.set_title("Guild Score Over Time", fontsize=16, weight="bold")
    ax.set_ylabel("Guild Score")
    ax.legend(loc="upper left", fontsize=9, ncol=2)
    fig.autofmt_xdate()
    fig.tight_layout()

    return _save(fig, path or f"{_OUT_DIR}/final_score_race.png")


def _summary_stats() -> list[tuple[str, str]]:
    scores = _competitor_scores()
    guilds = compute_guild_standings(scores)

    stats = [
        ("Competitors", f"{len(scores):,}"),
        ("Guilds", f"{len(guilds):,}"),
        ("Total SE Gained", _format_se(scores["se_gain"].sum())),
        ("Total EB Gained", _format_se(scores["eb_gain"].sum())),
        ("Total Prestiges Done", f"{int(scores['prestiges_gain'].sum()):,}"),
        ("Average Score", f"{scores['score'].mean():,.0f}"),
    ]
    if not scores.empty:
        top = scores.iloc[0]
        stats.append(("Top Player", f"{top['ei_name']} ({int(top['score']):,})"))
    if not guilds.empty:
        top_g = guilds.iloc[0]
        stats.append(("Top Guild", f"{top_g['guild']} ({int(top_g['guild_score']):,})"))
    return stats


def generate_stats_image(path: str | None = None) -> str | None:
    """Two-column stat-card: totals and highlights across all registered
    competitors."""
    stats = _summary_stats()
    if not stats:
        print("[report] no competitor data — skipping stats image")
        return None

    sns.set(style="whitegrid")
    fig, ax = plt.subplots(figsize=(7, max(3, len(stats) * 0.6 + 1)))
    fig.patch.set_visible(False)
    ax.axis("off")
    ax.set_title("Competition Stats", fontsize=16, weight="bold", pad=20)

    table = ax.table(cellText=stats, colLabels=["Stat", "Value"],
                      cellLoc="left", loc="center", colWidths=[0.55, 0.45])
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.2, 2.0)

    for (i, j), cell in table.get_celld().items():
        cell.set_edgecolor("black")
        if i == 0:
            cell.set_text_props(weight="bold", color="white")
            cell.set_facecolor(_ORANGE)
        else:
            cell.set_facecolor("#F9EBC8" if i % 2 == 0 else "#FFF4EB")
            if j == 0:
                cell.set_text_props(weight="bold")

    return _save(fig, path or f"{_OUT_DIR}/final_stats.png")


def generate_mer_scatter_image(path: str | None = None) -> str | None:
    """Scatter of final MER vs competition score, colored by guild —
    shows whether efficient players (high MER) also scored high."""
    scores = _final_scores()
    if scores.empty:
        print("[report] no score data — skipping MER scatter image")
        return None

    plot_df = scores.copy()
    plot_df["Guild"] = plot_df["guild"].replace("", "Unregistered")

    sns.set(style="whitegrid")
    fig, ax = plt.subplots(figsize=(9, 6))
    sns.scatterplot(data=plot_df, x="mer_end", y="score", hue="Guild",
                    palette="husl", s=60, alpha=0.8, ax=ax)

    ax.set_xlabel("MER (final)")
    ax.set_ylabel("Score")
    ax.set_title("MER vs Score", fontsize=16, weight="bold")
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    fig.tight_layout()

    return _save(fig, path or f"{_OUT_DIR}/final_mer_scatter.png")


def generate_score_distribution_image(path: str | None = None) -> str | None:
    """Histogram of final scores across registered competitors."""
    scores = _competitor_scores()
    if scores.empty:
        print("[report] no competitor data — skipping score distribution image")
        return None

    sns.set(style="whitegrid")
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.histplot(scores["score"], bins=min(20, max(5, len(scores) // 2)),
                color=_ORANGE, ax=ax)
    ax.axvline(scores["score"].mean(), color="black", linestyle="--", linewidth=1,
              label=f"Mean ({scores['score'].mean():,.0f})")
    ax.set_xlabel("Score")
    ax.set_ylabel("Players")
    ax.set_title("Score Distribution", fontsize=16, weight="bold")
    ax.legend()
    fig.tight_layout()

    return _save(fig, path or f"{_OUT_DIR}/final_score_distribution.png")


def generate_all() -> list[str]:
    paths = [
        generate_guild_standings_image(),
        generate_leaderboard_image(),
        generate_score_race_image(),
        generate_stats_image(),
        generate_mer_scatter_image(),
        generate_score_distribution_image(),
    ]
    return [p for p in paths if p]
