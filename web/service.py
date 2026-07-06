"""Data assembly for the website. Read-only: imports only config, db and
processors — never fetchers/ or sheets/. Everything is cached; the DB is
touched at most once per TTL per key."""

from datetime import datetime, timezone

import pandas as pd

from config import COMP_START_UTC, COMP_END_UTC
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
        hist = get_history()
        if hist.empty:
            return {"labels": [], "soul_eggs": [], "rank": []}
        rows = hist[(hist["discord_id"] == discord_id)
                    & (hist["ei_name"].str.lower() == ei_name.lower())]
        if rows.empty:
            return {"labels": [], "soul_eggs": [], "rank": []}
        rows = rows.sort_values("timestamp")
        return {
            "labels": rows["timestamp"].dt.strftime(_LABEL_FMT).tolist(),
            "soul_eggs": rows["soul_eggs"].tolist(),
            "rank": rows["rank"].tolist(),
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


def get_guild_series(gkey: str) -> dict:
    def compute():
        _, members = get_guild(gkey)
        hist = get_history()
        if members.empty or hist.empty:
            return {"labels": [], "soul_eggs": []}
        keys = set(zip(members["discord_id"], members["ei_name"].str.lower()))
        mask = [
            (i, n.lower()) in keys
            for i, n in zip(hist["discord_id"], hist["ei_name"])
        ]
        rows = hist[mask]
        if rows.empty:
            return {"labels": [], "soul_eggs": []}
        # ffill: a player missing one poll must not read as a guild SE dip
        pivot = (rows.pivot_table(index="timestamp", values="soul_eggs",
                                  columns=["discord_id", "ei_name"])
                 .ffill().sum(axis=1))
        return {
            "labels": pivot.index.strftime(_LABEL_FMT).tolist(),
            "soul_eggs": pivot.tolist(),
        }
    return cache.get_or_compute(f"gseries:{gkey}", compute)
