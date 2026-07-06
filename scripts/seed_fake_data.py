"""Seed a scratch database with synthetic competition data for local testing.

Usage:
    DATABASE_URL=postgresql://...eggday_test uv run python scripts/seed_fake_data.py
    DATABASE_URL=... uv run python scripts/seed_fake_data.py --pre-comp

Writes only through db.py — zero network. Refuses to run against a database
that already has rows unless --force is given.
"""

import argparse
import math
import random
import sys
from datetime import timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from config import COMP_START_UTC, COMP_END_UTC
import db

GUILDS = ["The Coop", "the coop ", "THE COOP", "Nest Egg", "Yolk Empire", None]

random.seed(42)
np.random.seed(42)


def build_players(n: int = 60) -> list[dict]:
    players = []
    for i in range(n):
        players.append({
            "discord_id": 100_000 + i,
            "discord_name": f"user{i}",
            "ei_name": f"Player {i}",
            "soul_eggs": 10 ** random.uniform(18.5, 22.5),
            "earnings_bonus": 10 ** random.uniform(12, 18),
            "prophecy_eggs": random.randint(50, 250),
            "truth_eggs": random.randint(0, 20),
            "num_prestiges": random.randint(100, 1500),
            "growth": random.uniform(0.001, 0.03),  # SE growth per poll
        })
    # edge cases
    players[5]["ei_name"] = "Émil 🥚"                      # unicode + emoji
    players[6]["ei_name"] = "a/b slash"                    # slash in name
    players[7]["discord_id"] = players[8]["discord_id"]    # two alts, one owner
    return players


def snapshot_frame(players: list[dict], step: int) -> pd.DataFrame:
    rows = []
    for p in players:
        rows.append({
            "discord_id": p["discord_id"],
            "discord_name": p["discord_name"],
            "ei_name": p["ei_name"],
            "earnings_bonus": p["earnings_bonus"] * (1 + p["growth"] / 3) ** step,
            "soul_eggs": p["soul_eggs"] * (1 + p["growth"]) ** step,
            "prophecy_eggs": p["prophecy_eggs"],
            "truth_eggs": p["truth_eggs"],
            "num_prestiges": p["num_prestiges"] + step,
            "mer": round(91 * (math.log10(p["soul_eggs"]) - 18) / 10, 1),
        })
    df = pd.DataFrame(rows).sort_values("soul_eggs", ascending=False)
    df.reset_index(drop=True, inplace=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    return df


def participants_frame(players: list[dict]) -> pd.DataFrame:
    rows = []
    for i, p in enumerate(players[:40]):  # rest stay unregistered
        guild = GUILDS[i % len(GUILDS)]
        if guild is None:
            continue
        rows.append({
            "discord_id": p["discord_id"],
            "discord_name": p["discord_name"],
            "ei_name": p["ei_name"],
            "guild": guild,
        })
    rows[3]["ei_name"] = "totally wrong name"   # tier-2 match (sole account)
    rows[4]["discord_id"] = 999_999_999         # tier-3 match (ei_name only)
    return pd.DataFrame(rows).drop_duplicates("discord_id")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pre-comp", action="store_true",
                    help="seed history only, leave start_snapshot empty")
    ap.add_argument("--force", action="store_true",
                    help="seed even if player_data already has rows")
    args = ap.parse_args()

    db.initialize()
    with db._engine.connect() as conn:
        from sqlalchemy import text
        existing = conn.execute(text("SELECT COUNT(*) FROM player_data")).scalar()
    if existing and not args.force:
        sys.exit(f"player_data already has {existing} rows — refusing to seed "
                 f"(use --force or point DATABASE_URL at a scratch db)")

    players = build_players()
    start = COMP_START_UTC.astimezone(timezone.utc)
    end = COMP_END_UTC.astimezone(timezone.utc)
    polls = int((end - start) / timedelta(minutes=15)) + 1

    from unittest.mock import patch
    for step in range(polls):
        ts = start + timedelta(minutes=15 * step)
        df = snapshot_frame(players, step)
        with patch("db.datetime") as mock_dt:
            mock_dt.now.return_value = ts
            db.save_snapshot(df)
        if step == 0 and not args.pre_comp:
            with patch("db.datetime") as mock_dt:
                mock_dt.now.return_value = ts
                db.save_start_snapshot(df)

    db.upsert_participants(participants_frame(players))
    print(f"seeded {len(players)} players × {polls} polls "
          f"({'pre-comp' if args.pre_comp else 'full comp'})")


if __name__ == "__main__":
    main()
