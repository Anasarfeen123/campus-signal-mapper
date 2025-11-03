import sqlite3
import time
import json
from flask import Flask, request, g, render_template, jsonify
from flask_socketio import SocketIO, emit
from datetime import datetime
from typing import Dict

DATABASE = 'signals.db'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace-with-secure-key'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')


# DB helpers
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, check_same_thread=False)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


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


@app.route('/api/submit', methods=['POST'])
def submit():
    """Accept a JSON payload describing a single sample (or list of samples)."""
    payload = request.get_json(force=True)

    if isinstance(payload, list):
        ids = []
        for s in payload:
            s.setdefault('timestamp', int(time.time()))
            insert_sample(s)
            ids.append(True)
        socketio.emit('new_samples', payload, broadcast=True)
        return jsonify({'status': 'ok', 'inserted': len(ids)})

    sample = payload
    sample.setdefault('timestamp', int(time.time()))
    insert_sample(sample)
    socketio.emit('new_sample', sample, broadcast=True)
    return jsonify({'status': 'ok'})


@app.route('/api/samples', methods=['GET'])
def samples():
    """Return recent samples, optional filters: ?carrier=Airtel&network_type=4G&limit=100"""
    carrier = request.args.get('carrier')
    network_type = request.args.get('network_type')
    limit = int(request.args.get('limit', 1000))

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
