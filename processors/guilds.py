import pandas as pd
from config import GUILD_FAIR_POWER


def guild_key(raw: str) -> str:
    """Normalized grouping key for free-text guild names; "" if blank."""
    return raw.strip().casefold() if isinstance(raw, str) else ""


def compute_guild_standings(scores: pd.DataFrame,
                            power: float = GUILD_FAIR_POWER) -> pd.DataFrame:
    """
    Guild race standings from participant-matched score rows.

    guild_score = round(sum(member scores) / N^power); N counts members with
    a score, so registering inactive players doesn't drag a guild down.
    Guild names are free text from the registration form — rows group on
    guild_key, display name is the most common original spelling.

    Returns columns: rank, guild_key, guild, member_count, se_gain,
    eb_gain, sum_score, guild_score — sorted by guild_score descending.
    Empty DataFrame with those columns if no guild rows exist.
    """
    cols = ["rank", "guild_key", "guild", "member_count",
            "se_gain", "eb_gain", "sum_score", "guild_score"]
    if scores.empty or "guild" not in scores.columns:
        return pd.DataFrame(columns=cols)

    df = scores.copy()
    df["guild_key"] = df["guild"].map(guild_key)
    df = df[df["guild_key"] != ""]
    if df.empty:
        return pd.DataFrame(columns=cols)

    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0)
    for gain_col in ("se_gain", "eb_gain"):
        df[gain_col] = (pd.to_numeric(df.get(gain_col), errors="coerce")
                        .fillna(0) if gain_col in df.columns else 0.0)

    def _one(g: pd.DataFrame) -> pd.Series:
        display = g["guild"].str.strip().value_counts().index[0]
        active = int((g["score"] > 0).sum()) or len(g)
        total = g["score"].sum()
        return pd.Series({
            "guild": display,
            "member_count": len(g),
            "se_gain": g["se_gain"].sum(),
            "eb_gain": g["eb_gain"].sum(),
            "sum_score": int(total),
            "guild_score": int(round(total / active ** power)),
        })

    out = df.groupby("guild_key").apply(_one, include_groups=False).reset_index()
    out.sort_values("guild_score", ascending=False, inplace=True)
    out.reset_index(drop=True, inplace=True)
    out.insert(0, "rank", range(1, len(out) + 1))
    return out[cols]
