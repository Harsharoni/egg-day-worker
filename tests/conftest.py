import os
import sys
from pathlib import Path

# Dummy env before any project import: tests never touch a real DB or any
# worker secret, and must pass on a machine with no .env at all.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("COMP_START_UTC", "2026-07-15T16:00:00+00:00")
os.environ.setdefault("COMP_END_UTC", "2026-07-16T17:30:00+00:00")

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone

import pandas as pd
import pytest


@pytest.fixture
def scores_df() -> pd.DataFrame:
    """Score-shaped frame: 4 players, one guild pair, one zero-scorer."""
    return pd.DataFrame({
        "rank": [1, 2, 3, 4],
        "discord_id": [1, 2, 3, 4],
        "ei_name": ["Alice", "Bob", "Émil 🥚", "a/b slash"],
        "discord_name": ["alice#1", "bob#2", "emil#3", "slash#4"],
        "se_start": [1e20, 5e19, 2e19, 1e19],
        "se_end": [1.5e20, 6e19, 2e19, 1e19],
        "se_gain": [5e19, 1e19, 0.0, 0.0],
        "se_gain_pct": [50.0, 20.0, 0.0, 0.0],
        "eb_start": [1e15, 1e14, 1e13, 1e12],
        "eb_end": [1.5e15, 1e14, 1e13, 1e12],
        "eb_gain": [5e14, 0.0, 0.0, 0.0],
        "eb_gain_pct": [50.0, 0.0, 0.0, 0.0],
        "pe_start": [100, 90, 80, 70], "pe_end": [101, 90, 80, 70],
        "pe_gain": [1, 0, 0, 0],
        "te_start": [5, 3, 1, 0], "te_end": [6, 3, 1, 0], "te_gain": [1, 0, 0, 0],
        "mer_start": [40.0, 38.0, 35.0, 30.0], "mer_end": [40.5, 38.0, 35.0, 30.0],
        "mer_gain": [0.5, 0.0, 0.0, 0.0],
        "prestiges_start": [500, 400, 300, 200],
        "prestiges_end": [510, 400, 300, 200],
        "prestiges_gain": [10, 0, 0, 0],
        "fair_factor": [1.0, 1.5, 2.0, 2.5],
        "score": [100, 50, 20, 0],
    })


@pytest.fixture
def participants_df() -> pd.DataFrame:
    return pd.DataFrame({
        "discord_id": [1, 2, 3],
        "discord_name": ["alice#1", "bob#2", "emil#3"],
        "ei_name": ["Alice", "Bob", "Émil 🥚"],
        "guild": ["The Coop", "the coop ", "Nest Egg"],
        "registered_at": [datetime.now(timezone.utc)] * 3,
    })


@pytest.fixture
def snapshot_df(scores_df) -> pd.DataFrame:
    """latest_snapshot-shaped frame matching scores_df players."""
    return pd.DataFrame({
        "discord_id": scores_df["discord_id"],
        "discord_name": scores_df["discord_name"],
        "ei_name": scores_df["ei_name"],
        "earnings_bonus": scores_df["eb_end"],
        "soul_eggs": scores_df["se_end"],
        "prophecy_eggs": scores_df["pe_end"],
        "mer": scores_df["mer_end"],
        "truth_eggs": scores_df["te_end"],
        "num_prestiges": scores_df["prestiges_end"],
        "rank": scores_df["rank"],
        "timestamp": [datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)] * 4,
    })


@pytest.fixture
def history_df(snapshot_df) -> pd.DataFrame:
    """Three polls of history for the same players."""
    frames = []
    for i in range(3):
        f = snapshot_df.copy()
        f["timestamp"] = datetime(2026, 7, 15, 16 + i, 0, tzinfo=timezone.utc)
        f["soul_eggs"] = f["soul_eggs"] * (1 + 0.01 * i)
        frames.append(f)
    return pd.concat(frames, ignore_index=True)
