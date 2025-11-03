import sqlite3
import time
import json
import os  # Import os to access environment variables
from flask import Flask, request, g, render_template, jsonify
from flask_socketio import SocketIO, emit
from datetime import datetime
from typing import Dict

DATABASE = 'signals.db'

app = Flask(__name__)
# Load secret key from an environment variable for security
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a-default-fallback-key-for-dev')
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')


# DB helpers
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        # Add timeout=10 to wait 10 seconds if the DB is locked
        db = g._database = sqlite3.connect(DATABASE, check_same_thread=False, timeout=10)
        db.row_factory = sqlite3.Row
    return db

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

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def validate_sample(sample: Dict) -> bool:
    """Check if a sample has the minimum required fields."""
    return 'latitude' in sample and 'longitude' in sample


def insert_sample(sample: Dict):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        '''INSERT INTO samples (timestamp, latitude, longitude, carrier, dbm, network_type, device_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (
            sample['timestamp'],
            sample['latitude'],
            sample['longitude'],
            sample.get('carrier'),
            sample.get('dbm'),
            sample.get('network_type'),
            sample.get('device_id'),
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

@app.route('/api/submit', methods=['POST'])
def submit():
    """Accept a JSON payload describing a single sample (or list of samples)."""
    payload = request.get_json()  # Don't use force=True
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
                    print(f"Skipping invalid sample: {s}") # Log invalid data

            if not valid_samples:
                 return jsonify({'status': 'error', 'message': 'No valid samples provided'}), 400

            # --- FIX ---
            # Removed broadcast=True
            socketio.emit('new_samples', valid_samples)
            # --- END FIX ---
            
            return jsonify({'status': 'ok', 'inserted': len(valid_samples)})

        # Handle single sample
        sample = payload
        sample.setdefault('timestamp', int(time.time()))
        if not validate_sample(sample):
            return jsonify({'status': 'error', 'message': 'Missing required fields (latitude, longitude)'}), 400

        insert_sample(sample)
        
        # --- FIX ---
        # Removed broadcast=True
        socketio.emit('new_sample', sample)
        # --- END FIX ---

        return jsonify({'status': 'ok'})

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        # Check for specific "database is locked" error
        if "locked" in str(e).lower():
            return jsonify({'status': 'error', 'message': 'Database is busy, please try again.'}), 503 # Service Unavailable
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
        limit = 1000 # Default to 1000 if limit is not a valid integer

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
    # Set the FLASK_SECRET_KEY environment variable before running
    # export FLASK_SECRET_KEY='your-very-secure-random-string'
    socketio.run(app, host='0.0.0.0', port=5000)