import sys
import time
import pandas as pd
from datetime import datetime, timedelta, timezone
from config import POLL_INTERVAL_MINUTES
from fetchers.egg9000 import fetch_leaderboard
from processors.competition import enrich, comp_phase, resolve_end_snapshot
from processors.participants import apply_participants
from processors.scoring import compute_scores
from db import (
    initialize, save_snapshot, save_start_snapshot, load_start_snapshot,
    upsert_participants, load_participants,
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


def update_scoreboard(df: pd.DataFrame, now: datetime) -> None:
    phase = comp_phase(now)
    if phase == "pre":
        return

    start_df = load_start_snapshot()
    if start_df.empty:
        if phase == "post":
            print("[main] no start snapshot and competition over — skipping scores")
            return
        save_start_snapshot(df)
        start_df = load_start_snapshot()

    end_df = resolve_end_snapshot(now, df)
    scores = compute_scores(start_df, end_df)
    scores = apply_participants(scores, load_participants())
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
