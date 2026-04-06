import scraper
import summarizer
import storage
import datetime
import sys

import os
import scraper
import summarizer
import storage
import datetime
import sys
from batch_processor import BatchProcessor

def run_daily_job():
    print(f"Starting job at {datetime.datetime.now()}")
    
    # 1. Fetch
    print("Fetching papers from arXiv...")
    papers, date_str = scraper.fetch_papers()
    print(f"Fetched {len(papers)} papers for date {date_str}.")
    
    if not papers:
        print("No papers found or error fetching.")
        return

    # 2. Check for existing data to resume/retry
    existing_data = storage.load_daily_data(date_str)
    existing_map = {p['id']: p for p in existing_data} if existing_data else {}
    
    papers_to_process = []
    processed_papers = [] # Final list in order

    for p in papers:
        existing_p = existing_map.get(p['id'])
        if existing_p and "summary_ja" in existing_p and existing_p["summary_ja"] != "要約生成エラー":
            processed_papers.append(existing_p)
        else:
            papers_to_process.append(p)
            processed_papers.append(p)

    print(f"Status: {len(existing_map)} already in storage, {len(papers_to_process)} need summarization.")

    if not papers_to_process:
        print("All papers already summarized. Skipping.")
        return

    # 3. Choose Path: Sync (Immediate) vs Batch (Scheduled)
    enable_sync = os.environ.get("ENABLE_SYNC_SUMMARIZATION") == "true"
    
    if enable_sync:
        print("!!! EMERGENCY FALLBACK: Running Synchronous Summarization !!!")
        newly_summarized = summarizer.summarize_and_translate(papers_to_process)
        # Merge back
        summarized_map = {p['id']: p for p in newly_summarized}
        for i, p in enumerate(processed_papers):
            if p['id'] in summarized_map:
                processed_papers[i] = summarized_map[p['id']]
        
        print(f"Saving data to {date_str}...")
        storage.save_daily_data(processed_papers, date_str)
    else:
        # Default: Use Batch API (50% OFF)
        print("Mode: Batch API (Cost-saving). Submitting job...")
        # Save initial data first so we don't forget the fetch
        storage.save_daily_data(processed_papers, date_str)
        
        bp = BatchProcessor()
        job_id = bp.submit_summary_batch(date_str, papers_to_process)
        print(f"Batch job submitted successfully: {job_id}")
        print("Result will be picked up by monitor_service once completed (up to 24h).")

    print("Job complete.")

if __name__ == "__main__":
    run_daily_job()
