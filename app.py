from flask import Flask, render_template, abort, request, jsonify, redirect, url_for, send_file
import storage
import slide_generator
import os

app = Flask(__name__)

SLIDE_GEN_WHITELIST = {'ryuta'}

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

@app.route('/api/u/<username>/generate_slides', methods=['POST'])
def generate_slides(username):
    if username not in SLIDE_GEN_WHITELIST:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.json
    date_str = data.get('date')
    force = data.get('force', False)
    
    if not date_str:
        return jsonify({'status': 'error', 'message': 'Date required'}), 400
        
    # Get papers for this date
    favorites = storage.get_favorites(username)
    target_papers = [p for p in favorites if p.get('saved_at', '').startswith(date_str)]
    
    if not target_papers:
        return jsonify({'status': 'error', 'message': 'No saved papers for this date'}), 404
        
    # Generate slides
    output_dir = os.path.join(storage.USERS_DIR, username, 'slides')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    filename = f"slides_{date_str}.pdf"
    output_path = os.path.join(output_dir, filename)
    
    # Check cache (skip if force=True)
    if not force and os.path.exists(output_path):
        print(f"Returning cached slides: {output_path}")
        download_url = url_for('download_slides', username=username, filename=filename)
        return jsonify({'status': 'success', 'download_url': download_url})
    
    # Atomic write to prevent concurrent file corruption
    temp_filename = f"temp_{uuid.uuid4().hex}.pdf"
    temp_output_path = os.path.join(output_dir, temp_filename)
    
    try:
        extractor = slide_generator.SlideContentExtractor()
        extractor.generate_slides_for_papers(target_papers, temp_output_path)
        
        # Atomic move
        os.rename(temp_output_path, output_path)
        
        download_url = url_for('download_slides', username=username, filename=filename)
        return jsonify({'status': 'success', 'download_url': download_url})
    except Exception as e:
        print(f"Slide generation error: {e}")
        # Clean up temp file
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/u/<username>/download_slides/<filename>')
def download_slides(username, filename):
    file_path = os.path.join(storage.USERS_DIR, username, 'slides', filename)
    if not os.path.exists(file_path):
        abort(404)
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)