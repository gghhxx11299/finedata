from flask import Flask, request, jsonify, session, send_file
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_secret_key_for_development')

# User data storage (in production, use a proper database)
USERS_FILE = 'users.json'

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

@app.route('/api/auth/google', methods=['POST'])
def google_login():
    data = request.json
    google_user_id = data.get('googleId')
    name = data.get('name')
    email = data.get('email')
    
    if not google_user_id or not email:
        return jsonify({'error': 'Missing required fields'}), 400
    
    users = load_users()
    
    # Check if user exists
    if google_user_id in users:
        user = users[google_user_id]
        # Update user info if needed
        user.update({
            'name': name,
            'email': email,
            'last_login': datetime.now().isoformat(),
        })
    else:
        # Create new user
        users[google_user_id] = {
            'id': google_user_id,
            'name': name,
            'email': email,
            'created_at': datetime.now().isoformat(),
            'last_login': datetime.now().isoformat(),
            'download_count': 0,
            'datasets_downloaded': []
        }
    
    save_users(users)
    
    # Store user info in session
    session['google_user_id'] = google_user_id
    session['name'] = name
    session['email'] = email
    
    return jsonify({
        'success': True,
        'user': {
            'id': google_user_id,
            'name': name,
            'email': email
        }
    })

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    if 'google_user_id' in session:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': session['google_user_id'],
                'name': session['name'],
                'email': session['email']
            }
        })
    else:
        return jsonify({'authenticated': False}), 401

@app.route('/api/datasets/<dataset_name>', methods=['GET'])
def download_dataset(dataset_name):
    if 'google_user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    # Log the download
    users = load_users()
    user_id = session['google_user_id']
    
    if user_id in users:
        users[user_id]['download_count'] += 1
        if dataset_name not in users[user_id]['datasets_downloaded']:
            users[user_id]['datasets_downloaded'].append(dataset_name)
    
    save_users(users)
    
    # In a real implementation, you would return the actual dataset file
    # This is just a mock to show the structure
    dataset_path = f"datasets/{dataset_name}.json"  # Or .csv, .xlsx, etc.
    
    if os.path.exists(dataset_path):
        return send_file(dataset_path, as_attachment=True)
    else:
        return jsonify({'error': 'Dataset not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)