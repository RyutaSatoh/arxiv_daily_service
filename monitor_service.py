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
    try:
        date_str = header_text.replace("Showing new listings for", "").strip()
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
            # Check if at least some papers have valid summaries
            # (April 6th is currently blank, so this will return False)
            summarized_count = 0
            for p in data[:10]: # Check first 10
                if "summary_ja" in p and p["summary_ja"] != "要約生成エラー" and p["summary_ja"].strip() != "":
                    summarized_count += 1
            return summarized_count >= 1
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
                    # Check if a batch job is already in progress for this date
                    if bp.is_job_running('summary', target_date_str):
                        print(f"Batch summary job for {target_date_str} is still running. Waiting...")
                    else:
                        print(f"Data for {target_date_str} is missing or incomplete. Processing...")
                        try:
                            papers = []
                            existing_data = storage.load_daily_data(target_date_str)
                            
                            if not existing_data:
                                fetched_papers, date_str = scraper.fetch_papers()
                                if fetched_papers:
                                    papers = fetched_papers
                                    storage.save_daily_data(papers, date_str)
                            else:
                                papers = existing_data
                                
                            if papers:
                                to_process = []
                                for p in papers:
                                    if p.get("summary_ja") == "要約生成エラー" or not p.get("summary_ja") or str(p.get("summary_ja")).strip() == "":
                                        to_process.append(p)
                                
                                if to_process:
                                    print(f"Submitting Batch Job for {len(to_process)} missing papers on {target_date_str}...")
                                    job_id = bp.submit_summary_batch(target_date_str, to_process)
                                    if job_id:
                                        print(f"Summary batch job submitted: {job_id}")
                                    else:
                                        print("Batch submission failed.")
                                else:
                                    print("No papers actually need processing.")
                            else:
                                print("No papers fetched or loaded.")
                                
                        except Exception as e:
                            print(f"Error in monitor processing for {target_date_str}: {e}")
            else:
                print("Could not parse date from header.")
        
        # Also check for 4/6 repair if it's not complete
        repair_date = "2026-04-06"
        if not is_json_complete(os.path.join(DATA_DIR, f"{repair_date}.json")):
            if not bp.is_job_running('summary', repair_date):
                print(f"Repairing {repair_date} via Batch...")
                # In a real scenario, we'd load the papers and submit.
                # For now, it will be handled when main_job logic triggers it or manually.
                pass
            else:
                print(f"Repair batch for {repair_date} is running.")

        time.sleep(CHECK_INTERVAL)
if __name__ == "__main__":
    monitor_loop()
