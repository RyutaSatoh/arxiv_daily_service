import requests
from bs4 import BeautifulSoup
import re

ARXIV_URL = "https://arxiv.org/list/cs.CV/new"

def fetch_papers():
    """
    Fetches the list of new papers from arXiv cs.CV.
    Only includes "New submissions" and "Cross-lists". Ignores "Replacements".
    Uses the counts provided in the headers to determine how many papers to fetch.
    """
    try:
        response = requests.get(ARXIV_URL)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching URL: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # 1. Determine how many papers to fetch by parsing headers
    total_new = 0
    total_cross = 0
    
    headers = soup.find_all('h3')
    for h in headers:
        text = h.text.lower()
        # Look for patterns like "showing 56 of 56 entries"
        match = re.search(r'showing (\d+) of \d+ entries', text)
        count = int(match.group(1)) if match else 0
        
        if "new submissions" in text:
            total_new = count
        elif "cross submissions" in text or "cross-lists" in text:
            total_cross = count
            
    total_to_fetch = total_new + total_cross
    print(f"Expected: New={total_new}, Cross={total_cross} | Total={total_to_fetch}")
    
    if total_to_fetch == 0:
        # Fallback: if headers not found, maybe it's the weekend or a different layout
        print("Warning: Could not parse counts from headers. Falling back to first DL.")
        total_to_fetch = 1000 # Just a large number
        
    # 2. Collect all dt/dd pairs from the page until we hit the count
    papers = []
    all_dls = soup.find_all('dl')
    
    for dl in all_dls:
        dts = dl.find_all('dt')
        dds = dl.find_all('dd')
        
        for dt, dd in zip(dts, dds):
            if len(papers) >= total_to_fetch:
                break
                
            paper = {}
            anchor = dt.find('a', title='Abstract')
            if anchor:
                paper['id'] = anchor.text.strip()
                paper['url'] = f"https://arxiv.org{anchor['href']}"
            
            title_div = dd.find('div', class_='list-title')
            if title_div:
                paper['title'] = title_div.text.replace('Title:', '').strip()
                
            authors_div = dd.find('div', class_='list-authors')
            if authors_div:
                authors_text = authors_div.text.replace('Authors:', '').strip()
                paper['authors'] = ' '.join(authors_text.split())

            if 'url' in paper:
                try:
                    paper_resp = requests.get(paper['url'])
                    if paper_resp.status_code == 200:
                        paper_soup = BeautifulSoup(paper_resp.content, 'html.parser')
                        abs_block = paper_soup.find('blockquote', class_='abstract')
                        if abs_block:
                            paper['abstract'] = abs_block.text.replace('Abstract:', '').strip()
                except Exception as e:
                    print(f"Error fetching abstract for {paper.get('id')}: {e}")

            papers.append(paper)
        
        if len(papers) >= total_to_fetch:
            break

    print(f"Actually fetched: {len(papers)} papers.")
    return papers

if __name__ == "__main__":
    # Test run
    results = fetch_papers()
    print(f"Fetched {len(results)} papers.")
    if results:
        print(results[0])
