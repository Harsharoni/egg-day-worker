import pandas as pd

from processors.guilds import guild_key, compute_guild_standings


def test_guild_key_normalization():
    assert guild_key("The Coop") == "the coop"
    assert guild_key("  THE COOP ") == "the coop"
    assert guild_key("") == ""
    assert guild_key("   ") == ""
    assert guild_key(None) == ""


def _frame(guilds, scores):
    return pd.DataFrame({
        "guild": guilds,
        "score": scores,
        "ei_name": [f"p{i}" for i in range(len(guilds))],
    })


def test_case_variants_merge_and_display_casing():
    df = _frame(["The Coop", "the coop ", "THE COOP", "Nest"], [10, 20, 30, 5])
    out = compute_guild_standings(df, power=0.0)
    assert len(out) == 2
    coop = out[out["guild_key"] == "the coop"].iloc[0]
    assert coop["member_count"] == 3
    assert coop["sum_score"] == 60
    assert coop["guild"] in {"The Coop", "the coop", "THE COOP"}


def test_power_extremes():
    df = _frame(["A"] * 4 + ["B"], [25, 25, 25, 25, 60])
    # power 0: pure sum — A (100) beats B (60)
    p0 = compute_guild_standings(df, power=0.0)
    assert p0.iloc[0]["guild"] == "A" and p0.iloc[0]["guild_score"] == 100
    # power 1: pure average — B (60) beats A (25)
    p1 = compute_guild_standings(df, power=1.0)
    assert p1.iloc[0]["guild"] == "B" and p1.iloc[0]["guild_score"] == 60
    assert p1[p1["guild"] == "A"].iloc[0]["guild_score"] == 25


def test_hand_computed_sqrt_power():
    df = _frame(["G", "G"], [100, 50])
    out = compute_guild_standings(df, power=0.5)
    assert out.iloc[0]["guild_score"] == round(150 / 2 ** 0.5)  # 106


def test_blank_guilds_excluded():
    df = _frame(["", "  ", "Real"], [10, 20, 30])
    out = compute_guild_standings(df)
    assert list(out["guild"]) == ["Real"]


def test_zero_scorers_not_counted_in_n():
    # 2 active + 1 zero-score member: N=2, not 3
    df = _frame(["G", "G", "G"], [100, 50, 0])
    out = compute_guild_standings(df, power=0.5)
    assert out.iloc[0]["guild_score"] == round(150 / 2 ** 0.5)
    assert out.iloc[0]["member_count"] == 3  # display still shows all


def test_none_scores_treated_as_zero():
    # pre-comp pseudo rows carry score=None
    df = _frame(["G", "G"], [None, None])
    out = compute_guild_standings(df, power=0.5)
    assert out.iloc[0]["guild_score"] == 0


def test_empty_input():
    out = compute_guild_standings(pd.DataFrame())
    assert out.empty
    assert "guild_score" in out.columns
