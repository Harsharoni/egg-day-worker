import time
from datetime import datetime, timedelta
from player_data_collection import run_data_collection
from update_sheet import update_google_sheet




def run_hourly_tasks():
    while True:
        now = datetime.now()
        next_half_hour = (now + timedelta(minutes=30)).replace(second=0, microsecond=0)

        if now.minute >= 30:
            next_half_hour = next_half_hour.replace(minute=0)
            next_half_hour += timedelta(hours=1)
        else:
            next_half_hour = next_half_hour.replace(minute=30)
        sleep_duration = (next_half_hour - now).total_seconds()

        print(f"[INFO] Sleeping for {int(sleep_duration)} seconds until {next_half_hour.strftime('%H:%M')}")
        time.sleep(sleep_duration)

        print(f"[INFO] Running data collection at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        run_data_collection()

        print(f"[INFO] Updating Google Sheet at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        update_google_sheet()

if __name__ == "__main__":
    run_hourly_tasks()

