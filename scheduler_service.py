import schedule
import time
import main_job
import datetime

def job():
    print(f"Running scheduled job: {datetime.datetime.now()}")
    try:
        main_job.run_daily_job()
    except Exception as e:
        print(f"Job failed: {e}")

# Schedule the job every day at a specific time (e.g., 10:00 AM)
# You can change this time as needed.
schedule.every().day.at("10:00").do(job)

print("Scheduler started. Waiting for next job...")
# Also run once immediately on startup if needed, or just wait.
# main_job.run_daily_job() # Uncomment to run immediately

while True:
    schedule.run_pending()
    time.sleep(60)
