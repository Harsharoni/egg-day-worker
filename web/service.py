"""Data assembly for the website. Read-only: imports only config, db and
processors — never fetchers/ or sheets/. Everything is cached; the DB is
touched at most once per TTL per key."""

from datetime import datetime, timezone

import pandas as pd

from config import COMP_START_UTC, COMP_END_UTC, FAIR_POWER, GUILD_FAIR_POWER
from db import load_snapshot, load_start_snapshot, load_participants, load_history
from processors.competition import comp_phase, resolve_end_snapshot
from processors.guilds import compute_guild_standings, guild_key
from processors.participants import apply_participants
from processors.scoring import compute_scores
from web.cache import cache

_LABEL_FMT = "%d/%m %H:%M"  # comp spans two days; keeps Chart.js adapter-free

_STATS = ["se", "eb", "pe", "te", "mer", "prestiges"]
_SNAPSHOT_TO_STAT = {
    "soul_eggs": "se", "earnings_bonus": "eb", "prophecy_eggs": "pe",
    "truth_eggs": "te", "mer": "mer", "num_prestiges": "prestiges",
}


def _pseudo_scores(latest: pd.DataFrame) -> pd.DataFrame:
    """Score-shaped frame for before the comp: current stats as *_end,
    no start/gain/score yet (rendered as dashes)."""
    df = latest.copy().sort_values("soul_eggs", ascending=False)
    df.reset_index(drop=True, inplace=True)
    out = pd.DataFrame({
        "rank": range(1, len(df) + 1),
        "discord_id": df["discord_id"],
        "ei_name": df["ei_name"],
        "discord_name": df["discord_name"],
    })
    for col, stat in _SNAPSHOT_TO_STAT.items():
        out[f"{stat}_end"] = df[col]
    for stat in _STATS:
        out[f"{stat}_start"] = None
        out[f"{stat}_gain"] = None
    out["se_gain_pct"] = None
    out["eb_gain_pct"] = None
    out["fair_factor"] = None
    out["score"] = None
    return out


def _build_bundle() -> dict:
    now = datetime.now(timezone.utc)
    latest = load_snapshot()
    start = load_start_snapshot()
    participants = load_participants()
    phase = comp_phase(now)

    if phase == "pre" or start.empty:
        scores = _pseudo_scores(latest)
    else:
        end_df = resolve_end_snapshot(now, latest)
        scores = compute_scores(start, end_df)

    scores = apply_participants(scores, participants, filter_unmatched=False)
    guilds = compute_guild_standings(scores)

    last_updated = None
    if not latest.empty:
        last_updated = pd.to_datetime(latest["timestamp"]).max()

    return {
        "phase": phase,
        "scores": scores,
        "guilds": guilds,
        "last_updated": last_updated,
    }


def get_bundle() -> dict:
    return cache.get_or_compute("bundle", _build_bundle)


def _load_comp_history() -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    if now < COMP_START_UTC:
        return pd.DataFrame(columns=["discord_id", "ei_name", "soul_eggs",
                                     "rank", "timestamp"])
    df = load_history(COMP_START_UTC, min(now, COMP_END_UTC))
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def get_history() -> pd.DataFrame:
    return cache.get_or_compute("history", _load_comp_history)


def get_player(discord_id: int, ei_name: str | None = None):
    """(row dict, accounts) — row is the matched account's score row or None;
    accounts lists all ei_names owned by this discord_id."""
    scores = get_bundle()["scores"]
    mine = scores[scores["discord_id"] == discord_id]
    accounts = mine["ei_name"].tolist()
    if mine.empty:
        return None, []
    if ei_name is not None:
        hit = mine[mine["ei_name"].str.lower() == ei_name.lower()]
        return (hit.iloc[0].to_dict() if len(hit) else None), accounts
    if len(mine) == 1:
        return mine.iloc[0].to_dict(), accounts
    return None, accounts


def get_player_series(discord_id: int, ei_name: str) -> dict:
    def compute():
        empty = {"labels": [], "soul_eggs": [], "earnings_bonus": [], "mer": [], "rank": []}
        hist = get_history()
        if hist.empty:
            return empty
        rows = hist[(hist["discord_id"] == discord_id)
                    & (hist["ei_name"].str.lower() == ei_name.lower())]
        if rows.empty:
            return empty
        rows = rows.sort_values("timestamp")

        # competition-leaderboard rank (by score), not the raw SE-based rank
        # egg9000 stamps on each poll — matches the "Rank N" shown on the page.
        sh = get_score_history()
        mine = sh[(sh["discord_id"] == discord_id)
                  & (sh["ei_name"].str.lower() == ei_name.lower())]
        rank_by_ts = mine.set_index("timestamp")["rank"]
        ranks = [int(r) if pd.notna(r) else None
                 for r in rows["timestamp"].map(rank_by_ts)]

        return {
            "labels": rows["timestamp"].dt.strftime(_LABEL_FMT).tolist(),
            "soul_eggs": rows["soul_eggs"].tolist(),
            "earnings_bonus": rows["earnings_bonus"].tolist(),
            "mer": rows["mer"].tolist(),
            "rank": ranks,
        }
    return cache.get_or_compute(f"pseries:{discord_id}:{ei_name.lower()}", compute)


def get_guild(gkey: str):
    """(standings row dict or None, member score rows DataFrame)."""
    bundle = get_bundle()
    guilds, scores = bundle["guilds"], bundle["scores"]
    hit = guilds[guilds["guild_key"] == gkey]
    if hit.empty:
        return None, pd.DataFrame()
    members = scores[scores["guild"].map(guild_key) == gkey]
    return hit.iloc[0].to_dict(), members


_SH_COLS = ["timestamp", "discord_id", "ei_name", "guild",
            "se_gain", "eb_gain", "prestiges", "score", "rank"]


def get_score_history() -> pd.DataFrame:
    """Per-poll per-player gains and score across the comp, guild attached.
    Same math as processors.scoring.compute_scores, applied to every poll."""
    def compute():
        hist = get_history()
        start = load_start_snapshot()
        if hist.empty or start.empty:
            return pd.DataFrame(columns=_SH_COLS)

        base = start[["discord_id", "ei_name", "soul_eggs", "earnings_bonus",
                      "num_prestiges"]]
        base = base.rename(columns={"soul_eggs": "se_start",
                                    "earnings_bonus": "eb_start",
                                    "num_prestiges": "prestiges_start"})
        max_eb = start["earnings_bonus"].max()

        df = hist.merge(base, on=["discord_id", "ei_name"], how="inner")
        avg_eb = (df["eb_start"] + df["earnings_bonus"]) / 2
        avg_eb = avg_eb.where(df["earnings_bonus"] != 0, df["eb_start"])
        fair = ((max_eb / avg_eb) ** FAIR_POWER).round(3)
        df["se_gain"] = df["soul_eggs"] - df["se_start"]
        df["eb_gain"] = df["earnings_bonus"] - df["eb_start"]
        df["prestiges"] = df["num_prestiges"] - df["prestiges_start"]
        df["score"] = (df["se_gain"] * fair / 1e18).round()
        df["rank"] = df.groupby("timestamp")["score"].rank(
            method="min", ascending=False).astype(int)

        guilds = get_bundle()["scores"][["discord_id", "ei_name", "guild"]].copy()
        guilds["ei_l"] = guilds["ei_name"].str.lower()
        df["ei_l"] = df["ei_name"].str.lower()
        df = df.merge(guilds[["discord_id", "ei_l", "guild"]],
                      on=["discord_id", "ei_l"], how="left")
        df["guild"] = df["guild"].fillna("")
        return df[_SH_COLS]
    return cache.get_or_compute("score_history", compute)


def _guild_pivots(rows: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Per-metric (timestamp × player) pivots. ffill: a player missing one
    poll must not read as a guild-wide dip."""
    return {
        col: rows.pivot_table(index="timestamp", values=col,
                              columns=["discord_id", "ei_name"]).ffill()
        for col in ("se_gain", "eb_gain", "prestiges", "score")
    }


def _guild_score_over_time(pivots: dict) -> pd.Series:
    score = pivots["score"]
    active = (score > 0).sum(axis=1)
    n = active.where(active > 0, score.notna().sum(axis=1)).clip(lower=1)
    return (score.sum(axis=1) / n ** GUILD_FAIR_POWER).round()


def get_guild_series(gkey: str) -> dict:
    def compute():
        sh = get_score_history()
        empty = {"labels": [], "se_gain": [], "eb_gain": [], "score": []}
        if sh.empty:
            return empty
        rows = sh[sh["guild"].map(guild_key) == gkey]
        if rows.empty:
            return empty
        pivots = _guild_pivots(rows)
        idx = pivots["se_gain"].index
        return {
            "labels": idx.strftime(_LABEL_FMT).tolist(),
            "se_gain": pivots["se_gain"].sum(axis=1).tolist(),
            "eb_gain": pivots["eb_gain"].sum(axis=1).tolist(),
            "score": _guild_score_over_time(pivots).tolist(),
        }
    return cache.get_or_compute(f"gseries:{gkey}", compute)


def _race_series(cache_key: str, per_guild) -> dict:
    """One dataset per guild (standings order); per_guild(pivots) -> Series."""
    def compute():
        sh = get_score_history()
        standings = get_bundle()["guilds"]
        if sh.empty or standings.empty:
            return {"labels": [], "datasets": []}
        sh_keyed = sh.assign(gkey=sh["guild"].map(guild_key))
        all_ts = pd.Index(sorted(sh_keyed["timestamp"].unique()))
        datasets = []
        for _, g in standings.iterrows():
            rows = sh_keyed[sh_keyed["gkey"] == g["guild_key"]]
            if rows.empty:
                continue
            series = per_guild(_guild_pivots(rows))
            series = series.reindex(all_ts).ffill().fillna(0)
            datasets.append({"label": g["guild"], "data": series.tolist()})
        return {
            "labels": all_ts.strftime(_LABEL_FMT).tolist(),
            "datasets": datasets,
        }
    return cache.get_or_compute(cache_key, compute)


def get_guild_race_series() -> dict:
    """Guild score over time, one dataset per guild."""
    return _race_series("race", _guild_score_over_time)


def get_prestige_race_series() -> dict:
    """Prestiges gained since comp start, one dataset per guild."""
    return _race_series("prace", lambda p: p["prestiges"].sum(axis=1))
