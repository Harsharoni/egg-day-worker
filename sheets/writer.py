import gspread
import pandas as pd
from datetime import datetime
from google.oauth2.service_account import Credentials
from config import (
    GOOGLE_SERVICE_ACCOUNT_FILE,
    SPREADSHEET_ID,
    SCOREBOARD_WORKSHEET,
)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _open_worksheet(sheet_name: str) -> gspread.Worksheet:
    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=_SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SPREADSHEET_ID).worksheet(sheet_name)


def _dump(sheet_name: str, df: pd.DataFrame, cols: list[str], header: list[str]) -> None:
    """
    Raw data dump: header row at A1, data below, timestamp one column
    to the right of the data. Display tabs pull from here via QUERY/FILTER;
    no formatting is applied or preserved on this tab.
    """
    ws = _open_worksheet(sheet_name)

    n_cols = len(cols)
    clear_col = gspread.utils.rowcol_to_a1(1, n_cols)[:-1]
    ts_col = gspread.utils.rowcol_to_a1(1, n_cols + 2)[:-1]

    ws.batch_clear([f"A1:{clear_col}6000"])
    data = [header] + df[cols].values.tolist()
    ws.update(values=data, range_name=f"A1:{clear_col}{len(data)}")

    time_str = f"Last Updated: {datetime.now().strftime('%d %b %Y, %H:%M')}"
    ws.update(range_name=f"{ts_col}1", values=[[time_str]])

    print(f"[sheets] wrote {len(df)} rows to '{sheet_name}'")


def write_scoreboard(df: pd.DataFrame) -> None:
    stat_cols = []
    stat_header = []
    for short, label in [
        ("se", "SE"), ("eb", "EB"), ("pe", "PE"),
        ("te", "TE"), ("mer", "MER"), ("prestiges", "Prestiges"),
    ]:
        stat_cols += [f"{short}_start", f"{short}_end", f"{short}_gain"]
        stat_header += [f"{label} Start", f"{label} End", f"{label} Gain"]

    _dump(
        SCOREBOARD_WORKSHEET,
        df,
        cols=["rank", "discord_id", "discord_name", "ei_name", "guild"]
             + stat_cols + ["fair_factor", "score"],
        header=["Rank", "Discord ID", "Discord Name", "EI Name", "Guild"]
               + stat_header + ["Fair Factor", "Score"],
    )
