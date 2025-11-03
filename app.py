import sqlite3
import time
import json
import os
import requests  # <-- NEW IMPORT
from flask import Flask, request, g, render_template, jsonify
from flask_socketio import SocketIO, emit
from datetime import datetime
from typing import Dict
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

DATABASE = 'signals.db'

# GEOFENCING BOUNDING BOX for VIT Chennai
VIT_MIN_LAT = 12.8300
VIT_MAX_LAT = 12.8500
VIT_MIN_LON = 80.1430
VIT_MAX_LON = 80.1630

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a-default-fallback-key-for-dev')
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "10 per minute"]
)

# DB helpers
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, check_same_thread=False, timeout=10)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def validate_sample(sample: Dict) -> bool:
    """Check if a sample has the minimum required fields and is on campus."""
    if 'latitude' not in sample or 'longitude' not in sample:
        return False
    
    try:
        lat = float(sample['latitude'])
        lon = float(sample['longitude'])
        if not (VIT_MIN_LAT <= lat <= VIT_MAX_LAT and VIT_MIN_LON <= lon <= VIT_MAX_LON):
            print(f"Skipping sample outside VIT bounds: {lat}, {lon}")
            return False
    except (ValueError, TypeError):
        return False
        
    return True


# The single, correct insert_sample function
def insert_sample(sample: Dict):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        '''INSERT INTO samples (timestamp, latitude, longitude, carrier, dbm, network_type, device_id, download_mbps, upload_mbps)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            sample['timestamp'],
            sample['latitude'],
            sample['longitude'],
            sample.get('carrier'),
            sample.get('dbm'),
            sample.get('network_type'),
            sample.get('device_id'),
            sample.get('download_mbps'),
            sample.get('upload_mbps'),
        ),
    )
    db.commit()
    return cur.lastrowid


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload')
def upload_page():
    """Serve the page for users to contribute data."""
    return render_template('upload.html')

# --- NEW API ENDPOINT ---
@app.route('/api/get-carrier')
@limiter.limit("15 per minute")
def get_carrier():
    """Get the client's carrier from their IP address."""
    ip_address = request.remote_addr

    # Handle localhost for testing
    if ip_address == '127.0.0.1':
        return jsonify({'carrier': 'Jio', 'message': 'Test IP detected'})

    try:
        # Call the third-party API as you described
        url = f"http://ip-api.com/json/{ip_address}?fields=status,message,carrier"
        response = requests.get(url, timeout=3)
        response.raise_for_status() # Raise an error for bad responses
        data = response.json()

        if data.get('status') == 'success' and data.get('carrier'):
            return jsonify({'carrier': data['carrier']})
        else:
            return jsonify({'error': data.get('message', 'Could not detect carrier')}), 404
            
    except requests.exceptions.RequestException as e:
        print(f"Carrier lookup failed: {e}")
        return jsonify({'error': 'Carrier lookup service failed'}), 503
# --- END NEW API ENDPOINT ---

@app.route('/api/submit', methods=['POST'])
@limiter.limit("5 per minute")
def submit():
    """Accept a JSON payload describing a single sample (or list of samples)."""
    payload = request.get_json()
    if not payload:
        return jsonify({'status': 'error', 'message': 'Invalid JSON payload'}), 400

    try:
        if isinstance(payload, list):
            valid_samples = []
            for s in payload:
                s.setdefault('timestamp', int(time.time()))
                if validate_sample(s):
                    insert_sample(s)
                    valid_samples.append(s)
                else:
                    print(f"Skipping invalid sample: {s}")

            if not valid_samples:
                 return jsonify({'status': 'error', 'message': 'No valid samples provided'}), 400

            socketio.emit('new_samples', valid_samples)
            return jsonify({'status': 'ok', 'inserted': len(valid_samples)})

        # Handle single sample
        sample = payload
        sample.setdefault('timestamp', int(time.time()))
        
        if not validate_sample(sample):
            return jsonify({'status': 'error', 'message': 'Invalid data or location outside campus area.'}), 400

        insert_sample(sample)
        socketio.emit('new_sample', sample)
        return jsonify({'status': 'ok'})

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({'status': 'error', 'message': 'Database insertion failed'}), 500
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({'status': 'error', 'message': 'An unexpected error occurred'}), 500

@app.route('/api/samples', methods=['GET'])
def samples():
    """Return recent samples, optional filters: ?carrier=Airtel&network_type=4G&limit=100"""
    carrier = request.args.get('carrier')
    network_type = request.args.get('network_type')
    
    try:
        limit = int(request.args.get('limit', 1000))
    except ValueError:
        limit = 1000 

    db = get_db()
    query = 'SELECT * FROM samples'
    clauses = []
    args = []

    if carrier:
        clauses.append('carrier = ?')
        args.append(carrier)
    if network_type:
        clauses.append('network_type = ?')
        args.append(network_type)

    if clauses:
        query += ' WHERE ' + ' AND '.join(clauses)

    query += ' ORDER BY timestamp DESC LIMIT ?'
    args.append(limit)

    rows = db.execute(query, args).fetchall()
    out = [dict(row) for row in rows]
    return jsonify(out)


@socketio.on('connect')
def on_connect():
    print('Client connected')
    emit('connected', {'msg': 'hello'})


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)