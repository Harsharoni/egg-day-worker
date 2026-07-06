import pandas as pd
from config import FAIR_POWER


def compute_scores(start_df: pd.DataFrame, end_df: pd.DataFrame,
                   power: float = FAIR_POWER) -> pd.DataFrame:
    """
    Port of the sheet fair-factor + score formulas.

    fair = (maxEB / avgEB) ^ power
      maxEB = max starting earnings_bonus across all players
      avgEB = mean(start EB, end EB); start EB alone if end EB is 0

    score = round(se_gain * fair / 10^18)
    """
    key = ["discord_id", "ei_name"]
    start = start_df.set_index(key)
    end = end_df.set_index(key)
    ids = start.index.intersection(end.index)
    start, end = start.loc[ids], end.loc[ids]

    max_eb = start["earnings_bonus"].max()
    avg_eb = (start["earnings_bonus"] + end["earnings_bonus"]) / 2
    avg_eb = avg_eb.where(end["earnings_bonus"] != 0, start["earnings_bonus"])

    fair = ((max_eb / avg_eb) ** power).round(3)
    se_gain = end["soul_eggs"] - start["soul_eggs"]

    scores = pd.DataFrame(index=ids)
    scores["discord_name"] = end["discord_name"]

    stats = {
        "se":        "soul_eggs",
        "eb":        "earnings_bonus",
        "pe":        "prophecy_eggs",
        "te":        "truth_eggs",
        "mer":       "mer",
        "prestiges": "num_prestiges",
    }
    for short, col in stats.items():
        scores[f"{short}_start"] = start[col].values
        scores[f"{short}_end"] = end[col].values
        scores[f"{short}_gain"] = (end[col] - start[col]).values

    scores["fair_factor"] = fair.values
    scores["score"] = (se_gain * fair / 1e18).round().astype("int64").values
    scores = scores.reset_index()  # discord_id, ei_name back as columns

    scores.sort_values("score", ascending=False, inplace=True)
    scores.reset_index(drop=True, inplace=True)
    scores.insert(0, "rank", range(1, len(scores) + 1))
    return scores
