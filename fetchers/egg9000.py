import requests
import pandas as pd
from config import EGG9000_API_KEY

_URL = "https://egg9000.com/Home/LeaderboardJson"


def fetch_leaderboard() -> pd.DataFrame:
    """
    Fetch egg9000 JSON leaderboard.

    Returns DataFrame sorted by soul_eggs descending with rank column added.
    Columns: discord_name, discord_id, ei_name, earnings_bonus, soul_eggs,
             prophecy_eggs, mer, truth_eggs, num_prestiges, rank
    """
    response = requests.get(
        _URL,
        headers={"X-API-Key": EGG9000_API_KEY},
        timeout=15,
    )
    response.raise_for_status()

    df = pd.DataFrame(response.json())
    df.rename(columns={
        "discordName":    "discord_name",
        "discordId":      "discord_id",
        "eggIncName":     "ei_name",
        "earningsBonus":  "earnings_bonus",
        "soulEggs":       "soul_eggs",
        "eggsOfProphecy": "prophecy_eggs",
        "mer":            "mer",
        "eggsOfTruth":    "truth_eggs",
        "numPrestiges":   "num_prestiges",
    }, inplace=True)

    df.sort_values("soul_eggs", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.insert(0, "rank", range(1, len(df) + 1))

    return df
