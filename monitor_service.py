import time
import datetime
import requests
from bs4 import BeautifulSoup
import os
import main_job
import re
import storage
import scraper
from batch_processor import BatchProcessor

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

def is_json_complete(json_path):
    """Checks if the JSON file exists and has summarized content."""
    if not os.path.exists(json_path):
        return False
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            if not data: return False
            # Check a sample of papers for summaries
            # If any paper has 'summary_ja' and it's not an error string, consider it good
            # Or check if ALL papers have it.
            for p in data[:5]: # Check first 5
                if "summary_ja" not in p or p["summary_ja"] == "要約生成エラー":
                    return False
            return True
    except:
        return False

def monitor_loop():
    print(f"Starting arXiv monitor service with Batch API support. Checking every {CHECK_INTERVAL} seconds.")
    bp = BatchProcessor()
    
    while True:
        print(f"Checking status at {datetime.datetime.now()}...")
        
        # 1. Process any completed Batch Jobs
        try:
            bp.check_jobs()
            bp.process_completed_jobs(storage)
        except Exception as e:
            print(f"Error checking batch jobs: {e}")

        # 2. Check arXiv for new listings
        current_header = get_current_arxiv_header()
        
        if current_header:
            target_date_str = parse_date_from_header(current_header)
            
            if target_date_str:
                json_path = os.path.join(DATA_DIR, f"{target_date_str}.json")
                
                if is_json_complete(json_path):
                    print(f"Data for {target_date_str} is complete.")
                else:
                    print(f"Data for {target_date_str} is missing or incomplete. Processing...")
                    try:
                        # Fetch the list
                        papers, date_str = scraper.fetch_papers()
                        if papers:
                            # Save initial data
                            storage.save_daily_data(papers, date_str)
                            
                            # Submit to Batch API (50% Cost)
                            print(f"Submitting Batch Job for {date_str}...")
                            job_id = bp.submit_summary_batch(date_str, papers)
                            if job_id:
                                print(f"Summary batch job submitted: {job_id}")
                            else:
                                print("Batch submission returned no ID. Falling back to sync processing?")
                                # Fallback option: main_job.run_daily_job()
                        else:
                            print("No papers fetched from arXiv.")
                            
                    except Exception as e:
                        print(f"Error in monitor processing for {target_date_str}: {e}")
            else:
                print("Could not parse date from header.")
        else:
            print("Could not retrieve header.")
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    monitor_loop()