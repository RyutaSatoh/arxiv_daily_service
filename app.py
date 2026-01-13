from flask import Flask, render_template, abort, request, jsonify
import storage

app = Flask(__name__)

@app.route('/')
def index():
    dates = storage.get_available_dates()
    return render_template('index.html', dates=dates)

@app.route('/date/<date_str>')
def detail(date_str):
    papers = storage.load_daily_data(date_str)
    if papers is None:
        abort(404)
    return render_template('detail.html', date=date_str, papers=papers)

@app.route('/player/<date_str>')
def player(date_str):
    papers = storage.load_daily_data(date_str)
    if papers is None:
        abort(404)
    return render_template('player.html', date=date_str, papers=papers)

@app.route('/favorites')
def favorites():
    raw_papers = storage.get_favorites()
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
    
    return render_template('favorites.html', grouped_papers=grouped_papers, sorted_dates=sorted_dates)

@app.route('/api/save_paper', methods=['POST'])
def save_paper():
    paper = request.json
    if not paper or 'id' not in paper:
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
    
    saved = storage.save_favorite(paper)
    return jsonify({'status': 'success', 'saved': saved})

@app.route('/api/delete_favorite', methods=['POST'])
def delete_favorite():
    data = request.json
    if not data or 'id' not in data:
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
    
    deleted = storage.delete_favorite(data['id'])
    return jsonify({'status': 'success', 'deleted': deleted})

@app.route('/api/delete_favorites_by_date', methods=['POST'])
def delete_favorites_by_date():
    data = request.json
    if not data or 'date' not in data:
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
    
    deleted = storage.delete_favorites_by_date(data['date'])
    return jsonify({'status': 'success', 'deleted': deleted})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
