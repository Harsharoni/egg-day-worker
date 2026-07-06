import sys
import time
import pandas as pd
from datetime import datetime, timedelta, timezone
from config import POLL_INTERVAL_MINUTES, COMP_START_UTC, COMP_END_UTC
from fetchers.egg9000 import fetch_leaderboard
from processors.competition import enrich
from processors.scoring import compute_scores
from db import (
    initialize, save_snapshot, save_start_snapshot, load_start_snapshot,
    snapshot_at, upsert_participants, load_participants,
)
from sheets.writer import write_scoreboard
from sheets.registration import fetch_registrations
from reports.image import generate_gains_image


def _next_interval(interval_minutes: int) -> datetime:
    """Return next wall-clock time aligned to interval boundaries."""
    now = datetime.now()
    minutes_past = now.minute % interval_minutes
    wait = interval_minutes - minutes_past
    nxt = (now + timedelta(minutes=wait)).replace(second=0, microsecond=0)
    return nxt


def sync_registrations() -> None:
    try:
        regs = fetch_registrations()
    except Exception as e:
        print(f"[main] registration sync failed: {e}")
        return
    if not regs.empty:
        upsert_participants(regs)
        print(f"[main] synced {len(regs)} registrations")


def _apply_participants(scores: pd.DataFrame) -> pd.DataFrame:
    """
    Filter scores to registered participants and attach guild.

    Scores hold one row per EI account (players can own alts), so each
    participant maps to exactly one account row:
      1. exact (discord_id, ei_name) match
      2. discord_id owning a single account (registered ei_name was a typo)
      3. unique ei_name match (registered discord id was a typo)
    Ambiguous or missing participants are reported for manual review.
    """
    participants = load_participants()
    if participants.empty:
        scores = scores.copy()
        scores["guild"] = ""
        return scores

    ei_lower = scores["ei_name"].str.lower()
    picked_rows: list[int] = []
    guilds: list[str] = []
    for p in participants.itertuples(index=False):
        exact = scores.index[(scores["discord_id"] == p.discord_id)
                             & (ei_lower == p.ei_name.lower())]
        if len(exact):
            picked_rows.append(exact[0])
            guilds.append(p.guild)
            continue

        by_id = scores.index[scores["discord_id"] == p.discord_id]
        if len(by_id) == 1:
            picked_rows.append(by_id[0])
            guilds.append(p.guild)
            print(f"[main] participant {p.discord_name}: registered ei_name "
                  f"'{p.ei_name}' not found, using their only account "
                  f"'{scores.at[by_id[0], 'ei_name']}'")
            continue
        if len(by_id) > 1:
            owned = scores.loc[by_id, "ei_name"].tolist()
            print(f"[main] participant {p.discord_name}: registered ei_name "
                  f"'{p.ei_name}' not among their accounts {owned} — skipped, "
                  f"fix registration")
            continue

        by_ei = scores.index[ei_lower == p.ei_name.lower()]
        if len(by_ei) == 1:
            picked_rows.append(by_ei[0])
            guilds.append(p.guild)
            print(f"[main] participant {p.discord_name}: discord id "
                  f"{p.discord_id} not on leaderboard, matched via ei_name "
                  f"'{p.ei_name}'")
        else:
            print(f"[main] participant {p.discord_name} "
                  f"({p.discord_id} / '{p.ei_name}') not on leaderboard")

    scores = scores.loc[picked_rows].copy()
    scores["guild"] = guilds
    scores.sort_values("score", ascending=False, inplace=True)
    scores.reset_index(drop=True, inplace=True)
    scores["rank"] = range(1, len(scores) + 1)
    return scores


def update_scoreboard(df: pd.DataFrame, now: datetime) -> None:
    if now < COMP_START_UTC:
        return

    start_df = load_start_snapshot()
    if start_df.empty:
        if now > COMP_END_UTC:
            print("[main] no start snapshot and competition over — skipping scores")
            return
        save_start_snapshot(df)
        start_df = load_start_snapshot()

    end_df = df if now <= COMP_END_UTC else snapshot_at(COMP_END_UTC)
    scores = compute_scores(start_df, end_df)
    scores = _apply_participants(scores)
    write_scoreboard(scores)


def run_cycle() -> None:
    now = datetime.now(timezone.utc)
    print(f"[main] cycle start @ {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")

    df = fetch_leaderboard()
    df = enrich(df)
    save_snapshot(df)
    sync_registrations()
    update_scoreboard(df, now)
    generate_gains_image(hours=1)

    print(f"[main] cycle done — {len(df)} players")


def main() -> None:
    initialize()

    if "--once" in sys.argv:
        print("[main] test mode: single cycle, no schedule")
        run_cycle()
        return

    print(f"[main] starting (interval={POLL_INTERVAL_MINUTES}min)")

    while True:
        next_run = _next_interval(POLL_INTERVAL_MINUTES)
        sleep_secs = (next_run - datetime.now()).total_seconds()
        print(f"[main] sleeping {int(sleep_secs)}s until {next_run.strftime('%H:%M')}")
        time.sleep(max(0, sleep_secs))
        try:
            run_cycle()
        except Exception as e:
            print(f"[main] cycle error: {e}")


if __name__ == "__main__":
    main()
