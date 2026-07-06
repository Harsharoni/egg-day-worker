import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import sys
from datetime import datetime, timedelta


# Check if correct number of arguments are provided
# if len(sys.argv) != 3:
#     print("Usage: python script_name.py <start_date> <end_date>")
#     sys.exit(1)

# Extract start_date and end_date from command line arguments
end_time = datetime.now().replace(minute=0, second=0, microsecond=0)
start_time = end_time - timedelta(hours=1)

start_timestamp = start_time.strftime('%Y-%m-%d %H:%M')
end_timestamp = end_time.strftime('%Y-%m-%d %H:%M')
try:
    limit = int(sys.argv[3])
except (IndexError, ValueError):
    limit = 50  # Default value

# Function to fetch data from SQLite database based on a query
def fetch_data_from_sqlite(query):
    conn = sqlite3.connect('player_data.db')
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return rows

# SQL Query with date range
query = f"""
SELECT 
    ROW_NUMBER() OVER (ORDER BY raw_gain DESC) AS Row,
    Name, 
    CASE 
        WHEN raw_gain / 1e18 > 1000 
            THEN printf('%.2fs', raw_gain / 1e21)
        ELSE CAST(CEIL(raw_gain / 1e18) AS INTEGER) || 'Q'
    END AS SE_Gain,
    CASE 
        WHEN max_rank < min_rank THEN min_rank || ' ↗ ' || max_rank
        WHEN max_rank > min_rank THEN min_rank || ' ↘ ' || max_rank
        ELSE min_rank || ' → ' || max_rank
    END AS Rank_Diff,
    MIN_SE || 's' AS Min_SE,
    MAX_SE || 's' AS Max_SE,
    CASE 
        WHEN first_mer < last_mer THEN first_mer || ' ↗ ' || last_mer
        WHEN first_mer > last_mer THEN first_mer || ' ↘ ' || last_mer
        ELSE first_mer || ' → ' || last_mer
    END AS mer_diff
FROM (
    SELECT 
        Name, 
        MAX(SE_RAW) - MIN(SE_RAW) AS raw_gain,
        MIN(CASE WHEN rn_asc = 1 THEN Rank END) AS min_rank,
        MIN(CASE WHEN rn_desc = 1 THEN Rank END) AS max_rank,
        MIN(SE_RAW) AS min_se_raw,
        MAX(SE_RAW) AS max_se_raw,
        ROUND(MIN(SE_RAW) / 1e21, 2) AS MIN_SE,
        ROUND(MAX(SE_RAW) / 1e21, 2) AS MAX_SE,
        MIN(CASE WHEN rn_asc = 1 THEN MER END) AS first_mer,
        MAX(CASE WHEN rn_desc = 1 THEN MER END) AS last_mer
    FROM (
        SELECT 
            Name,
            Rank,
            SE_RAW,
            MER,
            ROW_NUMBER() OVER (PARTITION BY Name ORDER BY Timestamp ASC) AS rn_asc,
            ROW_NUMBER() OVER (PARTITION BY Name ORDER BY Timestamp DESC) AS rn_desc
        FROM 
            player_data
        WHERE 
            Timestamp BETWEEN '{start_timestamp}' AND '{end_timestamp}'
    ) AS ranked_data
    WHERE 
        rn_asc = 1 OR rn_desc = 1
    GROUP BY 
        Name
) AS subquery
WHERE 
    raw_gain >= 1e18
ORDER BY 
    raw_gain DESC
LIMIT {limit};
"""

# Fetch data from SQLite into a list of tuples
data = fetch_data_from_sqlite(query)

# Define column names based on the query
columns = ["", "Name", "Farmed", "Leaderboard", start_timestamp, end_timestamp, "MER"]

# Create a DataFrame
df = pd.DataFrame(data, columns=columns)

# Set the style for the plot
sns.set(style="whitegrid")

# Create a matplotlib figure
fig, ax = plt.subplots(figsize=(10, 8))
fig.patch.set_visible(False)
ax.axis('off')

# Create the table
table = ax.table(cellText=df.values, colLabels=df.columns, cellLoc='center', loc='center')
table.auto_set_font_size(False)
table.set_fontsize(12)
table.scale(1.3, 2)

# Adjust column widths dynamically based on max length
cell_dict = table.get_celld()
for i, column in enumerate(df.columns):
    max_length = max(df[column].astype(str).map(len).max(), len(column))
    for j in range(len(df) + 1):
        cell_dict[j, i].set_width(0.08 + 0.01 * max_length)

# Style the table with contrasting colors
for (i, j), cell in cell_dict.items():
    cell.set_edgecolor('black')
    if i == 0:
        cell.set_text_props(weight='bold', color='white')
        cell.set_facecolor('#F28A02')  # Header row color
    else:
        cell.set_facecolor('#F9EBC8' if i % 2 == 0 else '#FFF4EB')  # Alternating row colors

# Save the figure
image_filename = f'gains/se_gains_{start_timestamp}_to_{end_timestamp}_100Q_cut-off.png'
plt.savefig(image_filename, bbox_inches='tight', dpi=90)

print(f"Image se_gains_{start_timestamp}_to_{end_timestamp}.png generated successfully.")
