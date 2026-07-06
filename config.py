import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

EGG9000_API_KEY: str = os.environ["EGG9000_API_KEY"]

GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "creds.json")

# Spreadsheet IDs (the long token in the sheet URL between /d/ and /edit).
# Opening by ID needs only the Sheets API scope; opening by name would
# require the Drive API.
SPREADSHEET_ID: str = os.environ["SPREADSHEET_ID"]
SCOREBOARD_WORKSHEET: str = os.getenv("SCOREBOARD_WORKSHEET", "Scoreboard")

# Google Form responses spreadsheet for registration. Leave ID empty to
# disable registration sync.
REGISTRATION_SPREADSHEET_ID: str = os.getenv("REGISTRATION_SPREADSHEET_ID", "")
REGISTRATION_WORKSHEET: str = os.getenv("REGISTRATION_WORKSHEET", "Form Responses 1")

POLL_INTERVAL_MINUTES: int = int(os.getenv("POLL_INTERVAL_MINUTES", "30"))

REPORT_MIN_GAIN: float = float(os.getenv("REPORT_MIN_GAIN", "1e18"))
REPORT_LIMIT: int = int(os.getenv("REPORT_LIMIT", "50"))

DATABASE_URL: str = os.environ["DATABASE_URL"]

# Competition window (UTC). 15/07/2026 17:00 BST -> 16:00 UTC,
# 16/07/2026 18:30 BST -> 17:30 UTC.
COMP_START_UTC = datetime.fromisoformat(
    os.getenv("COMP_START_UTC", "2026-07-15T16:00:00+00:00")
)
COMP_END_UTC = datetime.fromisoformat(
    os.getenv("COMP_END_UTC", "2026-07-16T17:30:00+00:00")
)

FAIR_POWER: float = float(os.getenv("FAIR_POWER", "0.235"))
