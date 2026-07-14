import pandas as pd
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from config import DATABASE_URL

_engine = create_engine(DATABASE_URL)

_DDL = """
CREATE TABLE IF NOT EXISTS player_data (
    discord_id      BIGINT      NOT NULL,
    discord_name    TEXT        NOT NULL,
    ei_name         TEXT        NOT NULL,
    earnings_bonus  FLOAT8      NOT NULL,
    soul_eggs       FLOAT8      NOT NULL,
    prophecy_eggs   INTEGER     NOT NULL,
    mer             FLOAT8      NOT NULL,
    truth_eggs      INTEGER     NOT NULL,
    num_prestiges   INTEGER     NOT NULL,
    rank            INTEGER     NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (discord_id, ei_name, timestamp)
);

CREATE INDEX IF NOT EXISTS player_data_ts_idx ON player_data (timestamp);

CREATE TABLE IF NOT EXISTS latest_snapshot (
    discord_id      BIGINT      NOT NULL,
    discord_name    TEXT        NOT NULL,
    ei_name         TEXT        NOT NULL,
    earnings_bonus  FLOAT8      NOT NULL,
    soul_eggs       FLOAT8      NOT NULL,
    prophecy_eggs   INTEGER     NOT NULL,
    mer             FLOAT8      NOT NULL,
    truth_eggs      INTEGER     NOT NULL,
    num_prestiges   INTEGER     NOT NULL,
    rank            INTEGER     NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (discord_id, ei_name)
);

CREATE TABLE IF NOT EXISTS start_snapshot (
    discord_id      BIGINT      NOT NULL,
    discord_name    TEXT        NOT NULL,
    ei_name         TEXT        NOT NULL,
    earnings_bonus  FLOAT8      NOT NULL,
    soul_eggs       FLOAT8      NOT NULL,
    prophecy_eggs   INTEGER     NOT NULL,
    mer             FLOAT8      NOT NULL,
    truth_eggs      INTEGER     NOT NULL,
    num_prestiges   INTEGER     NOT NULL,
    rank            INTEGER     NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (discord_id, ei_name)
);

CREATE TABLE IF NOT EXISTS participants (
    discord_id      BIGINT      PRIMARY KEY,
    discord_name    TEXT        NOT NULL,
    ei_name         TEXT        NOT NULL,
    guild           TEXT        NOT NULL,
    registered_at   TIMESTAMPTZ NOT NULL
);
"""

_COLS = [
    "discord_id", "discord_name", "ei_name", "earnings_bonus",
    "soul_eggs", "prophecy_eggs", "mer", "truth_eggs", "num_prestiges",
    "rank", "timestamp",
]


def initialize() -> None:
    with _engine.begin() as conn:
        conn.execute(text(_DDL))


def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """Players can own several EI accounts; identity key is (discord_id, ei_name).
    Drop exact key collisions (two accounts, both with blank ei_name)."""
    df = df.copy()
    dup = df.duplicated(subset=["discord_id", "ei_name"], keep="first")
    if dup.any():
        for r in df[dup].itertuples(index=False):
            print(f"[db] dropped duplicate (discord_id, ei_name): "
                  f"{r.discord_id} / '{r.ei_name}' ({r.discord_name})")
        df = df[~dup]
    return df


def save_snapshot(df: pd.DataFrame) -> None:
    timestamp = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    df = dedupe(df)
    df["timestamp"] = timestamp

    with _engine.begin() as conn:
        conn.execute(
            text("DELETE FROM player_data WHERE timestamp = :ts"),
            {"ts": timestamp},
        )
        df[_COLS].to_sql("player_data", conn, if_exists="append", index=False)
        conn.execute(text("TRUNCATE latest_snapshot"))
        df[_COLS].to_sql("latest_snapshot", conn, if_exists="append", index=False)

    print(f"[db] saved {len(df)} rows @ {timestamp.strftime('%Y-%m-%d %H:%M')}")


def load_snapshot() -> pd.DataFrame:
    with _engine.connect() as conn:
        return pd.read_sql_query(
            text("SELECT * FROM latest_snapshot ORDER BY soul_eggs DESC"),
            conn,
        )


def load_history(start: str, end: str) -> pd.DataFrame:
    with _engine.connect() as conn:
        return pd.read_sql_query(
            text(
                "SELECT * FROM player_data "
                "WHERE timestamp BETWEEN :start AND :end "
                "ORDER BY timestamp"
            ),
            conn,
            params={"start": start, "end": end},
        )


def save_start_snapshot(df: pd.DataFrame) -> None:
    """Freeze the competition baseline. No-op if one already exists."""
    with _engine.begin() as conn:
        existing = conn.execute(text("SELECT COUNT(*) FROM start_snapshot")).scalar()
        if existing:
            return
        df = dedupe(df)
        df["timestamp"] = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        df[_COLS].to_sql("start_snapshot", conn, if_exists="append", index=False)
    print(f"[db] start snapshot frozen — {len(df)} players")


def load_start_snapshot() -> pd.DataFrame:
    with _engine.connect() as conn:
        return pd.read_sql_query(text("SELECT * FROM start_snapshot"), conn)


def snapshot_at(ts: datetime) -> pd.DataFrame:
    """Latest row per player at or before ts (for the frozen end-of-comp state)."""
    with _engine.connect() as conn:
        return pd.read_sql_query(
            text(
                "SELECT DISTINCT ON (discord_id, ei_name) * FROM player_data "
                "WHERE timestamp <= :ts "
                "ORDER BY discord_id, ei_name, timestamp DESC"
            ),
            conn,
            params={"ts": ts},
        )


def upsert_participants(df: pd.DataFrame) -> None:
    """Insert/update registrations keyed on discord_id."""
    if df.empty:
        return
    now = datetime.now(timezone.utc)
    with _engine.begin() as conn:
        for row in df.itertuples(index=False):
            conn.execute(
                text(
                    "INSERT INTO participants "
                    "(discord_id, discord_name, ei_name, guild, registered_at) "
                    "VALUES (:id, :dname, :ei, :guild, :ts) "
                    "ON CONFLICT (discord_id) DO UPDATE SET "
                    "discord_name = EXCLUDED.discord_name, "
                    "ei_name = EXCLUDED.ei_name, "
                    "guild = EXCLUDED.guild"
                ),
                {"id": row.discord_id, "dname": row.discord_name,
                 "ei": row.ei_name, "guild": row.guild, "ts": now},
            )


def load_participants() -> pd.DataFrame:
    with _engine.connect() as conn:
        return pd.read_sql_query(text("SELECT * FROM participants"), conn)
