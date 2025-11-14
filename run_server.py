from flask import Flask, request, jsonify, session, send_file, render_template_string, send_from_directory
import json
import os
from datetime import datetime
import uuid

app = Flask(__name__, static_folder='.')

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

@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/static/<path:filename>')
def serve_static_files(filename):
    # Specific route for static files in static/ directory
    return send_from_directory('static', filename)

@app.route('/<path:filename>')
def serve_other_files(filename):
    # Serve any HTML file or other asset
    if filename.endswith('.html'):
        return send_from_directory('.', filename)
    else:
        # For other static assets that aren't in the static/ folder
        try:
            return send_from_directory('.', filename)
        except FileNotFoundError:
            # If file doesn't exist in root, try static directory
            try:
                return send_from_directory('static', filename)
            except FileNotFoundError:
                # Return a 404 page if not found
                return "File not found", 404

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

@app.route('/api/datasets/<dataset_name>')
def download_dataset(dataset_name):
    # Check if user is authenticated
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
    # For demonstration, create a mock dataset
    mock_data = f"""Mock Dataset: {dataset_name}
Generated for user: {session['name']}
Email: {session['email']}
Download time: {datetime.now().isoformat()}
    
This is a placeholder. In a real implementation, this would be your actual dataset.
"""
    
    # Create a temporary file to serve
    import tempfile
    temp_filename = f'/tmp/{dataset_name}_data.txt'
    with open(temp_filename, 'w') as f:
        f.write(mock_data)
    
    return send_file(temp_filename, as_attachment=True, download_name=f"{dataset_name}_data.txt")

# API endpoint to get user download history
@app.route('/api/user/downloads', methods=['GET'])
def get_download_history():
    if 'google_user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    users = load_users()
    user_id = session['google_user_id']
    
    if user_id in users:
        return jsonify({
            'download_count': users[user_id]['download_count'],
            'datasets': users[user_id]['datasets_downloaded']
        })
    else:
        return jsonify({'download_count': 0, 'datasets': []})

if __name__ == '__main__':
    print("Starting Finedatas server...")
    print("Visit http://localhost:5000 to access the site")
    print("Make sure to add your Google Client ID in the HTML files")
    app.run(debug=True, host='0.0.0.0', port=5000)