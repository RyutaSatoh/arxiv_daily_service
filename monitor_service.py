import time
import datetime
import requests
from bs4 import BeautifulSoup
import os
import main_job
import re

# Check every 30 minutes
CHECK_INTERVAL = 30 * 60 
ARXIV_URL = "https://arxiv.org/list/cs.CV/new"
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

def get_current_arxiv_header():
    try:
        response = requests.get(ARXIV_URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # The date header is usually the first h3
        # e.g. "Showing new listings for Tuesday, 13 January 2026"
        h3s = soup.find_all('h3')
        for h3 in h3s:
            text = h3.text.strip()
            if "Showing new listings" in text:
                return text
        return None
    except Exception as e:
        print(f"Error checking arXiv: {e}")
        return None

def parse_date_from_header(header_text):
    """
    Parses "Showing new listings for Tuesday, 13 January 2026"
    into "2026-01-13".
    """
    # Regex to find the date part: DayName, Day Month Year
    # e.g. "Tuesday, 13 January 2026"
    try:
        # Remove prefix
        date_str = header_text.replace("Showing new listings for", "").strip()
        # Parse format: %A, %d %B %Y
        dt = datetime.datetime.strptime(date_str, "%A, %d %B %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError as e:
        print(f"Error parsing date from header '{header_text}': {e}")
        return None

def monitor_loop():
    print(f"Starting arXiv monitor service. Checking every {CHECK_INTERVAL} seconds.")
    
    while True:
        print(f"Checking arXiv at {datetime.datetime.now()}...")
        current_header = get_current_arxiv_header()
        
        if current_header:
            target_date_str = parse_date_from_header(current_header)
            
            if target_date_str:
                json_path = os.path.join(DATA_DIR, f"{target_date_str}.json")
                
                if os.path.exists(json_path):
                    print(f"Data for {target_date_str} already exists. No update needed.")
                else:
                    print(f"New data detected for {target_date_str} (File missing). Starting job...")
                    try:
                        main_job.run_daily_job()
                        
                        if os.path.exists(json_path):
                            print(f"Successfully created {json_path}.")
                        else:
                            print(f"Job ran, but {json_path} was not found. Main job might have saved with system date.")
                            # Check if a file with system date exists
                            sys_date = datetime.datetime.now().strftime('%Y-%m-%d')
                            sys_path = os.path.join(DATA_DIR, f"{sys_date}.json")
                            if os.path.exists(sys_path) and sys_date != target_date_str:
                                print(f"Renaming {sys_path} to {json_path} to match arXiv header.")
                                os.rename(sys_path, json_path)
                            
                    except Exception as e:
                        print(f"Error running daily job: {e}")
            else:
                print("Could not parse date from header.")
        else:
            print("Could not retrieve header.")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    monitor_loop()