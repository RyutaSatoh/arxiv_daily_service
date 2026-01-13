import scraper
import summarizer
import storage
import datetime
import sys

def run_daily_job():
    print(f"Starting job at {datetime.datetime.now()}")
    
    # 1. Fetch
    print("Fetching papers from arXiv...")
    papers = scraper.fetch_papers()
    print(f"Fetched {len(papers)} papers.")
    
    if not papers:
        print("No papers found or error fetching.")
        return

    # 2. Summarize & Translate
    print("Summarizing and translating...")
    # For testing purposes, you might want to limit the number of papers
    # processed_papers = summarizer.summarize_and_translate(papers[:3]) # Uncomment to test with 3
    processed_papers = summarizer.summarize_and_translate(papers)
    
    # 3. Save
    print("Saving data...")
    storage.save_daily_data(processed_papers)
    print("Job complete.")

if __name__ == "__main__":
    run_daily_job()
