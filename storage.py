import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
USERS_DIR = os.path.join(DATA_DIR, 'users')

def save_daily_data(data, date_str=None):
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    filepath = os.path.join(DATA_DIR, f"{date_str}.json")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Saved data to {filepath}")

def load_daily_data(date_str):
    filepath = os.path.join(DATA_DIR, f"{date_str}.json")
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_available_dates():
    if not os.path.exists(DATA_DIR):
        return []
    
    # Filter out directories and non-json files
    files = [f for f in os.listdir(DATA_DIR) 
             if f.endswith('.json') and os.path.isfile(os.path.join(DATA_DIR, f))]
    dates = [f.replace('.json', '') for f in files]
    dates.sort(reverse=True)
    return dates

def _get_user_favorites_file(username):
    user_dir = os.path.join(USERS_DIR, username)
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)
    return os.path.join(user_dir, 'favorites.json')

def get_favorites(username):
    filepath = _get_user_favorites_file(username)
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_favorite(username, paper):
    favorites = get_favorites(username)
    filepath = _get_user_favorites_file(username)
    
    # Check if already exists
    for fav in favorites:
        if fav.get('id') == paper.get('id'):
            return False # Already exists
            
    # Add timestamp
    paper['saved_at'] = datetime.now().isoformat()
    favorites.insert(0, paper) # Add to top
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(favorites, f, ensure_ascii=False, indent=2)
    return True

def delete_favorite(username, paper_id):
    favorites = get_favorites(username)
    filepath = _get_user_favorites_file(username)
    
    original_len = len(favorites)
    favorites = [p for p in favorites if p.get('id') != paper_id]
    
    if len(favorites) != original_len:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(favorites, f, ensure_ascii=False, indent=2)
        return True
    return False

def delete_favorites_by_date(username, date_str):
    """
    date_str: 'YYYY-MM-DD'
    """
    favorites = get_favorites(username)
    filepath = _get_user_favorites_file(username)
    
    original_len = len(favorites)
    # saved_at is ISO format "2026-01-13T10:00:00..."
    favorites = [p for p in favorites if not p.get('saved_at', '').startswith(date_str)]
    
    if len(favorites) != original_len:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(favorites, f, ensure_ascii=False, indent=2)
        return True
    return False
