import pandas as pd
from db import load_history
from datetime import datetime, timedelta
from config import REPORT_MIN_GAIN, REPORT_LIMIT


def compute_gains(hours: int = 1, limit: int | None = None) -> pd.DataFrame:
    """
    Compare oldest vs newest snapshot per player within the last `hours` window.
    Returns DataFrame sorted by soul_egg gain descending, filtered to >= REPORT_MIN_GAIN.
    """
    end_time = datetime.now().replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(hours=hours)
    start_ts = start_time.strftime("%Y-%m-%d %H:%M")
    end_ts = end_time.strftime("%Y-%m-%d %H:%M")

    history = load_history(start_ts, end_ts)
    if history.empty:
        return pd.DataFrame()

    history["timestamp"] = pd.to_datetime(history["timestamp"])

    key = ["discord_id", "ei_name"]
    first = history.sort_values("timestamp").groupby(key).first()
    last = history.sort_values("timestamp").groupby(key).last()

    gains = pd.DataFrame({
        "discord_id":   [i[0] for i in first.index],
        "ei_name":      [i[1] for i in first.index],
        "discord_name": last["discord_name"],
        "se_gain":      last["soul_eggs"] - first["soul_eggs"],
        "rank_start":   first["rank"],
        "rank_end":     last["rank"],
        "mer_start":    first["mer"],
        "mer_end":      last["mer"],
        "se_start":     first["soul_eggs"],
        "se_end":       last["soul_eggs"],
    }).reset_index(drop=True)

    gains = gains[gains["se_gain"] >= REPORT_MIN_GAIN]
    gains.sort_values("se_gain", ascending=False, inplace=True)
    gains.reset_index(drop=True, inplace=True)

    cap = limit if limit is not None else REPORT_LIMIT
    return gains.head(cap)
