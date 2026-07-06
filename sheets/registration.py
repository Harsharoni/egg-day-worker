import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from config import (
    GOOGLE_SERVICE_ACCOUNT_FILE,
    REGISTRATION_SPREADSHEET_ID,
    REGISTRATION_WORKSHEET,
)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Form question headers are free text — match by substring, first hit wins.
_HEADER_MAP = [
    ("discord id", "discord_id"),
    ("egg inc", "ei_name"),
    ("guild", "guild"),
    ("discord", "discord_name"),
]


def fetch_registrations() -> pd.DataFrame:
    """
    Read the Google Form responses sheet.

    Returns DataFrame with columns: discord_id, discord_name, ei_name, guild.
    Rows with a non-numeric discord id are dropped (reported to stdout).
    Empty DataFrame if REGISTRATION_SPREADSHEET_ID is not configured.
    """
    if not REGISTRATION_SPREADSHEET_ID:
        return pd.DataFrame()

    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=_SCOPES)
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(REGISTRATION_SPREADSHEET_ID).worksheet(REGISTRATION_WORKSHEET)
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    renames = {}
    for col in df.columns:
        low = col.strip().lower()
        for needle, target in _HEADER_MAP:
            if needle in low and target not in renames.values():
                renames[col] = target
                break
    df.rename(columns=renames, inplace=True)

    missing = {"discord_id", "discord_name", "ei_name", "guild"} - set(df.columns)
    if missing:
        raise ValueError(f"registration sheet missing columns: {sorted(missing)}")

    df = df[["discord_id", "discord_name", "ei_name", "guild"]].copy()
    for col in ("discord_name", "ei_name", "guild"):
        df[col] = df[col].astype(str).str.strip()

    df["discord_id"] = pd.to_numeric(df["discord_id"], errors="coerce")
    bad = df["discord_id"].isna()
    if bad.any():
        for name in df.loc[bad, "discord_name"]:
            print(f"[registration] bad discord id, skipped: {name}")
        df = df[~bad]
    df["discord_id"] = df["discord_id"].astype("int64")

    df.drop_duplicates(subset="discord_id", keep="last", inplace=True)
    return df.reset_index(drop=True)
