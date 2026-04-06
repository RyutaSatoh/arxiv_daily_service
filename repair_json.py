import storage
import summarizer
import datetime
import os

DATE_STR = "2026-04-02"

def repair():
    print(f"Starting repair for {DATE_STR}")
    
    # 1. Load existing data
    data = storage.load_daily_data(DATE_STR)
    if not data:
        print(f"No data found for {DATE_STR}")
        return

    # 2. Identify needs
    to_process = []
    for p in data:
        if p.get("summary_ja") == "要約生成エラー" or not p.get("summary_ja"):
            to_process.append(p)
            
    print(f"Total papers: {len(data)}, Needs repair: {len(to_process)}")
    
    if not to_process:
        print("No repairs needed.")
        return

    # 3. Summarize (Only the ones needing it)
    print(f"Repairing {len(to_process)} papers...")
    newly_summarized = summarizer.summarize_and_translate(to_process)
    
    # 4. Merge back
    summarized_map = {p['id']: p for p in newly_summarized}
    for i, p in enumerate(data):
        if p['id'] in summarized_map:
            data[i] = summarized_map[p['id']]
            
    # 5. Save
    storage.save_daily_data(data, DATE_STR)
    print("Repair complete.")

if __name__ == "__main__":
    repair()
