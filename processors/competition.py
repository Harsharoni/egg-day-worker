from datetime import datetime
from typing import Literal

import pandas as pd

from config import COMP_START_UTC, COMP_END_UTC

# MER is computed server-side and returned in the JSON response.
# No local calculation needed.

Phase = Literal["pre", "live", "post"]


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    return df


def comp_phase(now: datetime) -> Phase:
    if now < COMP_START_UTC:
        return "pre"
    if now <= COMP_END_UTC:
        return "live"
    return "post"


def resolve_end_snapshot(now: datetime, latest_df: pd.DataFrame) -> pd.DataFrame:
    """Current end-state for scoring: live snapshot while the competition
    runs, the frozen state at COMP_END_UTC once it is over."""
    if now <= COMP_END_UTC:
        return latest_df
    from db import snapshot_at
    return snapshot_at(COMP_END_UTC)
