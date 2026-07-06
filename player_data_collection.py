#!/usr/bin/env python
# coding: utf-8

import requests
import pandas as pd
import numpy as np
from io import StringIO
import math
import sqlite3
from datetime import datetime
from collections import defaultdict

TOKEN = "YOUR_COOKIE_HERE"  # Replace with your actual cookie string

multipliers = {
    "d": 1e33, "N": 1e30, "o": 1e27, "S": 1e24,
    "s": 1e21, "Q": 1e18, "q": 1e15, "T": 1e12,
    "B": 1e9, "M": 1e6, "K": 1e3
}

def se_to_raw(SE):
    SE = SE.replace(" ", "")
    if not SE:
        print(f"[WARN] Empty SE value.")
        return 0

    if SE[-1].isalpha() and SE[-1] in multipliers:
        try:
            return float(SE[:-1]) * multipliers[SE[-1]]
        except ValueError:
            print(f"[WARN] Could not parse suffixed SE: {SE}")
            return 0
    else:
        try:
            return float(SE)
        except ValueError:
            print(f"[WARN] Could not parse plain SE: {SE}")
            return 0

def mer(se, pe):
    return round((91 * (math.log10(se) + (0 - 18)) + 200 - pe) / 10, 1)

def fetch_leaderboard_data():
    url = 'https://egg9000.com/Home/Leaderboard?sortby=se'
    headers = {
        'Cookie': f'egg9000Cookie={TOKEN}'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def parse_leaderboard(html_content):
    html_buffer = StringIO(html_content)
    df = pd.read_html(html_buffer)[0]
    df.drop(['Unnamed: 5', 'Coops', 'BG'], axis=1, inplace=True)
    df.rename(columns={'Unnamed: 3': 'PE', 'Unnamed: 0': 'Rank', 'Unnamed: 2': 'SE'}, inplace=True)

    df['PE'] = df['PE'].astype(int)
    df['SE_RAW'] = df['SE'].apply(se_to_raw)
    df['SE'] = df['SE'].str.replace(" ", "")
    df['MER'] = df.apply(lambda row: mer(row['SE_RAW'], row['PE']), axis=1)
    df['EB'] = df['EB'].str.replace(" ", "")
    df.sort_values(by=['SE_RAW'], ascending=False, inplace=True)
    df.index = np.arange(1, len(df) + 1)
    return df

def initialize_db(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_data (
            AccountID TEXT,
            Name TEXT,
            SE TEXT,
            SE_RAW INTEGER,
            Rank INTEGER,
            PE INTEGER,
            EB TEXT,
            Timestamp TEXT,
            PRIMARY KEY (AccountID, Timestamp)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS latest_snapshot (
            AccountID TEXT,
            Name TEXT,
            SE TEXT,
            SE_RAW INTEGER,
            Rank INTEGER,
            PE INTEGER,
            EB TEXT,
            Timestamp TEXT
        )
    """)
    conn.commit()

def save_to_sqlite(df, db_name='player_data.db'):
    conn = sqlite3.connect(db_name)
    initialize_db(conn)

    current_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    df['Timestamp'] = current_time
    cols = ['AccountID', 'Name', 'SE', 'SE_RAW', 'Rank', 'PE', 'EB', 'Timestamp']
    df = df[cols]

    # Save history
    df.to_sql('player_data', conn, if_exists='append', index=False)

    # Save clean snapshot
    df.to_sql('latest_snapshot', conn, if_exists='replace', index=False)

    print(f"[INFO] Saved {len(df)} rows to history and snapshot.")
    print(df.head())
    conn.close()

def run_data_collection():
    html_content = fetch_leaderboard_data()
    leaderboard_df = parse_leaderboard(html_content)

    name_counter = defaultdict(int)
    account_ids = []

    for _, row in leaderboard_df.iterrows():
        name = row['Name']
        name_counter[name] += 1
        account_id = f"{name}_{name_counter[name]}"
        account_ids.append(account_id)

    leaderboard_df['AccountID'] = account_ids
    save_to_sqlite(leaderboard_df)

if __name__ == '__main__':
    run_data_collection()