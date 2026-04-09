import os
import json
import time
from google import genai
from google.genai import types
import logging

# Configure logging
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
    
logging.basicConfig(
    filename=os.path.join(LOG_DIR, 'batch_processor.log'),
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

JOBS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'batch_jobs.json')

class BatchProcessor:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required.")
        self.client = genai.Client(api_key=self.api_key, http_options={'api_version': 'v1beta'})

    def is_job_running(self, job_type, date_str, user=None):
        """Checks if a job of a certain type, date and optionally user is already running."""
        if not os.path.exists(JOBS_FILE):
            return False
        try:
            with open(JOBS_FILE, 'r') as f:
                jobs = json.load(f)
            for info in jobs.values():
                if info['status'] == 'RUNNING' and \
                   info['metadata'].get('type') == job_type and \
                   info['metadata'].get('date') == date_str:
                    
                    # If user is specified, check it too
                    if user and info['metadata'].get('user') != user:
                        continue
                        
                    return True
        except:
            return False
        return False

    def _save_job_info(self, job_id, metadata):
        jobs = {}
        if os.path.exists(JOBS_FILE):
            with open(JOBS_FILE, 'r') as f:
                try:
                    jobs = json.load(f)
                except json.JSONDecodeError:
                    jobs = {}
        
        jobs[job_id] = {
            "status": "RUNNING",
            "created_at": time.time(),
            "metadata": metadata # {type: 'summary'|'slide', date: ..., user: ...}
        }
        
        with open(JOBS_FILE, 'w') as f:
            json.dump(jobs, f, indent=2)

    def submit_summary_batch(self, date_str, papers):
        """Submits a batch job for paper summaries using OpenAI compatible format."""
        requests = []
        for p in papers:
            prompt = f"""
You are an expert researcher. Read the following paper title and abstract, then provide a Japanese summary.
Title: {p['title']}
Abstract: {p['abstract']}

CRITICAL INSTRUCTIONS:
1. Respond ONLY with a valid JSON object.
2. DO NOT use any Markdown formatting (like **, ###, *, -, etc.) inside the text values. The output must be plain text suitable for Text-to-Speech reading.

JSON Schema:
{{
    "summary_ja": "A concise Japanese summary of the abstract (plain text, 3-4 sentences).",
    "contribution_ja": "A one-sentence statement of the main contribution or novelty in Japanese (plain text)."
}}
"""
            # Construct OpenAI-compatible JSONL request format
            req = {
                "custom_id": p['id'],
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "gemini-3-flash-preview",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "response_format": {"type": "json_object"}
                }
            }
            requests.append(req)

        # Write to temp file
        temp_file = f"batch_summary_{date_str}.jsonl"
        with open(temp_file, 'w') as f:
            for req in requests:
                f.write(json.dumps(req) + '\n')

        # Upload and submit
        print(f"Uploading {temp_file}...")
        # argument name is 'file' and we specify mime_type
        try:
            gfile = self.client.files.upload(
                file=temp_file,
                config={'mime_type': 'application/jsonl'}
            )
            
            job = self.client.batches.create(
                model='models/gemini-3-flash-preview',
                src=gfile.name
            )
            
            print(f"Batch job submitted: {job.name}")
            self._save_job_info(job.name, {"type": "summary", "date": date_str})
            os.remove(temp_file)
            return job.name
        except Exception as e:
            logging.error(f"Error submitting summary batch: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise e

    def submit_slide_batch(self, username, date_str, papers, extractor):
        """Submits a batch job for slide content extraction."""
        import base64
        import io
        requests = []
        for p in papers:
            prompt = """
You are an expert Computer Vision researcher creating a high-quality technical presentation slide for a paper reading session (Journal Club).
Please read the paper deeply and extract the following information in JAPANESE.

CRITICAL INSTRUCTIONS:
- BE SPECIFIC and TECHNICAL. Do not use generic phrases like "improved performance" or "novel method". State HOW and BY HOW MUCH.
- Mention specific module names, mathematical concepts, or loss functions used.
- For Novelty: Explain exactly what mechanism allows it to surpass previous methods.
- For Validation: Mention the Dataset names (COCO, ImageNet) and Metrics.
- OUTPUT STRICTLY VALID JSON. Escape all backslashes. Do not use markdown blocks inside values.

JSON structure:
{
    "title_en": "Original English Title",
    "title_ja": "日本語のタイトル",
    "authors": "著者名 (First Author et al.)",
    "affiliations": "著者の所属 (筆頭著者の所属、または主要な機関名)",
    "summary": "どんなもの？（提案手法の核心となる技術名と、それが解決する具体的なタスク）",
    "novelty": "先行研究との明確な差分",
    "method_key": "技術のキモ（数式やアーキテクチャの具体的名称を用いて説明）",
    "validation": "検証方法と結果（データセット名と主要指標の数値を記載）",
    "discussion": "議論・課題",
    "next_paper": "次に読むべき論文",
    "figure1": { "page_index": 0, "bbox": [ymin, xmin, ymax, xmax], "description": "メソッドの概要図" },
    "figure2": { "page_index": 0, "bbox": [ymin, xmin, ymax, xmax], "description": "結果や効果を示す図" }
}

CRITICAL: 
- figure1: Must be the ARCHITECTURE/METHOD Diagram.
- figure2: Must be a RESULT comparison or Qualitative example.
- bbox: [0-1000] scale.
"""
            
            url = p.get('url')
            if not url: continue
            
            try:
                # We need to download and convert to images to send to Batch API
                pdf_stream = extractor._download_pdf(url)
                images, _ = extractor._pdf_to_images(pdf_stream, num_pages=4)
                
                contents = [{"type": "text", "text": prompt}]
                for img in images:
                    buffered = io.BytesIO()
                    img.save(buffered, format="JPEG", quality=80)
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    contents.append({
                        "type": "image_url", 
                        "image_url": {"url": f"data:image/jpeg;base64,{img_str}"}
                    })
                
                req = {
                    "custom_id": p['id'],
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "gemini-3-flash-preview",
                        "messages": [{"role": "user", "content": contents}],
                        "response_format": {"type": "json_object"}
                    }
                }
                requests.append(req)
            except Exception as e:
                logging.error(f"Error preparing slide batch for {url}: {e}")

        if not requests:
            logging.error("No valid requests generated for slide batch.")
            return None

        # Write to temp file
        temp_file = f"batch_slide_{username}_{date_str}.jsonl"
        with open(temp_file, 'w') as f:
            for req in requests:
                f.write(json.dumps(req) + '\n')

        print(f"Uploading slide batch {temp_file}...")
        try:
            gfile = self.client.files.upload(
                file=temp_file,
                config={'mime_type': 'application/jsonl'}
            )
            
            job = self.client.batches.create(
                model='models/gemini-3-flash-preview',
                src=gfile.name
            )
            
            print(f"Slide Batch job submitted: {job.name}")
            self._save_job_info(job.name, {"type": "slide", "date": date_str, "user": username})
            os.remove(temp_file)
            return job.name
        except Exception as e:
            logging.error(f"Error submitting slide batch: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise e

    def check_jobs(self):
        """Checks all active jobs and updates state."""
        if not os.path.exists(JOBS_FILE):
            return
            
        with open(JOBS_FILE, 'r') as f:
            try:
                jobs = json.load(f)
            except:
                return
            
        updated = False
        for job_id, info in list(jobs.items()):
            if info['status'] == 'COMPLETED' or info['status'] == 'FAILED':
                continue
                
            try:
                job = self.client.batches.get(name=job_id)
                state_str = str(job.state)
                if 'SUCCEEDED' in state_str:
                    print(f"Job {job_id} succeeded!")
                    info['status'] = 'COMPLETED'
                    info['completed_at'] = time.time()
                    info['output_uri'] = job.dest.file_name
                    updated = True
                elif any(x in state_str for x in ['FAILED', 'EXPIRED', 'CANCELLED']):
                    print(f"Job {job_id} failed: {state_str}")
                    info['status'] = 'FAILED'
                    updated = True
            except Exception as e:
                logging.error(f"Error checking job {job_id}: {e}")

        if updated:
            with open(JOBS_FILE, 'w') as f:
                json.dump(jobs, f, indent=2)

    def get_job_results(self, job_id):
        """Downloads and parses job results from OpenAI-style response."""
        if not os.path.exists(JOBS_FILE):
            return None
            
        with open(JOBS_FILE, 'r') as f:
            jobs = json.load(f)
            
        info = jobs.get(job_id)
        if not info or info['status'] != 'COMPLETED' or not info.get('output_uri'):
            return None

        try:
            print(f"Downloading results for {job_id}...")
            content = self.client.files.download(file=info['output_uri'])
            
            if isinstance(content, bytes):
                full_content = content.decode('utf-8')
            else:
                full_content = b"".join(content).decode('utf-8')
            
            results = {}
            for line in full_content.strip().split('\n'):
                if not line: continue
                resp = json.loads(line)
                custom_id = resp.get('custom_id')
                
                # Extract text from OpenAI-compatible response format
                try:
                    choices = resp.get('response', {}).get('body', {}).get('choices', [])
                    if choices:
                        text = choices[0].get('message', {}).get('content', '')
                        results[custom_id] = text
                except Exception as parse_err:
                    logging.error(f"Error parsing line for {custom_id}: {parse_err}")
            
            return results
        except Exception as e:
            logging.error(f"Error downloading results for {job_id}: {e}")
            return None

    def process_completed_jobs(self, storage, extractor=None):
        """Processes all COMPLETED jobs and updates storage/files."""
        if not os.path.exists(JOBS_FILE):
            return
            
        with open(JOBS_FILE, 'r') as f:
            try:
                jobs = json.load(f)
            except:
                return
            
        updated_any = False
        for job_id, info in list(jobs.items()):
            if info['status'] == 'COMPLETED' and not info.get('processed'):
                results = self.get_job_results(job_id)
                if not results:
                    continue
                
                metadata = info.get('metadata', {})
                if metadata.get('type') == 'summary':
                    date_str = metadata.get('date')
                    print(f"Updating summary data for {date_str}...")
                    data = storage.load_daily_data(date_str)
                    if data:
                        for p in data:
                            if p['id'] in results:
                                raw_result = results[p['id']]
                                try:
                                    # Try to parse the result as JSON
                                    cleaned_text = raw_result.strip()
                                    if cleaned_text.startswith("```json"): cleaned_text = cleaned_text[7:]
                                    if cleaned_text.startswith("```"): cleaned_text = cleaned_text[3:]
                                    if cleaned_text.endswith("```"): cleaned_text = cleaned_text[:-3]
                                    
                                    parsed_res = json.loads(cleaned_text.strip())
                                    p['summary_ja'] = parsed_res.get('summary_ja', 'パースエラー')
                                    p['contribution_ja'] = parsed_res.get('contribution_ja', 'パースエラー')
                                except Exception as e:
                                    logging.error(f"Failed to parse batch result JSON for {p['id']}: {e}")
                                    p['summary_ja'] = raw_result # Fallback to raw text
                                    p['contribution_ja'] = "エラー: JSON形式ではありません"
                        storage.save_daily_data(data, date_str)
                        info['processed'] = True
                        updated_any = True
                
                elif metadata.get('type') == 'slide':
                    username = metadata.get('user')
                    date_str = metadata.get('date')
                    print(f"Generating Batch PDF for {username} on {date_str}...")

                    if not extractor:
                        from slide_generator import SlideContentExtractor
                        extractor = SlideContentExtractor()

                    favorites = storage.get_favorites(username)
                    target_papers = [p for p in favorites if (p.get('list_date') or p.get('saved_at', '')[:10]) == date_str]

                    output_dir = os.path.join(storage.USERS_DIR, username, 'slides')
                    if not os.path.exists(output_dir): os.makedirs(output_dir)

                    filename = f"slides_{date_str}.pdf"
                    output_path = os.path.join(output_dir, filename)

                    import slide_generator
                    from reportlab.pdfgen import canvas
                    c = canvas.Canvas(output_path, pagesize=slide_generator.landscape(slide_generator.A4))
                    w, h = slide_generator.landscape(slide_generator.A4)

                    c.setFont(extractor.font_name, 30)
                    c.drawCentredString(w/2, h/2 + 20, "ArXiv Paper Digest (Batch)")
                    c.setFont(extractor.font_name, 16)
                    c.drawCentredString(w/2, h/2 - 20, f"Generated on {time.strftime('%Y-%m-%d')}")
                    c.showPage()

                    for paper in target_papers:
                        custom_id = paper['id']
                        if custom_id in results:
                            raw_result = results[custom_id]
                            try:
                                cleaned_text = raw_result.strip()
                                if cleaned_text.startswith("```json"): cleaned_text = cleaned_text[7:]
                                if cleaned_text.startswith("```"): cleaned_text = cleaned_text[3:]
                                if cleaned_text.endswith("```"): cleaned_text = cleaned_text[:-3]

                                parsed_res = json.loads(cleaned_text.strip())

                                url = paper.get('url')
                                pdf_stream = extractor._download_pdf(url)
                                images, _ = extractor._pdf_to_images(pdf_stream, num_pages=4)

                                def crop_fig(fig_key):
                                    fig_info = parsed_res.get(fig_key)
                                    if not fig_info: return None
                                    page_idx = fig_info.get("page_index")
                                    bbox = fig_info.get("bbox")
                                    if page_idx is None or bbox is None or not isinstance(bbox, list) or len(bbox) != 4:
                                        return None
                                    if 0 <= page_idx < len(images):
                                        target_img = images[page_idx]
                                        img_w, img_h = target_img.size
                                        ymin, xmin, ymax, xmax = bbox
                                        if ymax <= ymin or xmax <= xmin: return None
                                        left = (xmin / 1000) * img_w
                                        top = (ymin / 1000) * img_h
                                        right = (xmax / 1000) * img_w
                                        bottom = (ymax / 1000) * img_h
                                        try:
                                            return target_img.crop((left, top, right, bottom))
                                        except Exception as ce:
                                            logging.error(f"Crop error {ce}")
                                            return None
                                    return None

                                img1 = crop_fig("figure1")
                                img2 = crop_fig("figure2")

                                slide_data = {
                                    "meta": parsed_res,
                                    "image1": img1,
                                    "image2": img2,
                                    "arxiv_url": url.replace('/pdf/', '/abs/').replace('.pdf', '')
                                }
                                extractor._draw_paper_slide(c, slide_data)
                                c.showPage()
                            except Exception as e:
                                logging.error(f"Failed to generate slide from batch result for {custom_id}: {e}")
                                c.setFont("Helvetica", 12)
                                c.drawString(100, 100, f"Error rendering content: {e}")
                                c.showPage()

                    c.save()
                    info['processed'] = True
                    updated_any = True

        if updated_any:
            with open(JOBS_FILE, 'w') as f:
                json.dump(jobs, f, indent=2)
