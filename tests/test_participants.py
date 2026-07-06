import pandas as pd
import pytest

from processors.participants import apply_participants


@pytest.fixture
def scores():
    return pd.DataFrame({
        "rank": [1, 2, 3, 4, 5],
        "discord_id": [1, 2, 2, 3, 4],   # discord 2 owns two alts
        "ei_name": ["Alice", "Bob Main", "Bob Alt", "Carol", "Dave"],
        "discord_name": ["a", "b", "b", "c", "d"],
        "score": [100, 80, 60, 40, 20],
    })


def _parts(rows):
    return pd.DataFrame(rows, columns=["discord_id", "discord_name", "ei_name", "guild"])


def test_tier1_exact_match(scores):
    parts = _parts([(1, "a", "alice", "G1")])  # case-insensitive ei match
    out = apply_participants(scores, parts)
    assert list(out["ei_name"]) == ["Alice"]
    assert list(out["guild"]) == ["G1"]


def test_tier2_sole_account_typo_ei(scores):
    parts = _parts([(4, "d", "WRONG NAME", "G2")])
    out = apply_participants(scores, parts)
    assert list(out["ei_name"]) == ["Dave"]


def test_tier2_ambiguous_multi_account_skipped(scores):
    parts = _parts([(2, "b", "not an account", "G3")])
    out = apply_participants(scores, parts)
    assert out.empty


def test_tier3_ei_name_only(scores):
    parts = _parts([(999, "c", "carol", "G4")])
    out = apply_participants(scores, parts)
    assert list(out["ei_name"]) == ["Carol"]


def test_filtered_resorts_and_reranks(scores):
    parts = _parts([(3, "c", "Carol", "G"), (1, "a", "Alice", "G")])
    out = apply_participants(scores, parts, filter_unmatched=True)
    assert list(out["ei_name"]) == ["Alice", "Carol"]  # by score desc
    assert list(out["rank"]) == [1, 2]                 # re-ranked


def test_unfiltered_keeps_all_rows_and_order(scores):
    parts = _parts([(1, "a", "Alice", "G1")])
    out = apply_participants(scores, parts, filter_unmatched=False)
    assert len(out) == len(scores)
    assert list(out["rank"]) == [1, 2, 3, 4, 5]        # untouched
    assert out.loc[out["ei_name"] == "Alice", "guild"].iloc[0] == "G1"
    assert (out.loc[out["ei_name"] != "Alice", "guild"] == "").all()


def test_empty_participants(scores):
    out = apply_participants(scores, pd.DataFrame(), filter_unmatched=True)
    assert len(out) == len(scores)
    assert (out["guild"] == "").all()


def test_regression_matches_old_apply_participants(scores):
    """filter_unmatched=True must reproduce the pre-refactor main.py logic."""
    parts = _parts([
        (1, "a", "alice", "Coop"),        # tier 1
        (4, "d", "typo", "Coop"),         # tier 2
        (999, "c", "carol", "Nest"),      # tier 3
        (2, "b", "unknown", "X"),         # ambiguous — dropped
        (777, "g", "ghost", "Y"),         # not on leaderboard — dropped
    ])
    out = apply_participants(scores, parts, filter_unmatched=True)
    old = _old_apply_participants(scores, parts)
    pd.testing.assert_frame_equal(
        out.reset_index(drop=True), old.reset_index(drop=True)
    )


def _old_apply_participants(scores, participants):
    """Verbatim pre-refactor main.py:_apply_participants (participants inlined)."""
    if participants.empty:
        scores = scores.copy()
        scores["guild"] = ""
        return scores

    ei_lower = scores["ei_name"].str.lower()
    picked_rows, guilds = [], []
    for p in participants.itertuples(index=False):
        exact = scores.index[(scores["discord_id"] == p.discord_id)
                             & (ei_lower == p.ei_name.lower())]
        if len(exact):
            picked_rows.append(exact[0]); guilds.append(p.guild); continue
        by_id = scores.index[scores["discord_id"] == p.discord_id]
        if len(by_id) == 1:
            picked_rows.append(by_id[0]); guilds.append(p.guild); continue
        if len(by_id) > 1:
            continue
        by_ei = scores.index[ei_lower == p.ei_name.lower()]
        if len(by_ei) == 1:
            picked_rows.append(by_ei[0]); guilds.append(p.guild)

    scores = scores.loc[picked_rows].copy()
    scores["guild"] = guilds
    scores.sort_values("score", ascending=False, inplace=True)
    scores.reset_index(drop=True, inplace=True)
    scores["rank"] = range(1, len(scores) + 1)
    return scores
