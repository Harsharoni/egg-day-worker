import pandas as pd


def apply_participants(scores: pd.DataFrame, participants: pd.DataFrame,
                       filter_unmatched: bool = True) -> pd.DataFrame:
    """
    Attach guild to score rows via participant registrations.

    Scores hold one row per EI account (players can own alts), so each
    participant maps to exactly one account row:
      1. exact (discord_id, ei_name) match
      2. discord_id owning a single account (registered ei_name was a typo)
      3. unique ei_name match (registered discord id was a typo)
    Ambiguous or missing participants are reported for manual review.

    filter_unmatched=True (worker/sheet): keep only matched rows, re-sort by
    score and re-rank. filter_unmatched=False (site): keep every row with
    guild="" where unmatched, original order and rank untouched.
    """
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
            print(f"[participants] participant {p.discord_name}: registered ei_name "
                  f"'{p.ei_name}' not found, using their only account "
                  f"'{scores.at[by_id[0], 'ei_name']}'")
            continue
        if len(by_id) > 1:
            owned = scores.loc[by_id, "ei_name"].tolist()
            print(f"[participants] participant {p.discord_name}: registered ei_name "
                  f"'{p.ei_name}' not among their accounts {owned} — skipped, "
                  f"fix registration")
            continue

        by_ei = scores.index[ei_lower == p.ei_name.lower()]
        if len(by_ei) == 1:
            picked_rows.append(by_ei[0])
            guilds.append(p.guild)
            print(f"[participants] participant {p.discord_name}: discord id "
                  f"{p.discord_id} not on leaderboard, matched via ei_name "
                  f"'{p.ei_name}'")
        else:
            print(f"[participants] participant {p.discord_name} "
                  f"({p.discord_id} / '{p.ei_name}') not on leaderboard")

    if not filter_unmatched:
        scores = scores.copy()
        scores["guild"] = ""
        scores.loc[picked_rows, "guild"] = guilds
        return scores

    scores = scores.loc[picked_rows].copy()
    scores["guild"] = guilds
    scores.sort_values("score", ascending=False, inplace=True)
    scores.reset_index(drop=True, inplace=True)
    scores["rank"] = range(1, len(scores) + 1)
    return scores
