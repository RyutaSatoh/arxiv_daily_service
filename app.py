from flask import Flask, render_template, abort, request, jsonify, redirect, url_for, send_file
import storage
import slide_generator
import os
import uuid
import threading
import time

app = Flask(__name__)

SLIDE_GEN_WHITELIST = {'ryuta', 'yusuke'}

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/u/<username>')
def index(username):
    dates = storage.get_available_dates()
    return render_template('index.html', dates=dates, username=username)

@app.route('/u/<username>/date/<date_str>')
def detail(username, date_str):
    papers = storage.load_daily_data(date_str)
    if papers is None:
        abort(404)
    return render_template('detail.html', date=date_str, papers=papers, username=username)

@app.route('/u/<username>/player/<date_str>')
def player(username, date_str):
    papers = storage.load_daily_data(date_str)
    if papers is None:
        abort(404)
    return render_template('player.html', date=date_str, papers=papers, username=username)

@app.route('/u/<username>/favorites')
def favorites(username):
    raw_papers = storage.get_favorites(username)
    # Group by date
    grouped_papers = {}
    for p in raw_papers:
        # Use list_date if available (publication list date), else fallback to saved date
        date_key = p.get('list_date')
        if not date_key:
            # Extract YYYY-MM-DD from saved_at (ISO string)
            date_key = p.get('saved_at', '').split('T')[0]
        
        if not date_key:
            date_key = "Unknown"
        
        if date_key not in grouped_papers:
            grouped_papers[date_key] = []
        grouped_papers[date_key].append(p)
    
    # Sort dates descending
    sorted_dates = sorted(grouped_papers.keys(), reverse=True)
    
    can_generate_slides = username in SLIDE_GEN_WHITELIST
    
    return render_template('favorites.html', grouped_papers=grouped_papers, sorted_dates=sorted_dates, username=username, can_generate_slides=can_generate_slides)

# API endpoints now include username in the URL for better REST structure/security scoping
@app.route('/api/u/<username>/save_paper', methods=['POST'])
def save_paper(username):
    paper = request.json
    if not paper or 'id' not in paper:
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
    
    saved = storage.save_favorite(username, paper)
    return jsonify({'status': 'success', 'saved': saved})

@app.route('/api/u/<username>/delete_favorite', methods=['POST'])
def delete_favorite(username):
    data = request.json
    if not data or 'id' not in data:
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
    
    deleted = storage.delete_favorite(username, data['id'])
    return jsonify({'status': 'success', 'deleted': deleted})

@app.route('/api/u/<username>/delete_favorites_by_date', methods=['POST'])
def delete_favorites_by_date(username):
    data = request.json
    if not data or 'date' not in data:
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
    
    deleted = storage.delete_favorites_by_date(username, data['date'])
    return jsonify({'status': 'success', 'deleted': deleted})

import uuid

import threading

# Global status tracking for background tasks
# { 'username_date': { 'status': 'running'|'completed'|'error', 'progress': '3/15', 'error_msg': '...' } }
GENERATION_STATUS = {}

def background_generate_slides(username, date_str, papers, output_path, status_key):
    try:
        extractor = slide_generator.SlideContentExtractor()
        
        # We need to track progress inside generate_slides_for_papers or similar.
        # For now, let's wrap the loop here if possible, or just call the extractor.
        # To provide granular progress, I'll modify the extractor's method or do it here.
        
        prs = slide_generator.landscape(slide_generator.A4)
        c = slide_generator.canvas.Canvas(output_path, pagesize=prs)
        w, h = prs
        
        # Title Page
        c.setFont(extractor.font_name, 30)
        c.drawCentredString(w/2, h/2 + 20, "ArXiv Paper Digest")
        c.setFont(extractor.font_name, 16)
        c.drawCentredString(w/2, h/2 - 20, f"Generated on {time.strftime('%Y-%m-%d')}")
        c.showPage()
        
        for i, paper in enumerate(papers):
            GENERATION_STATUS[status_key]['progress'] = f"{i+1}/{len(papers)}"
            url = paper.get('url')
            if not url: continue
            
            try:
                data = extractor.extract_content(url)
                if data:
                    extractor._draw_paper_slide(c, data)
                    c.showPage()
            except Exception as e:
                print(f"Error in background task for {url}: {e}")
        
        c.save()
        GENERATION_STATUS[status_key]['status'] = 'completed'
    except Exception as e:
        print(f"Background task failed: {e}")
        GENERATION_STATUS[status_key]['status'] = 'error'
        GENERATION_STATUS[status_key]['error_msg'] = str(e)

@app.route('/api/u/<username>/generate_slides', methods=['POST'])
def generate_slides(username):
    if username not in SLIDE_GEN_WHITELIST:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.json
    date_str = data.get('date')
    force = data.get('force', False)
    
    if not date_str:
        return jsonify({'status': 'error', 'message': 'Date required'}), 400
        
    status_key = f"{username}_{date_str}"
    
    # Get papers for this date
    favorites = storage.get_favorites(username)
    target_papers = [p for p in favorites if (p.get('list_date') or p.get('saved_at', '')[:10]) == date_str]
    
    if not target_papers:
        return jsonify({'status': 'error', 'message': 'No saved papers for this date'}), 404
        
    output_dir = os.path.join(storage.USERS_DIR, username, 'slides')
    if not os.path.exists(output_dir): os.makedirs(output_dir)
    filename = f"slides_{date_str}.pdf"
    output_path = os.path.join(output_dir, filename)
    
    # Check if already running
    if status_key in GENERATION_STATUS and GENERATION_STATUS[status_key]['status'] == 'running':
        return jsonify({'status': 'processing', 'progress': GENERATION_STATUS[status_key].get('progress')})

    # Check cache
    if not force and os.path.exists(output_path):
        download_url = url_for('download_slides', username=username, filename=filename)
        return jsonify({'status': 'success', 'download_url': download_url})
    
    # Start background thread
    GENERATION_STATUS[status_key] = {'status': 'running', 'progress': '0/%d' % len(target_papers)}
    thread = threading.Thread(target=background_generate_slides, args=(username, date_str, target_papers, output_path, status_key))
    thread.start()
    
    return jsonify({'status': 'started'})

@app.route('/api/u/<username>/generation_status/<date_str>')
def generation_status(username, date_str):
    status_key = f"{username}_{date_str}"
    info = GENERATION_STATUS.get(status_key)
    
    # If not in memory but file exists, it's completed (from previous session)
    if not info:
        output_path = os.path.join(storage.USERS_DIR, username, 'slides', f"slides_{date_str}.pdf")
        if os.path.exists(output_path):
            return jsonify({'status': 'completed', 'download_url': url_for('download_slides', username=username, filename=f"slides_{date_str}.pdf")})
        return jsonify({'status': 'not_found'})
        
    if info['status'] == 'completed':
        info['download_url'] = url_for('download_slides', username=username, filename=f"slides_{date_str}.pdf")
        
    return jsonify(info)

@app.route('/u/<username>/download_slides/<filename>')
def download_slides(username, filename):
    file_path = os.path.join(storage.USERS_DIR, username, 'slides', filename)
    if not os.path.exists(file_path):
        abort(404)
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
