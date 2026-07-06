import sqlite3
import pandas as pd
import gspread
from datetime import datetime


def update_google_sheet():
    now = datetime.now()
    last_update = now.replace(minute=0, second=0, microsecond=0)
    elapsed = int((now-last_update).total_seconds()//60)
    formatted_time = now.strftime("%d %b %Y, %H:%M")
    time_string = f"Last Updated: {formatted_time}"
    now = datetime.now()


    # Set up Google Sheets API
    client = gspread.service_account(filename="creds.json")

    # Open your sheet by name
    spreadsheet = client.open("EggDay 2025 Comp")
    worksheet = spreadsheet.worksheet("End LB")

    # Connect to the database
    conn = sqlite3.connect("player_data.db")
    query = """
SELECT Name, SE, PE, EB
FROM latest_snapshot
ORDER BY SE_RAW DESC
"""
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Compute EB from SE_RAW and PE

    # Get target values
    names = df["Name"].tolist()
    se = df["SE"].tolist()
    pe = df["PE"].tolist()
    eb = df["EB"].tolist()

    # Compute the number of rows
    num_rows = len(names)


    # Write each column starting at the right cell
    worksheet.update(range_name='J1', values=[[time_string]])
    worksheet.format('J1', {
        "horizontalAlignment": "CENTER",
        "textFormat": {"bold": True}
    })
    worksheet.batch_clear(['K13:N6000'])
    worksheet.update(values=[[n] for n in names], range_name=f'K13:K{12+num_rows}')
    worksheet.update(values=[[s] for s in se],    range_name=f'L13:L{12+num_rows}')
    worksheet.update(values=[[p] for p in pe],    range_name=f'M13:M{12+num_rows}')
    worksheet.update(values=[[e] for e in eb],    range_name=f'N13:N{12+num_rows}')
    print(f"? Updated {num_rows} rows in sheet 'End LB'")

if __name__ == "__main__":
    update_google_sheet()