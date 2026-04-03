import os
import google.generativeai as genai
import time
import json
import re
import logging

# Configure logging
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
    
logging.basicConfig(
    filename=os.path.join(LOG_DIR, 'summarizer.log'),
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

def configure_genai():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        error_msg = "GEMINI_API_KEY environment variable not set."
        logging.error(error_msg)
        raise ValueError(error_msg)
    genai.configure(api_key=api_key)

def process_batch(model, batch_papers):
    """
    Processes a batch of papers using a single API call.
    Returns a list of dictionaries with 'summary_ja' and 'contribution_ja'.
    """
    
    papers_text = ""
    for i, paper in enumerate(batch_papers):
        papers_text += f"--- PAPER {i+1} ---\n"
        papers_text += f"Title: {paper.get('title', '')}\n"
        papers_text += f"Abstract: {paper.get('abstract', '')}\n\n"

    prompt = f"""
    You are an expert researcher. Please read the following {len(batch_papers)} papers (titles and abstracts) and provide a Japanese summary for each.

    For each paper, extract:
    1. "summary_ja": A concise summary of the abstract in Japanese.
    2. "contribution_ja": A one-sentence statement of the main contribution in Japanese.

    Input Data:
    {papers_text}

    Output Format:
    Return a strictly valid JSON array of objects. Each object must correspond to the input papers in the same order.
    Do not include markdown formatting (like ```json). Just the raw JSON string.
    Example structure:
    [
        {{"summary_ja": "...", "contribution_ja": "..."}},
        {{"summary_ja": "...", "contribution_ja": "..."}}
    ]
    """

    max_retries = 5 # Increased for free tier
    for attempt in range(max_retries):
        try:
            logging.info(f"Generating content for batch (size {len(batch_papers)}), attempt {attempt+1}")
            response = model.generate_content(prompt)
            text = response.text.strip()
            
            # Clean up potential markdown code blocks if the model adds them
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            results = json.loads(text.strip())
            
            if not isinstance(results, list) or len(results) != len(batch_papers):
                 logging.error(f"Invalid JSON structure or length mismatch. Expected {len(batch_papers)}, got {len(results) if isinstance(results, list) else 'type:' + str(type(results))}")
                 raise ValueError(f"Expected list of length {len(batch_papers)}")
                 
            return results

        except Exception as e:
            error_str = str(e)
            logging.warning(f"Batch processing error (attempt {attempt+1}): {error_str}")
            
            if attempt < max_retries - 1:
                # Try to parse recommended retry delay from error message
                # e.g. "Please retry in 17.185952805s."
                delay = 10 * (2 ** attempt) # Default exponential backoff: 10, 20, 40, 80...
                
                match = re.search(r'retry in ([\d\.]+)s', error_str)
                if match:
                    delay = float(match.group(1)) + 1.0 # Add 1s buffer
                    logging.info(f"Parsed recommended retry delay: {delay}s")
                else:
                    # Alternative format check: "seconds: 19"
                    match_sec = re.search(r'seconds: (\d+)', error_str)
                    if match_sec:
                        delay = float(match_sec.group(1)) + 2.0
                        logging.info(f"Parsed recommended retry seconds: {delay}s")

                logging.info(f"Waiting {delay}s before retry...")
                time.sleep(delay)
            else:
                logging.error(f"Failed to process batch after {max_retries} attempts.")
                logging.error(f"Raw Response Text (if available): {text if 'text' in locals() else 'None'}")
                return None

    return None

def summarize_and_translate(papers, batch_size=5):
    """
    Takes a list of paper dictionaries.
    Returns the list with added 'summary_ja' and 'contribution_ja' keys.
    Processes in batches to reduce API calls.
    """
    configure_genai()
    model = genai.GenerativeModel('gemini-3-flash-preview') # Using flash for speed/cost effectiveness

    processed_papers = []
    
    # Create batches
    for i in range(0, len(papers), batch_size):
        batch = papers[i:i + batch_size]
        logging.info(f"Processing batch {i//batch_size + 1} (Papers {i+1}-{min(i+batch_size, len(papers))})...")
        print(f"Processing batch {i//batch_size + 1} (Papers {i+1}-{min(i+batch_size, len(papers))})...")
        
        # Filter out papers with no abstract to avoid wasting tokens
        valid_indices = []
        clean_batch = []
        for idx, p in enumerate(batch):
            if p.get('abstract'):
                valid_indices.append(idx)
                clean_batch.append(p)
            else:
                p['summary_ja'] = "要約不可 (アブストラクトなし)"
                logging.info(f"Skipping paper {p.get('id')} (No abstract)")
        
        if clean_batch:
            results = process_batch(model, clean_batch)
            
            if results:
                for v_idx, res in zip(valid_indices, results):
                    batch[v_idx]['summary_ja'] = res.get('summary_ja', 'Error')
                    batch[v_idx]['contribution_ja'] = res.get('contribution_ja', 'Error')
            else:
                # Fallback: Mark as error if batch failed
                for v_idx in valid_indices:
                     batch[v_idx]['summary_ja'] = "要約生成エラー"
                     batch[v_idx]['contribution_ja'] = "-"
                     logging.error(f"Marked paper {batch[v_idx].get('id')} as Error due to batch failure")
        
        processed_papers.extend(batch)
        
        # Respect rate limits - Increased for free tier
        time.sleep(5.0)

    return processed_papers
